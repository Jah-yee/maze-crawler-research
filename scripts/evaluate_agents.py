#!/usr/bin/env python3
"""Run lightweight local Crawl agent comparisons."""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

logging.basicConfig(level=logging.ERROR)

from kaggle_environments import make  # noqa: E402


def play(agent_a: str, agent_b: str, seed: int) -> dict[str, object]:
    env = make("crawl", configuration={"seed": seed}, debug=True)
    env.run([agent_a, agent_b])
    final = env.steps[-1]
    reward_a = final[0].reward
    reward_b = final[1].reward
    if reward_a > reward_b:
        winner = 0
    elif reward_b > reward_a:
        winner = 1
    else:
        winner = -1
    return {
        "seed": seed,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "reward_a": reward_a,
        "reward_b": reward_b,
        "status_a": final[0].status,
        "status_b": final[1].status,
        "winner": winner,
        "steps": len(env.steps),
    }


def summarize(rows: list[dict[str, object]]) -> None:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["agent_a"]), str(row["agent_b"])), []).append(row)

    for (agent_a, agent_b), group in sorted(grouped.items()):
        wins_a = sum(1 for r in group if r["winner"] == 0)
        wins_b = sum(1 for r in group if r["winner"] == 1)
        draws = sum(1 for r in group if r["winner"] == -1)
        avg_a = sum(float(r["reward_a"]) for r in group) / len(group)
        avg_b = sum(float(r["reward_b"]) for r in group) / len(group)
        print(
            f"{Path(agent_a).parent.name} vs {Path(agent_b).parent.name}: "
            f"{wins_a}-{wins_b}-{draws}, avg_reward={avg_a:.1f}/{avg_b:.1f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", nargs="+", required=True)
    parser.add_argument("--opponent", default="random")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=1)
    parser.add_argument("--swap-sides", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    seeds = range(args.start_seed, args.start_seed + args.seeds)
    for agent in args.agents:
        for seed in seeds:
            rows.append(play(agent, args.opponent, seed))
            if args.swap_sides and args.opponent != "random":
                rows.append(play(args.opponent, agent, seed))

    summarize(rows)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
