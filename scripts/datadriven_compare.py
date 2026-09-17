#!/usr/bin/env python3
"""Compare v37 self-play rules against W-Tree top-15 dataset, head-to-head.

For each leaf rule mined from v37 self-play, project the same condition onto
the W-Tree dataset (corrected obs/action pairing) and compute what top-15
players do under that condition. Differences = candidate novel rules.

Outputs:
  reports/datadriven_compare.json  — full per-leaf comparison
  reports/datadriven_rule_diff.md  — markdown table
  reports/datadriven_top5_candidates.md — top 5 patches
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def parse_conds(text: str) -> list[tuple[str, str, float]]:
    """Parse 'feat OP num AND feat OP num ...' into list of (feat, op, val)."""
    out = []
    if "(root)" in text or not text.strip():
        return out
    for part in text.split(" AND "):
        m = re.match(r"^\s*([\w_]+)\s*(<=|>=|>|<|==)\s*(-?\d+(?:\.\d+)?)\s*$", part.strip())
        if not m:
            continue
        out.append((m.group(1), m.group(2), float(m.group(3))))
    return out


def apply_conds(df: pd.DataFrame, conds: list[tuple[str, str, float]]) -> pd.DataFrame:
    sub = df
    for feat, op, val in conds:
        if feat not in sub.columns:
            return sub.iloc[0:0]
        if op == "<=":
            sub = sub[sub[feat] <= val]
        elif op == ">":
            sub = sub[sub[feat] > val]
        elif op == "<":
            sub = sub[sub[feat] < val]
        elif op == ">=":
            sub = sub[sub[feat] >= val]
        elif op == "==":
            sub = sub[sub[feat] == val]
    return sub


def load_rules() -> list[dict]:
    """Read datadriven_rules.csv into structured rule dicts."""
    df = pd.read_csv(REPORTS / "datadriven_rules.csv")
    rules = []
    for _, row in df.iterrows():
        rules.append({
            "leaf": row["leaf"],
            "block": row["block"],
            "conds_text": row["conds"],
            "conds": parse_conds(row["conds"]),
            "majority_action": row["majority_action"],
            "precision": float(row["precision"]),
            "n_samples": int(row["n_samples"]),
            "second_action": row.get("second_action", ""),
            "second_share": float(row.get("second_share", 0.0)),
        })
    return rules


def build_wtree_df() -> pd.DataFrame:
    """Re-build W-Tree dataset with corrected pairing (reuses pipeline helper)."""
    from scripts.datadriven_pipeline import _wtree_dataset  # type: ignore
    return _wtree_dataset()


def annotate_v37_status(row: dict) -> str:
    """Heuristic: tag whether a leaf is already implemented in v37 main.py."""
    conds = " ".join(row["conds_text"].split(" AND "))
    act = row["majority_action"]
    # IDLE leaves with move_cd>1.5 are v37's `elif f_move_cd > 1: IDLE`.
    if act == "IDLE" and "factory_move_cd > 1.50" in conds:
        return "confirmed"
    if act == "IDLE" and "factory_move_cd <= 0.50" in conds and "factory_build_cd <= 9.50" in conds:
        return "confirmed"  # own-mine sit or BFS-returned-IDLE
    if act == "BUILD_MINER_NORTH" and "adj_north_mining_node > 0.50" in conds and "factory_energy > 65" in conds:
        return "confirmed"  # v37's mine_build_action branch
    if act == "BUILD_SCOUT" and "factory_build_cd > 9.50" in conds:
        return "confirmed-equivalent"  # post-build state recorded
    if act.startswith("JUMP_") and "factory_jump_cd > 19" in conds:
        return "confirmed-equivalent"  # jump_cd>19 means just jumped; intent-spam
    if act in ("NORTH", "EAST", "WEST", "SOUTH"):
        return "confirmed"  # v37's BFS produces these moves
    return "uncertain"


def compare_one(rule: dict, df_wt: pd.DataFrame, df_sp: pd.DataFrame) -> dict:
    sp_sub = apply_conds(df_sp, rule["conds"])
    wt_sub = apply_conds(df_wt, rule["conds"])
    sp_n = len(sp_sub)
    wt_n = len(wt_sub)
    sp_top = Counter(sp_sub["__label__"]).most_common(3) if sp_n else []
    wt_top = Counter(wt_sub["__label__"]).most_common(3) if wt_n else []
    sp_act_share = sp_top[0][1] / sp_n if sp_n else 0.0
    wt_act_share = wt_top[0][1] / wt_n if wt_n else 0.0
    sp_act = sp_top[0][0] if sp_top else ""
    wt_act = wt_top[0][0] if wt_top else ""
    return {
        "leaf": rule["leaf"],
        "block": rule["block"],
        "conds": rule["conds_text"],
        "v37_action": rule["majority_action"],
        "v37_precision": rule["precision"],
        "v37_n": rule["n_samples"],
        "sp_sub_n": sp_n,
        "sp_top": sp_top,
        "wt_sub_n": wt_n,
        "wt_top_action": wt_act,
        "wt_top_share": wt_act_share,
        "wt_top3": wt_top,
        "divergent": int(sp_act != wt_act and sp_n > 50 and wt_n > 50),
        "v37_status": annotate_v37_status(rule),
    }


def main() -> None:
    rules = load_rules()
    print(f"loaded {len(rules)} leaves")
    df_sp = pd.read_csv(REPORTS / "datadriven_dataset.csv")
    print(f"self-play rows={len(df_sp)}")
    print("building w-tree dataset (corrected pairing) ...")
    df_wt = build_wtree_df()
    print(f"w-tree rows={len(df_wt)}")

    rows = [compare_one(r, df_wt, df_sp) for r in rules]
    out = REPORTS / "datadriven_compare.json"
    out.write_text(json.dumps(rows, default=str, indent=2))

    # Markdown diff table — split by block, focus on precision>=0.5 leaves.
    md = REPORTS / "datadriven_rule_diff.md"
    with md.open("w") as fh:
        fh.write("# v37 self-play 决策树 vs v37 main.py + W-Tree top-15 数据对比\n\n")
        fh.write(f"> 数据: v37 self-play {len(df_sp):,} rows, W-Tree top-15 {len(df_wt):,} rows (均已修正 obs(t)→action(t+1) 配对)\n")
        fh.write(f"> 树: DecisionTreeClassifier(max_depth=4, min_samples_leaf=50)\n\n")
        fh.write("## W-Tree R1/R2 cross-validation (修正配对后)\n\n")
        cc = json.loads((REPORTS / "datadriven_crosscheck.json").read_text())
        fh.write("| rule | v37 self-play prec/n | W-Tree top-15 prec/n |\n|---|---|---|\n")
        for k in ("L00_IDLE_baseline", "R1_TRANSFER_NORTH_wide", "R2_BUILD_MINER_NORTH"):
            sp = cc["v37_self_play"][k]
            wt = cc["wtree_top15"].get(k.replace("_wide", "").replace("_narrow", ""), {"precision": float("nan"), "support": 0})
            fh.write(f"| {k} | {sp['precision']:.3f} / {sp['support']} | {wt['precision']:.3f} / {wt['support']} |\n")
        fh.write("\n")
        fh.write("**结论**: W-Tree R1 (factory TRANSFER_NORTH) 修正配对后 precision 0.91→0.135, R2 (2nd miner) 0.555→0.000。两条规则原本看起来高 precision 是因为 `env.steps[t].action` 是产生 obs(t) 的动作 (off-by-one), 实际是动作的*后果*而非*触发条件*。\n\n")

        for block in ("A_wins", "ALL", "B_strong", "B_weak"):
            fh.write(f"## block={block}\n\n")
            fh.write("| leaf | v37→action | v37 prec/n | top-15→action | top-15 share/n | v37 vs v37 | div? | 状态 |\n")
            fh.write("|---|---|---|---|---|---|---|---|\n")
            for r in rows:
                if r["block"] != block or r["v37_precision"] < 0.5:
                    continue
                sp_share = (r["sp_top"][0][1] / r["sp_sub_n"]) if r["sp_sub_n"] else 0.0
                sp_act = r["sp_top"][0][0] if r["sp_top"] else "-"
                fh.write(
                    f"| {r['leaf']} | {r['v37_action']} | {r['v37_precision']:.2f}/{r['v37_n']:,} "
                    f"| {r['wt_top_action']} | {r['wt_top_share']:.2f}/{r['wt_sub_n']:,} "
                    f"| {sp_act} {sp_share:.2f} | {'YES' if r['divergent'] else ''} | {r['v37_status']} |\n"
                )
            fh.write("\n")

    print(f"wrote {md}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
