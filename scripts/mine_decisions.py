#!/usr/bin/env python3
"""Mine decision-tree rules from top-15 replays (W1 'ship rules, not models').

Inputs : reports/top_competitors/<rank 02-15>/replays/episode-*.json
         reports/replays_bunterrrrr_focus/episode-*.json
Output : reports/mined_rules.txt    (one block per leaf, sorted by precision)
         reports/mined_rules.csv    (raw)

Per turn we extract that team's factory state + the action it issued, fit a
sklearn DecisionTreeClassifier(max_depth=4, min_samples_leaf=20), and dump
each leaf as `IF path THEN majority_action (precision=...)`.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, _tree

ROOT = Path(__file__).resolve().parents[1]
TC = ROOT / "reports" / "top_competitors"
BUNTER = ROOT / "reports" / "replays_bunterrrrr_focus"
OUT_TXT = ROOT / "reports" / "mined_rules.txt"
OUT_CSV = ROOT / "reports" / "mined_rules.csv"

FACTORY = 0
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}
FEATURES = [
    "step", "factory_gap", "factory_energy", "factory_jump_cd",
    "factory_build_cd", "factory_move_cd", "support_count",
    "scout_count", "miner_count", "worker_count", "support_energy",
    "enemy_support_count", "enemy_factory_min_dist",
    "adj_north_mining_node", "adj_north_own_mine",
    "adj_side_mining_node", "wall_north_blocked", "north_remaining",
]


def iter_replays():
    for d in sorted(TC.glob("*/replays/")):
        m = re.match(r"^(\d+)_", d.parent.name)
        if not m or not (2 <= int(m.group(1)) <= 15):
            continue
        prof = d.parent / "profile.md"
        team = None
        if prof.exists():
            for ln in prof.read_text().splitlines()[:3]:
                mm = re.match(r"^#\s*Rank\s*\d+:\s*(.+?)\s*$", ln)
                if mm:
                    team = mm.group(1).strip(); break
        if team:
            for fp in sorted(d.glob("episode-*-replay.json")):
                yield fp, team
    if BUNTER.exists():
        for fp in sorted(BUNTER.glob("episode-*-replay.json")):
            yield fp, "bunterrrrr"


def parse_pos(d):
    out = set()
    for k in d or {}:
        a, b = k.split(",")
        out.add((int(a), int(b)))
    return out


def own_mines(mines, player):
    out = set()
    for k, v in (mines or {}).items():
        if len(v) >= 3 and v[2] == player:
            a, b = k.split(",")
            out.add((int(a), int(b)))
    return out


def extract(step_state, owner, width):
    rec = step_state[owner]
    obs = rec.get("observation") or {}
    if not obs:
        return None
    robots = obs.get("globalRobots") or obs.get("robots") or {}
    fac, fac_uid = None, None
    for uid, r in robots.items():
        if r[0] == FACTORY and r[4] == owner:
            fac, fac_uid = r, uid; break
    if fac is None:
        return None
    label = (rec.get("action") or {}).get(fac_uid)
    if not label:
        return None
    fc, fr, fe = fac[1], fac[2], fac[3]
    fmove_cd = fac[5] if len(fac) > 5 else 0
    fjump_cd = fac[6] if len(fac) > 6 else 0
    fbuild_cd = fac[7] if len(fac) > 7 else 0
    south = obs.get("southBound", 0)
    north = obs.get("northBound", 0)
    own = [r for r in robots.values() if r[4] == owner]
    enemy = [r for r in robots.values() if r[4] != owner]
    sup = [r for r in own if r[0] != FACTORY]
    enemy_sup = [r for r in enemy if r[0] != FACTORY]
    enemy_fac = [r for r in enemy if r[0] == FACTORY]
    enemy_min = min((abs(r[1]-fc)+abs(r[2]-fr) for r in enemy_fac), default=99)
    mn = parse_pos(obs.get("miningNodes"))
    om = own_mines(obs.get("mines"), owner)
    walls = obs.get("walls") or []
    idx = (fr - south) * width + fc
    w_here = walls[idx] if 0 <= idx < len(walls) and walls[idx] != -1 else 0
    return {
        "step": obs.get("step", 0),
        "factory_gap": fr - south,
        "factory_energy": fe,
        "factory_jump_cd": fjump_cd,
        "factory_build_cd": fbuild_cd,
        "factory_move_cd": fmove_cd,
        "support_count": len(sup),
        "scout_count": sum(1 for r in sup if r[0] == 1),
        "worker_count": sum(1 for r in sup if r[0] == 2),
        "miner_count": sum(1 for r in sup if r[0] == 3),
        "support_energy": sum(r[3] for r in sup),
        "enemy_support_count": len(enemy_sup),
        "enemy_factory_min_dist": enemy_min,
        "adj_north_mining_node": int((fc, fr+1) in mn),
        "adj_north_own_mine": int((fc, fr+1) in om),
        "adj_side_mining_node": int((fc+1, fr) in mn or (fc-1, fr) in mn),
        "wall_north_blocked": int(bool(w_here & WALL_BITS["NORTH"])),
        "north_remaining": north - fr,
        "__label__": label, "__team__": "",
    }


def build_df():
    rows, n = [], 0
    for path, team in iter_replays():
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        n += 1
        info = data.get("info", {})
        names = info.get("TeamNames") or [a.get("Name") for a in info.get("Agents", [])]
        owners = [i for i, x in enumerate(names) if x == team]
        if not owners:
            continue
        owner = owners[0]
        width = (data.get("configuration") or {}).get("width", 22)
        for st in data.get("steps") or []:
            if owner >= len(st):
                continue
            r = extract(st, owner, width)
            if r is None:
                continue
            r["__team__"] = team
            rows.append(r)
    df = pd.DataFrame(rows)
    print(f"replays={n} rows={len(df)} labels={df['__label__'].nunique() if len(df) else 0}")
    return df


def leaves(clf, classes):
    t = clf.tree_
    out = []
    def go(node, conds):
        if t.feature[node] != _tree.TREE_UNDEFINED:
            f, thr = FEATURES[t.feature[node]], t.threshold[node]
            go(t.children_left[node],  conds + [f"{f} <= {thr:.2f}"])
            go(t.children_right[node], conds + [f"{f} > {thr:.2f}"])
            return
        # In sklearn 1.6+, tree_.value is normalized proportions; combine with n_node_samples for counts.
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


def main():
    df = build_df()
    if df.empty:
        print("no rows"); return
    print("top labels:", Counter(df["__label__"]).most_common(10))
    X = df[FEATURES].astype(float).values
    clf = DecisionTreeClassifier(max_depth=4, min_samples_leaf=20, random_state=0).fit(X, df["__label__"].values)
    rules = leaves(clf, list(clf.classes_))
    high = sum(1 for r in rules if r["precision"] >= 0.6)
    with OUT_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rules[0].keys()))
        w.writeheader(); w.writerows(rules)
    with OUT_TXT.open("w") as fh:
        fh.write(f"# Mined factory action rules (depth=4, min_samples_leaf=20)\n")
        fh.write(f"# total_rows={len(df)} leaves={len(rules)} precision>=0.6={high}\n")
        fh.write(f"# top labels: {Counter(df['__label__']).most_common(10)}\n\n")
        for i, r in enumerate(rules):
            fh.write(
                f"[L{i:02d}] precision={r['precision']:.3f} n={r['n_samples']:5d} "
                f"-> {r['majority_action']}\n      IF {r['conds']}\n"
                f"      runner-up: {r['second_action']} ({r['second_share']:.3f})\n\n"
            )
    print(f"wrote {OUT_TXT} ({len(rules)} leaves, {high} >=0.6)")


if __name__ == "__main__":
    main()
