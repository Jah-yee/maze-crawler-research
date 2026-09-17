#!/usr/bin/env python3
"""Summarize a Kaggle Crawl replay JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def factory_state(agent_step: dict) -> tuple[int, int, int] | None:
    obs = agent_step.get("observation") or {}
    player = obs.get("player")
    for robot in (obs.get("robots") or {}).values():
        if robot[0] == 0 and robot[4] == player:
            return robot[1], robot[2], robot[3]
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()

    data = json.loads(args.replay.read_text())
    info = data.get("info", {})
    names = info.get("TeamNames") or [a.get("Name") for a in info.get("Agents", [])]
    rewards = data.get("rewards")
    statuses = data.get("statuses")
    steps = data.get("steps", [])

    print(f"episode={info.get('EpisodeId')} seed={data.get('configuration', {}).get('seed')}")
    print(f"teams={names}")
    print(f"rewards={rewards} statuses={statuses} steps={len(steps)}")
    if not steps:
        return

    for idx in range(len(steps[-1])):
        last = steps[-1][idx]
        obs = last.get("observation") or {}
        print(
            f"agent[{idx}] player={obs.get('player')} "
            f"last_factory={factory_state(last)} "
            f"south={obs.get('southBound')} north={obs.get('northBound')} "
            f"remaining={obs.get('remainingOverageTime')}"
        )

    for idx in range(len(steps[-1])):
        death_step = None
        for step_idx, step in enumerate(steps):
            if factory_state(step[idx]) is None:
                death_step = step_idx
                break
        print(f"agent[{idx}] factory_missing_from_step={death_step}")


if __name__ == "__main__":
    main()
