#!/usr/bin/env python3
"""Paired swap-sides evaluation of agent A vs agent B with a significance z-score.

For each seed we play A-as-player0 vs B AND B-as-player0 vs A, then aggregate
results from A's perspective. Reports W-L-D, decisive win-rate, mean reward, and
z = (W - L) / sqrt(W + L)  (sign-test normal approx; the project's >=1.5 gate).

Usage:
  .venv/bin/python scripts/paired_eval.py --a CAND.py --b BASE.py --seeds 50
  .venv/bin/python scripts/paired_eval.py --a CAND.py --b BASE.py --seeds 50 --label "v44 vs v37"
"""
from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

logging.disable(logging.INFO)  # silence kaggle_environments / open_spiel INFO spam

from kaggle_environments import make  # noqa: E402


def _play(p0: str, p1: str, seed: int):
    env = make("crawl", configuration={"seed": seed}, debug=False)
    env.run([p0, p1])
    final = env.steps[-1]
    return final[0].reward, final[1].reward, len(env.steps)


def run(a: str, b: str, seeds: int, start_seed: int):
    w = l = d = 0
    a_reward_sum = 0.0
    b_reward_sum = 0.0
    games = 0
    for seed in range(start_seed, start_seed + seeds):
        for a_is_p0 in (True, False):
            if a_is_p0:
                ra, rb, _ = _play(a, b, seed)
            else:
                rb, ra, _ = _play(b, a, seed)
            a_reward_sum += ra
            b_reward_sum += rb
            games += 1
            if ra > rb:
                w += 1
            elif rb > ra:
                l += 1
            else:
                d += 1
    decisive = w + l
    z = (w - l) / math.sqrt(decisive) if decisive else 0.0
    winrate = w / decisive if decisive else 0.5
    draw_rate = d / games if games else 0.0
    return {
        "games": games, "w": w, "l": l, "d": d,
        "z": z, "winrate": winrate, "draw_rate": draw_rate,
        "a_mean": a_reward_sum / games, "b_mean": b_reward_sum / games,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="candidate agent (perspective)")
    ap.add_argument("--b", required=True, help="baseline agent")
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--start-seed", type=int, default=1)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    r = run(args.a, args.b, args.seeds, args.start_seed)
    label = args.label or f"{Path(args.a).parent.name or args.a} vs {Path(args.b).parent.name or args.b}"
    gate = "PASS z>=1.5" if r["z"] >= 1.5 else ("ok z>=1.0" if r["z"] >= 1.0 else "REJECT")
    print(
        f"{label}: A {r['w']}-{r['l']}-{r['d']} (W-L-D over {r['games']} games) | "
        f"winrate {r['winrate']*100:.1f}% | z={r['z']:+.2f} [{gate}] | "
        f"draw_rate {r['draw_rate']*100:.1f}% | "
        f"reward {r['a_mean']:.0f}/{r['b_mean']:.0f}"
    )


if __name__ == "__main__":
    main()
