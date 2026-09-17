#!/usr/bin/env python3
"""Paired swap-sides evaluation with separate p0/p1 win tallies.

Same protocol as scripts/paired_eval.py (2 games per seed: A as p0 and A as p1)
but also reports first-player vs second-player wins so we can spot the seed-band
side bias that W-Verify flagged.

Uses a multiprocessing pool so 160-game runs finish in roughly one minute on
this box.

Usage:
  .venv/bin/python scripts/paired_eval_sides.py --a CAND.py --b BASE.py --seeds 80
"""
from __future__ import annotations

import argparse
import logging
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

logging.disable(logging.INFO)


def _play_game(args):
    a, b, seed, a_is_p0 = args
    from kaggle_environments import make
    env = make("crawl", configuration={"seed": seed}, debug=False)
    if a_is_p0:
        env.run([a, b])
        r0, r1 = env.steps[-1][0].reward, env.steps[-1][1].reward
        ra, rb = r0, r1
    else:
        env.run([b, a])
        r0, r1 = env.steps[-1][0].reward, env.steps[-1][1].reward
        ra, rb = r1, r0
    if r0 is None:
        r0 = 0
    if r1 is None:
        r1 = 0
    return seed, a_is_p0, ra, rb, r0, r1


def run(a: str, b: str, seeds: int, start_seed: int, workers: int):
    jobs = []
    for seed in range(start_seed, start_seed + seeds):
        jobs.append((a, b, seed, True))
        jobs.append((a, b, seed, False))

    w = l = d = 0
    a_reward_sum = 0.0
    b_reward_sum = 0.0
    p0_wins = p1_wins = side_draws = 0

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_play_game, j) for j in jobs]
        for fut in as_completed(futures):
            seed, a_is_p0, ra, rb, r0, r1 = fut.result()
            a_reward_sum += ra
            b_reward_sum += rb
            if ra > rb:
                w += 1
            elif rb > ra:
                l += 1
            else:
                d += 1
            if r0 > r1:
                p0_wins += 1
            elif r1 > r0:
                p1_wins += 1
            else:
                side_draws += 1

    games = w + l + d
    decisive = w + l
    z = (w - l) / math.sqrt(decisive) if decisive else 0.0
    winrate = w / decisive if decisive else 0.5
    draw_rate = d / games if games else 0.0
    side_decisive = p0_wins + p1_wins
    side_z = (p0_wins - p1_wins) / math.sqrt(side_decisive) if side_decisive else 0.0
    return {
        "games": games, "w": w, "l": l, "d": d,
        "z": z, "winrate": winrate, "draw_rate": draw_rate,
        "a_mean": a_reward_sum / games, "b_mean": b_reward_sum / games,
        "p0_wins": p0_wins, "p1_wins": p1_wins, "side_draws": side_draws,
        "side_z": side_z,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--seeds", type=int, default=80)
    ap.add_argument("--start-seed", type=int, default=0)
    ap.add_argument("--label", default=None)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    r = run(args.a, args.b, args.seeds, args.start_seed, args.workers)
    label = args.label or f"{Path(args.a).parent.name} vs {Path(args.b).parent.name}"
    if r["z"] >= 1.7:
        gate = "PASS z>=1.7"
    elif r["z"] >= 0.5:
        gate = "WEAK z>=0.5"
    elif r["z"] >= -0.5:
        gate = "NEUTRAL"
    else:
        gate = "NEG"
    print(
        f"{label}: A {r['w']}-{r['l']}-{r['d']} (W-L-D over {r['games']}) | "
        f"winrate {r['winrate']*100:.1f}% | z={r['z']:+.2f} [{gate}] | "
        f"draw_rate {r['draw_rate']*100:.1f}% | "
        f"reward {r['a_mean']:.0f}/{r['b_mean']:.0f} | "
        f"p0_wins={r['p0_wins']} p1_wins={r['p1_wins']} side_draws={r['side_draws']} "
        f"side_z={r['side_z']:+.2f}"
    )


if __name__ == "__main__":
    main()
