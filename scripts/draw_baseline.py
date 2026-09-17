#!/usr/bin/env python3
"""Self-play draw-rate baseline runner.

Plays N seeds × 2 swap-sides between two identical agent paths and prints a CSV
row: seeds, games, wins_p0, wins_p1, draws, draw_rate.

Usage:
  .venv/bin/python scripts/draw_baseline.py --agent path/to/main.py --seeds 50 \
      --start-seed 300 --out reports/v37_self_draw_baseline.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

logging.disable(logging.INFO)

from kaggle_environments import make  # noqa: E402


def _play(p0: str, p1: str, seed: int):
    env = make("crawl", configuration={"seed": seed}, debug=False)
    env.run([p0, p1])
    final = env.steps[-1]
    return final[0].reward, final[1].reward


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--start-seed", type=int, default=300)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    wins_p0 = wins_p1 = draws = 0
    games = 0
    seed_lo = args.start_seed
    seed_hi = args.start_seed + args.seeds - 1
    for seed in range(args.start_seed, args.start_seed + args.seeds):
        for _swap in (False, True):
            r0, r1 = _play(args.agent, args.agent, seed)
            games += 1
            if r0 > r1:
                wins_p0 += 1
            elif r1 > r0:
                wins_p1 += 1
            else:
                draws += 1

    draw_rate = draws / games if games else 0.0
    seeds_label = f"{seed_lo}-{seed_hi}"

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seeds", "games", "wins_p0", "wins_p1", "draws", "draw_rate"])
        w.writerow([seeds_label, games, wins_p0, wins_p1, draws, f"{draw_rate:.4f}"])

    print(f"agent={args.agent} seeds={seeds_label} games={games} "
          f"p0={wins_p0} p1={wins_p1} draws={draws} draw_rate={draw_rate*100:.1f}%")


if __name__ == "__main__":
    main()
