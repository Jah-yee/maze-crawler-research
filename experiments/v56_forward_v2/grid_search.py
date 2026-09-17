#!/usr/bin/env python3
"""Coarse grid search over v56 cost weights via env vars.

Each combo is evaluated on 20 paired games (40 matches) vs v37.
Top combos are then re-evaluated on 80 paired games (160 matches).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAIRED = str(REPO / "scripts/paired_eval_sides.py")
A = str(REPO / "experiments/v56_forward_v2/main.py")
B = str(REPO / "experiments/v37_late_save_jump_no_scout/main.py")
PY = str(REPO / ".venv/bin/python")


def evaluate(weights: dict, seeds: int, start_seed: int = 0, workers: int = 6):
    env = os.environ.copy()
    for k, v in weights.items():
        env[f"V56_{k}"] = str(v)
    cmd = [
        PY, PAIRED,
        "--a", A, "--b", B,
        "--seeds", str(seeds),
        "--start-seed", str(start_seed),
        "--workers", str(workers),
        "--label", "grid",
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    # Parse last line: "grid: A 1-39-0 (W-L-D over 40) | winrate ... | z=+X.YZ [...]"
    line = result.stdout.strip().split("\n")[-1]
    try:
        z_field = line.split("z=")[1].split(" ")[0]
        z = float(z_field)
    except Exception:
        z = float("nan")
    wld_field = line.split("A ")[1].split(" ")[0]
    return z, wld_field, line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coarse-seeds", type=int, default=20)
    ap.add_argument("--fine-seeds", type=int, default=80)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    # Coarse grid (small to keep runtime down).
    W_NORTH_VALS = [3, 5, 8]
    W_CD_LOCK_VALS = [0.02, 0.05, 0.15]
    W_MINE_VALS = [3, 8]
    W_COLLISION_VALS = [100]
    grid = []
    for wn in W_NORTH_VALS:
        for wc in W_CD_LOCK_VALS:
            for wm in W_MINE_VALS:
                for wcol in W_COLLISION_VALS:
                    grid.append({
                        "W_NORTH": wn,
                        "W_CD_LOCK": wc,
                        "W_MINE": wm,
                        "W_COLLISION": wcol,
                    })
    print(f"=== coarse grid: {len(grid)} combos x {args.coarse_seeds*2} games ===", flush=True)
    results = []
    for i, w in enumerate(grid):
        z, wld, line = evaluate(w, args.coarse_seeds, workers=args.workers)
        results.append((z, wld, w, line))
        print(f"[{i+1:2d}/{len(grid)}] {w} -> z={z:+.2f} {wld}", flush=True)
    results.sort(key=lambda x: -x[0])
    print(f"\n=== top {args.top_k} coarse ===")
    for z, wld, w, _ in results[:args.top_k]:
        print(f"  z={z:+.2f} {wld} :: {w}")

    print(f"\n=== fine eval: top {args.top_k} x {args.fine_seeds*2} games ===", flush=True)
    fine = []
    for z, wld, w, _ in results[:args.top_k]:
        zf, wldf, _ = evaluate(w, args.fine_seeds, workers=args.workers)
        fine.append((zf, wldf, w))
        print(f"  z={zf:+.2f} {wldf} :: {w}", flush=True)
    fine.sort(key=lambda x: -x[0])
    print(f"\n=== best fine ===")
    for z, wld, w in fine:
        print(f"  z={z:+.2f} {wld} :: {w}")


if __name__ == "__main__":
    main()
