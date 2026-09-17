#!/usr/bin/env python3
"""Data-driven decision-tree rule mining from v37 self-play (W-DataDriven).

Pipeline phases (run via subcommand):
  collect  : play 1000 games (5 pairings x 200), dump per-turn rows to CSV
  train    : run experiment A (wins only) / B (strong vs weak) / C (cross-val
             vs W-Tree top-15 dataset), emit rules.txt + per-experiment trees
  crosscheck : compute precision of W-Tree R1 / R2 on v37 self-play data and
             of new rules on the W-Tree top-15 dataset

Features kept aligned with scripts/mine_decisions.py so cross-checks are valid.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from collections import Counter
from multiprocessing import Pool, cpu_count
from pathlib import Path

logging.disable(logging.INFO)  # silence kaggle_environments noise during workers

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.tree import DecisionTreeClassifier, _tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT_CSV = REPORTS / "datadriven_dataset.csv"
OUT_RULES_TXT = REPORTS / "datadriven_rules.txt"
OUT_RULES_CSV = REPORTS / "datadriven_rules.csv"

FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}

# Feature columns used for tree training (must match W-Tree to allow cross-val).
FEATURES = [
    "step", "factory_gap", "factory_energy",
    "factory_move_cd", "factory_jump_cd", "factory_build_cd",
    "scout_count", "worker_count", "miner_count", "support_count",
    "support_energy",
    "enemy_support_count", "enemy_support_energy", "enemy_factory_min_dist",
    "adj_north_mining_node", "adj_north_own_mine",
    "adj_east_mining_node", "adj_east_own_mine",
    "adj_west_mining_node", "adj_west_own_mine",
    "adj_south_mining_node", "adj_south_own_mine",
]

# Match W-Tree's exact feature ordering for cross-validation experiment C.
WTREE_FEATURES = [
    "step", "factory_gap", "factory_energy", "factory_jump_cd",
    "factory_build_cd", "factory_move_cd", "support_count",
    "scout_count", "miner_count", "worker_count", "support_energy",
    "enemy_support_count", "enemy_factory_min_dist",
    "adj_north_mining_node", "adj_north_own_mine",
    "adj_side_mining_node", "wall_north_blocked", "north_remaining",
]

V37 = str(ROOT / "experiments/v37_late_save_jump_no_scout/main.py")
PAIRS = {
    "v37_vs_v37":       (V37, str(ROOT / "experiments/v37_late_save_jump_no_scout/main.py")),
    "v37_vs_v24":       (V37, str(ROOT / "experiments/v24_jump_enemy_factory_avoid/main.py")),
    "v37_vs_top2":      (V37, str(ROOT / "baselines/top2_jump_bfs/main.py")),
    "v37_vs_worker":    (V37, str(ROOT / "baselines/worker_bfs/main.py")),
    "v37_vs_pilkwang":  (V37, str(ROOT / "baselines/pilkwang_structure/main.py")),
}

# ---------- feature extraction (shared with W-Tree) -----------------------

def _parse_pos_set(d):
    out = set()
    for k in d or {}:
        a, b = k.split(",")
        out.add((int(a), int(b)))
    return out


def _own_mines(mines, player):
    out = set()
    for k, v in (mines or {}).items():
        if len(v) >= 3 and v[2] == player:
            a, b = k.split(",")
            out.add((int(a), int(b)))
    return out


def extract_row(step_state, next_state, owner, width):
    """Extract (obs features, next-action label) for `owner`.

    IMPORTANT: in kaggle_environments, env.steps[t].action is the action that
    produced obs at step t (i.e. chosen from obs at step t-1). To pair
    "agent saw X, chose Y", we read obs from step_state[t] and the label
    from next_state[t+1].action. Pass next_state=None for the final step.

    Returns None if obs is empty / factory missing / next action not present.
    """
    rec = step_state[owner]
    obs = rec.get("observation") or {}
    if not obs or next_state is None:
        return None
    robots = obs.get("globalRobots") or obs.get("robots") or {}
    fac = fac_uid = None
    for uid, r in robots.items():
        if r[0] == FACTORY and r[4] == owner:
            fac, fac_uid = r, uid
            break
    if fac is None:
        return None
    next_rec = next_state[owner] if owner < len(next_state) else None
    if next_rec is None:
        return None
    label = (next_rec.get("action") or {}).get(fac_uid)
    if not label:
        return None
    fc, fr, fe = fac[1], fac[2], fac[3]
    fmove = fac[5] if len(fac) > 5 else 0
    fjump = fac[6] if len(fac) > 6 else 0
    fbuild = fac[7] if len(fac) > 7 else 0
    south = obs.get("southBound", 0)
    north = obs.get("northBound", 0)

    own = [r for r in robots.values() if r[4] == owner]
    enemy = [r for r in robots.values() if r[4] != owner]
    sup = [r for r in own if r[0] != FACTORY]
    enemy_sup = [r for r in enemy if r[0] != FACTORY]
    enemy_fac = [r for r in enemy if r[0] == FACTORY]
    enemy_min = min((abs(r[1] - fc) + abs(r[2] - fr) for r in enemy_fac), default=99)

    mn = _parse_pos_set(obs.get("miningNodes"))
    om = _own_mines(obs.get("mines"), owner)
    walls = obs.get("walls") or []
    idx = (fr - south) * width + fc
    w_here = walls[idx] if 0 <= idx < len(walls) and walls[idx] != -1 else 0

    return {
        "step": obs.get("step", 0),
        "factory_gap": fr - south,
        "factory_row": fr,
        "factory_energy": fe,
        "factory_move_cd": fmove,
        "factory_jump_cd": fjump,
        "factory_build_cd": fbuild,
        "scout_count": sum(1 for r in sup if r[0] == 1),
        "worker_count": sum(1 for r in sup if r[0] == 2),
        "miner_count": sum(1 for r in sup if r[0] == 3),
        "support_count": len(sup),
        "support_energy": sum(r[3] for r in sup),
        "enemy_support_count": len(enemy_sup),
        "enemy_support_energy": sum(r[3] for r in enemy_sup),
        "enemy_factory_min_dist": enemy_min,
        "adj_north_mining_node": int((fc, fr + 1) in mn),
        "adj_north_own_mine":    int((fc, fr + 1) in om),
        "adj_east_mining_node":  int((fc + 1, fr) in mn),
        "adj_east_own_mine":     int((fc + 1, fr) in om),
        "adj_west_mining_node":  int((fc - 1, fr) in mn),
        "adj_west_own_mine":     int((fc - 1, fr) in om),
        "adj_south_mining_node": int((fc, fr - 1) in mn),
        "adj_south_own_mine":    int((fc, fr - 1) in om),
        "adj_side_mining_node":  int((fc + 1, fr) in mn or (fc - 1, fr) in mn),
        "wall_north_blocked":    int(bool(w_here & WALL_BITS["NORTH"])),
        "north_remaining":       north - fr,
        "__label__": label,
    }


# ---------- data collection (worker for multiprocessing) -----------------

def _play_one(args):
    """Worker entry: play one game, extract per-turn features for v37 side.

    Returns list[dict] (no DataFrame to keep IPC cheap).
    """
    pair_name, p0_path, p1_path, seed, v37_is_p0 = args
    # Lazy import inside worker to avoid Pool fork issues with kaggle's globals.
    from kaggle_environments import make  # noqa: WPS433

    env = make("crawl", configuration={"seed": seed}, debug=False)
    if v37_is_p0:
        env.run([p0_path, p1_path])
        owner = 0
    else:
        env.run([p1_path, p0_path])
        owner = 1
    width = env.configuration.width
    final = env.steps[-1]
    r0 = final[0].get("reward") or 0
    r1 = final[1].get("reward") or 0
    v37_reward = r0 if v37_is_p0 else r1
    other = r1 if v37_is_p0 else r0
    if v37_reward > other:
        outcome = 1
    elif v37_reward < other:
        outcome = -1
    else:
        outcome = 0
    rows = []
    steps = env.steps
    for t in range(len(steps) - 1):
        st = steps[t]
        nxt = steps[t + 1]
        if owner >= len(st):
            continue
        row = extract_row(st, nxt, owner, width)
        if row is None:
            continue
        row["pair"] = pair_name
        row["seed"] = seed
        row["v37_is_p0"] = int(v37_is_p0)
        row["v37_reward"] = float(v37_reward)
        row["is_winning"] = outcome
        rows.append(row)
    return rows


def collect(games_per_pair: int = 200, processes: int | None = None) -> None:
    """Play games_per_pair games for each pairing, half v37-as-p0 / half as p1.

    Writes one big CSV at OUT_CSV.
    """
    tasks = []
    for name, (p0, p1) in PAIRS.items():
        half = games_per_pair // 2
        for seed in range(1, half + 1):
            tasks.append((name, p0, p1, seed, True))
            tasks.append((name, p0, p1, seed, False))
    procs = processes or max(1, min(cpu_count() - 1, 6))
    print(f"[collect] tasks={len(tasks)} processes={procs} pairs={list(PAIRS)}")
    t0 = time.time()
    written = 0
    REPORTS.mkdir(exist_ok=True)
    # Stream to CSV to avoid OOM if dataset gets large.
    fh = OUT_CSV.open("w", newline="")
    writer = None
    done = 0
    with Pool(processes=procs) as pool:
        for rows in pool.imap_unordered(_play_one, tasks, chunksize=2):
            if rows:
                if writer is None:
                    writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                writer.writerows(rows)
                written += len(rows)
            done += 1
            if done % 50 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed else 0
                eta = (len(tasks) - done) / rate if rate else 0
                print(
                    f"[collect] {done}/{len(tasks)} games done, rows={written}, "
                    f"elapsed={elapsed/60:.1f}min, ETA={eta/60:.1f}min",
                    flush=True,
                )
    fh.close()
    print(f"[collect] DONE games={len(tasks)} rows={written} in {(time.time()-t0)/60:.1f}min -> {OUT_CSV}")


# ---------- tree training + leaf extraction ------------------------------

def _leaves(clf, classes, feature_names):
    t = clf.tree_
    out = []

    def go(node, conds):
        if t.feature[node] != _tree.TREE_UNDEFINED:
            f, thr = feature_names[t.feature[node]], t.threshold[node]
            go(t.children_left[node], conds + [f"{f} <= {thr:.2f}"])
            go(t.children_right[node], conds + [f"{f} > {thr:.2f}"])
            return
        prop = t.value[node][0]
        n = int(t.n_node_samples[node])
        if n <= 0:
            return
        order = np.argsort(-prop)
        out.append({
            "conds": " AND ".join(conds) if conds else "(root)",
            "n_samples": n,
            "majority_action": classes[int(order[0])],
            "precision": round(float(prop[order[0]]), 3),
            "second_action": classes[int(order[1])] if len(classes) > 1 else "",
            "second_share": round(float(prop[order[1]]), 3) if len(classes) > 1 else 0.0,
        })

    go(0, [])
    out.sort(key=lambda r: (-r["precision"], -r["n_samples"]))
    return out


def _fit(df: pd.DataFrame, features=FEATURES):
    if df.empty:
        return None, []
    X = df[features].astype(float).values
    y = df["__label__"].values
    clf = DecisionTreeClassifier(max_depth=4, min_samples_leaf=50, random_state=0).fit(X, y)
    return clf, _leaves(clf, list(clf.classes_), features)


def _write_rules(path: Path, title: str, df: pd.DataFrame, rules):
    high = sum(1 for r in rules if r["precision"] >= 0.6)
    with path.open("w") as fh:
        fh.write(f"# {title}\n")
        fh.write(f"# total_rows={len(df)} leaves={len(rules)} precision>=0.6={high}\n")
        fh.write(f"# top labels: {Counter(df['__label__']).most_common(10)}\n\n")
        for i, r in enumerate(rules):
            fh.write(
                f"[L{i:02d}] precision={r['precision']:.3f} n={r['n_samples']:5d} -> {r['majority_action']}\n"
                f"      IF {r['conds']}\n"
                f"      runner-up: {r['second_action']} ({r['second_share']:.3f})\n\n"
            )


def train():
    df = pd.read_csv(OUT_CSV)
    print(f"[train] loaded {len(df)} rows from {OUT_CSV}")
    print(f"[train] outcome dist: {Counter(df['is_winning'])}")
    print(f"[train] pair dist: {Counter(df['pair'])}")

    REPORTS.mkdir(exist_ok=True)
    out_a = REPORTS / "datadriven_rules_A_wins.txt"
    out_b_strong = REPORTS / "datadriven_rules_B_strong.txt"
    out_b_weak = REPORTS / "datadriven_rules_B_weak.txt"
    out_all = REPORTS / "datadriven_rules_all.txt"

    # All-data baseline (apples-to-apples with W-Tree).
    _, rules_all = _fit(df)
    _write_rules(out_all, "Data-driven all (v37 self-play, every game)", df, rules_all)

    # Experiment A: only games v37 won.
    df_wins = df[df["is_winning"] == 1]
    _, rules_a = _fit(df_wins)
    _write_rules(out_a, "Experiment A: v37 winning games only", df_wins, rules_a)

    # Experiment B: strong (v37/v24/top2) vs weak (worker/pilkwang).
    strong = df[df["pair"].isin(["v37_vs_v37", "v37_vs_v24", "v37_vs_top2"])]
    weak = df[df["pair"].isin(["v37_vs_worker", "v37_vs_pilkwang"])]
    _, rules_b_strong = _fit(strong)
    _, rules_b_weak = _fit(weak)
    _write_rules(out_b_strong, "Experiment B: strong opponents (v37/v24/top2)", strong, rules_b_strong)
    _write_rules(out_b_weak, "Experiment B: weak opponents (worker/pilkwang)", weak, rules_b_weak)

    # Concatenated main rules.txt (priority: A → all → B_strong → B_weak).
    blocks = [
        ("A_wins", rules_a),
        ("ALL",    rules_all),
        ("B_strong", rules_b_strong),
        ("B_weak", rules_b_weak),
    ]
    with OUT_RULES_TXT.open("w") as fh:
        fh.write("# data-driven leaf rules (depth=4, min_samples_leaf=50)\n")
        fh.write("# blocks: A_wins | ALL | B_strong | B_weak\n\n")
        for tag, rules in blocks:
            fh.write(f"## block={tag} leaves={len(rules)} hi(p>=0.6)={sum(1 for r in rules if r['precision'] >= 0.6)}\n")
            for i, r in enumerate(rules):
                fh.write(
                    f"[{tag}.L{i:02d}] p={r['precision']:.3f} n={r['n_samples']:5d} -> {r['majority_action']}\n"
                    f"  IF {r['conds']}\n  ru: {r['second_action']} ({r['second_share']:.3f})\n"
                )
            fh.write("\n")

    # CSV dump of all experiments for downstream diff scripts.
    rows = []
    for tag, rules in blocks:
        for i, r in enumerate(rules):
            rr = dict(r)
            rr["block"] = tag
            rr["leaf"] = f"{tag}.L{i:02d}"
            rows.append(rr)
    pd.DataFrame(rows).to_csv(OUT_RULES_CSV, index=False)
    print(f"[train] wrote {OUT_RULES_TXT} + {OUT_RULES_CSV} + per-experiment files")


# ---------- cross-check W-Tree R1/R2 + experiment C ----------------------

def _match_rule(df: pd.DataFrame, conds: dict, label: str) -> tuple[float, int]:
    """Return (precision, support) for `label` on rows matching conds.

    `conds` is a dict {col: ("op", value)} with op in {<=, >, ==}.
    """
    mask = pd.Series(True, index=df.index)
    for col, (op, val) in conds.items():
        if col not in df.columns:
            return float("nan"), 0
        if op == "<=":
            mask &= df[col] <= val
        elif op == ">":
            mask &= df[col] > val
        elif op == "==":
            mask &= df[col] == val
    sub = df[mask]
    n = len(sub)
    if n == 0:
        return float("nan"), 0
    hits = (sub["__label__"] == label).sum()
    return hits / n, n


def _wtree_dataset() -> pd.DataFrame:
    """Re-build the W-Tree top-15 + bunterrrrr dataset for cross-validation.

    Uses W-Tree's feature extraction but applies the obs(t) -> action(t+1)
    off-by-one fix so labels match agent decisions, not their consequences.
    """
    from scripts.mine_decisions import iter_replays, extract as wtree_extract  # type: ignore

    rows = []
    for path, team in iter_replays():
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        info = data.get("info", {})
        names = info.get("TeamNames") or [a.get("Name") for a in info.get("Agents", [])]
        owners = [i for i, x in enumerate(names) if x == team]
        if not owners:
            continue
        owner = owners[0]
        width = (data.get("configuration") or {}).get("width", 22)
        steps = data.get("steps") or []
        for t in range(len(steps) - 1):
            st = steps[t]
            nxt = steps[t + 1]
            if owner >= len(st) or owner >= len(nxt):
                continue
            r = wtree_extract(st, owner, width)
            if r is None:
                continue
            # Override label with action from t+1 (the action chosen from obs(t)).
            obs = (st[owner].get("observation") or {})
            robots = obs.get("globalRobots") or obs.get("robots") or {}
            fac_uid = None
            for uid, rr in robots.items():
                if rr[0] == FACTORY and rr[4] == owner:
                    fac_uid = uid
                    break
            if fac_uid is None:
                continue
            new_label = (nxt[owner].get("action") or {}).get(fac_uid)
            if not new_label:
                continue
            r["__label__"] = new_label
            rows.append(r)
    return pd.DataFrame(rows)


def crosscheck():
    df = pd.read_csv(OUT_CSV)
    print(f"[crosscheck] v37 self-play rows={len(df)}")

    # W-Tree R1 (factory_move_cd <= 1.5 AND support_energy > 299.5
    #            AND miner_count <= 0.5 AND support_energy <= 300.5 -> TRANSFER_NORTH)
    # The 299.5 < energy <= 300.5 bucket is very narrow; we also report a wider
    # band so we can tell whether the precision collapse is real or aliasing.
    # Narrow = the actual W-Tree L02 leaf: 299.5 < support_energy <= 300.5
    r1_narrow = _match_rule(
        df,
        {
            "factory_move_cd": ("<=", 1.5),
            "support_energy": (">", 299.5),
            "miner_count": ("<=", 0.5),
        },
        "TRANSFER_NORTH",
    )
    df_n = df[(df["factory_move_cd"] <= 1.5) & (df["support_energy"] > 299.5)
              & (df["support_energy"] <= 300.5) & (df["miner_count"] <= 0.5)]
    if len(df_n):
        p_n = (df_n["__label__"] == "TRANSFER_NORTH").mean()
    else:
        p_n = float("nan")
    r1_narrow = (float(p_n), int(len(df_n)))
    # Wide = no upper bound on support_energy (L08 in W-Tree).
    df_w = df[(df["factory_move_cd"] <= 1.5) & (df["support_energy"] > 300.5)
              & (df["miner_count"] <= 0.5)]
    if len(df_w):
        p_w = (df_w["__label__"] == "TRANSFER_NORTH").mean()
    else:
        p_w = float("nan")
    r1_wide = (float(p_w), int(len(df_w)))
    # R2 (factory_move_cd<=1.5 AND support_energy>299.5 AND miner_count>0.5
    #     AND adj_north_mining_node>0.5 -> BUILD_MINER_NORTH)
    r2 = _match_rule(
        df,
        {
            "factory_move_cd": ("<=", 1.5),
            "support_energy": (">", 299.5),
            "miner_count": (">", 0.5),
            "adj_north_mining_node": (">", 0.5),
        },
        "BUILD_MINER_NORTH",
    )
    # L00 baseline IDLE rule (sanity check).
    r0 = _match_rule(
        df,
        {
            "factory_move_cd": ("<=", 0.5),
            "factory_build_cd": ("<=", 9.5),
            "support_energy": ("<=", 299.5),
        },
        "IDLE",
    )

    results = {
        "L00_IDLE_baseline":          r0,
        "R1_TRANSFER_NORTH_narrow":   r1_narrow,
        "R1_TRANSFER_NORTH_wide":     r1_wide,
        "R2_BUILD_MINER_NORTH":       r2,
    }

    # Now do experiment C: rebuild W-Tree dataset, evaluate same rules on it.
    print("[crosscheck] rebuilding W-Tree top-15 dataset for cross-validation ...")
    df_wt = _wtree_dataset()
    print(f"[crosscheck] W-Tree dataset rows={len(df_wt)}")
    results_wt = {}
    if not df_wt.empty:
        for name, conds, label in [
            ("L00_IDLE_baseline",
             {"factory_move_cd": ("<=", 0.5), "factory_build_cd": ("<=", 9.5),
              "support_energy": ("<=", 299.5)}, "IDLE"),
            ("R1_TRANSFER_NORTH",
             {"factory_move_cd": ("<=", 1.5), "support_energy": (">", 299.5),
              "miner_count": ("<=", 0.5)}, "TRANSFER_NORTH"),
            ("R2_BUILD_MINER_NORTH",
             {"factory_move_cd": ("<=", 1.5), "support_energy": (">", 299.5),
              "miner_count": (">", 0.5), "adj_north_mining_node": (">", 0.5)},
             "BUILD_MINER_NORTH"),
        ]:
            results_wt[name] = _match_rule(df_wt, conds, label)

    # Pretty print.
    print("\n[v37 self-play dataset]")
    for k, (p, n) in results.items():
        print(f"  {k:30s} precision={p:.3f}  support={n}")
    print("\n[W-Tree top-15 dataset]")
    for k, (p, n) in results_wt.items():
        print(f"  {k:30s} precision={p:.3f}  support={n}")

    # Save JSON for downstream report scripts.
    out = REPORTS / "datadriven_crosscheck.json"
    payload = {
        "v37_self_play": {k: {"precision": p, "support": n} for k, (p, n) in results.items()},
        "wtree_top15":  {k: {"precision": p, "support": n} for k, (p, n) in results_wt.items()},
        "self_play_rows": int(len(df)),
        "wtree_rows":     int(len(df_wt)),
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"[crosscheck] wrote {out}")


# ---------- CLI ----------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--games-per-pair", type=int, default=200)
    c.add_argument("--processes", type=int, default=None)
    sub.add_parser("train")
    sub.add_parser("crosscheck")
    args = ap.parse_args()
    if args.cmd == "collect":
        collect(args.games_per_pair, args.processes)
    elif args.cmd == "train":
        train()
    elif args.cmd == "crosscheck":
        crosscheck()


if __name__ == "__main__":
    # Make scripts/ importable as a package for crosscheck's mine_decisions import.
    sys.path.insert(0, str(ROOT))
    main()
