#!/usr/bin/env python3
"""Combo evaluation harness.

Runs paired_eval (swap-sides) for:
  1. each --combos agent vs --baseline
  2. each unordered pair within --combos (round-robin)

Sorts the vs-baseline table by z-score (desc) and tags a decision per agent.

Usage:
  .venv/bin/python scripts/combo_eval.py \
    --combos experiments/v44b_transfer_only/main.py,experiments/v46_defense_bundle/main.py \
    --baseline experiments/v37_late_save_jump_no_scout/main.py \
    --seeds 40
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paired_eval import run  # noqa: E402  (sibling script in scripts/)


def _decision(z: float) -> str:
    if z >= 1.5:
        return "PASS (强正)"
    if z >= 1.0:
        return "KEEP (中正)"
    if z >= 0.3:
        return "KEEP (弱正)"
    if z >= -0.3:
        return "KEEP (中性)"
    if z >= -1.0:
        return "WATCH (弱负)"
    return "DROP (负)"


def _short(path: str) -> str:
    p = Path(path)
    return p.parent.name or p.stem


def _print_table(rows: list[dict]) -> None:
    rows.sort(key=lambda r: r["z"], reverse=True)
    print("\n=== Round-robin vs baseline ===")
    print(f"{'agent':<32} {'W-L-D':<14} {'z':>7}  {'draw':>6}  decision")
    print("-" * 78)
    for r in rows:
        wld = f"{r['w']}-{r['l']}-{r['d']}"
        print(
            f"{r['name']:<32} {wld:<14} {r['z']:+6.2f}  "
            f"{r['draw_rate']*100:5.1f}%  {_decision(r['z'])}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combos", required=True, help="comma-separated agent paths")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--seeds", type=int, default=40,
                    help="seeds per pair; games = seeds*2 (swap sides)")
    ap.add_argument("--start-seed", type=int, default=1)
    ap.add_argument("--skip-pairs", action="store_true", help="only vs baseline")
    args = ap.parse_args()

    combos = [c.strip() for c in args.combos.split(",") if c.strip()]
    if not combos:
        raise SystemExit("--combos is empty")
    for p in combos + [args.baseline]:
        if not Path(p).is_file():
            raise SystemExit(f"missing agent file: {p}")

    rows = []
    for c in combos:
        name = _short(c)
        print(f"[combo_eval] {name} vs baseline ({args.seeds} seeds) ...", flush=True)
        r = run(c, args.baseline, args.seeds, args.start_seed)
        r["name"] = name
        rows.append(r)
    _print_table(rows)

    if args.skip_pairs or len(combos) < 2:
        return

    print("\n=== Round-robin (each pair) ===")
    for a, b in itertools.combinations(combos, 2):
        na, nb = _short(a), _short(b)
        print(f"[combo_eval] {na} vs {nb} ({args.seeds} seeds) ...", flush=True)
        r = run(a, b, args.seeds, args.start_seed)
        print(
            f"{na} vs {nb}: {r['w']}-{r['l']}-{r['d']} | z={r['z']:+.2f} | "
            f"draw {r['draw_rate']*100:.1f}% | reward {r['a_mean']:.0f}/{r['b_mean']:.0f}"
        )


if __name__ == "__main__":
    main()
