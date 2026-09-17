#!/usr/bin/env python3
"""Collect local paired Crawl replays as JSON for probe analysis."""
from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path

logging.disable(logging.INFO)

from kaggle_environments import make  # noqa: E402


def play(a: str, b: str, seed: int, a_is_p0: bool, out_dir: Path) -> dict:
    agents = [a, b] if a_is_p0 else [b, a]
    env = make("crawl", configuration={"seed": seed}, debug=False)
    env.run(agents)
    data = env.toJSON()
    side = "a_p0" if a_is_p0 else "a_p1"
    path = out_dir / f"local-seed{seed:04d}-{side}-replay.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r0, r1 = env.steps[-1][0].reward, env.steps[-1][1].reward
    ra, rb = (r0, r1) if a_is_p0 else (r1, r0)
    return {
        "seed": seed,
        "a_is_p0": int(a_is_p0),
        "replay_path": str(path),
        "reward_a": ra,
        "reward_b": rb,
        "reward_p0": r0,
        "reward_p1": r1,
        "result_a": "win" if ra > rb else ("loss" if rb > ra else "draw"),
        "steps": len(env.steps),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--start-seed", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for seed in range(args.start_seed, args.start_seed + args.seeds):
        rows.append(play(args.a, args.b, seed, True, args.out_dir))
        rows.append(play(args.a, args.b, seed, False, args.out_dir))

    manifest = args.out_dir / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    wins = sum(r["result_a"] == "win" for r in rows)
    losses = sum(r["result_a"] == "loss" for r in rows)
    draws = sum(r["result_a"] == "draw" for r in rows)
    print(f"wrote {len(rows)} replays to {args.out_dir}; A {wins}-{losses}-{draws}; manifest={manifest}")


if __name__ == "__main__":
    main()
