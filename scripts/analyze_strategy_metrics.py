#!/usr/bin/env python3
"""Extract high-level strategy metrics from Maze Crawler replays."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


FACTORY = 0
SCOUT = 1
WORKER = 2
MINER = 3


def global_robots(step: list[dict]) -> dict[str, list]:
    for agent_step in step:
        obs = agent_step.get("observation") or {}
        robots = obs.get("globalRobots")
        if robots is not None:
            return {str(uid): list(data) for uid, data in robots.items()}
    obs = step[0].get("observation") or {}
    return {str(uid): list(data) for uid, data in (obs.get("robots") or {}).items()}


def global_mines(step: list[dict]) -> dict[str, list]:
    for agent_step in step:
        obs = agent_step.get("observation") or {}
        mines = obs.get("globalMines")
        if mines is not None:
            return {str(pos): list(data) for pos, data in mines.items()}
    return {}


def bounds(step: list[dict]) -> tuple[int, int]:
    obs = step[0].get("observation") or {}
    return int(obs.get("southBound", 0)), int(obs.get("northBound", 0))


def factory_for_owner(robots: dict[str, list], owner: int) -> list | None:
    for data in robots.values():
        if data[0] == FACTORY and data[4] == owner:
            return data
    return None


def robot_summary(robots: dict[str, list], owner: int) -> dict[str, int]:
    counts = Counter()
    support_energy = 0
    for data in robots.values():
        if data[4] != owner:
            continue
        counts[data[0]] += 1
        if data[0] != FACTORY:
            support_energy += int(data[3])
    return {
        "factory_count": counts[FACTORY],
        "scout_count": counts[SCOUT],
        "worker_count": counts[WORKER],
        "miner_count": counts[MINER],
        "support_count": counts[SCOUT] + counts[WORKER] + counts[MINER],
        "support_energy": support_energy,
    }


def mine_summary(mines: dict[str, list], owner: int) -> dict[str, int]:
    owned = [data for data in mines.values() if len(data) >= 3 and data[2] == owner]
    return {"mine_count": len(owned), "mine_energy": sum(int(data[0]) for data in owned)}


def action_metrics(steps: list[list[dict]], agent_index: int) -> dict[str, object]:
    counts = Counter()
    first = {}
    for step_no, step in enumerate(steps):
        actions = step[agent_index].get("action") or {}
        for act in actions.values():
            counts[act] += 1
            head = act.split("_", 1)[0]
            counts[f"{head}_*"] += 1
            if act not in first:
                first[act] = step_no
            if head not in first:
                first[head] = step_no
    return {
        "build_scout": sum(v for k, v in counts.items() if k.startswith("BUILD_SCOUT")),
        "build_worker": sum(v for k, v in counts.items() if k.startswith("BUILD_WORKER")),
        "build_miner": sum(v for k, v in counts.items() if k.startswith("BUILD_MINER")),
        "transform": counts["TRANSFORM"],
        "transfer": counts["TRANSFER_*"],
        "remove_wall": counts["REMOVE_*"],
        "build_wall": sum(v for k, v in counts.items() if k.startswith("BUILD_") and not k.startswith("BUILD_SCOUT") and not k.startswith("BUILD_WORKER") and not k.startswith("BUILD_MINER")),
        "factory_jump": sum(v for k, v in counts.items() if k.startswith("JUMP_")),
        "first_build_scout": min((first[k] for k in first if k.startswith("BUILD_SCOUT")), default=""),
        "first_build_worker": min((first[k] for k in first if k.startswith("BUILD_WORKER")), default=""),
        "first_build_miner": min((first[k] for k in first if k.startswith("BUILD_MINER")), default=""),
        "first_transform": first.get("TRANSFORM", ""),
        "first_transfer": first.get("TRANSFER", ""),
        "top_actions": ";".join(f"{k}:{v}" for k, v in counts.most_common(12) if not k.endswith("_*")),
    }


def row_for_replay(path: Path, team_name: str) -> dict[str, object]:
    data = json.loads(path.read_text())
    names = data.get("info", {}).get("TeamNames") or [a.get("Name") for a in data.get("info", {}).get("Agents", [])]
    team_index = names.index(team_name)
    opp_index = 1 - team_index
    steps = data.get("steps") or []
    rewards = data.get("rewards") or []

    final_robots = global_robots(steps[-1])
    final_mines = global_mines(steps[-1])
    team_factory = factory_for_owner(final_robots, team_index)
    opp_factory = factory_for_owner(final_robots, opp_index)
    team_summary = robot_summary(final_robots, team_index)
    opp_summary = robot_summary(final_robots, opp_index)
    team_mines = mine_summary(final_mines, team_index)
    opp_mines = mine_summary(final_mines, opp_index)

    max_factory_energy = 0
    max_gap = 0
    min_gap_after_scroll = 999
    max_mines = 0
    rows_at = {}
    for step_no, step in enumerate(steps):
        robots = global_robots(step)
        mines = global_mines(step)
        factory = factory_for_owner(robots, team_index)
        south, _ = bounds(step)
        if factory is not None:
            max_factory_energy = max(max_factory_energy, int(factory[3]))
            gap = int(factory[2]) - south
            max_gap = max(max_gap, gap)
            if south > 0:
                min_gap_after_scroll = min(min_gap_after_scroll, gap)
            if step_no in (50, 100, 150, 200, 300, 400):
                rows_at[f"row_{step_no}"] = int(factory[2])
                rows_at[f"gap_{step_no}"] = gap
                rows_at[f"energy_{step_no}"] = int(factory[3])
        max_mines = max(max_mines, mine_summary(mines, team_index)["mine_count"])

    result = "draw"
    if len(rewards) == 2:
        if rewards[team_index] > rewards[opp_index]:
            result = "win"
        elif rewards[team_index] < rewards[opp_index]:
            result = "loss"

    row = {
        "episode_id": data.get("info", {}).get("EpisodeId") or path.stem,
        "seed": (data.get("configuration") or {}).get("seed", ""),
        "teams": "|".join(names),
        "team_index": team_index,
        "opponent": names[opp_index],
        "result": result,
        "team_reward": rewards[team_index] if len(rewards) > team_index else "",
        "opp_reward": rewards[opp_index] if len(rewards) > opp_index else "",
        "steps": len(steps),
        "final_factory_row": "" if team_factory is None else team_factory[2],
        "final_factory_energy": "" if team_factory is None else team_factory[3],
        "opp_final_factory_row": "" if opp_factory is None else opp_factory[2],
        "opp_final_factory_energy": "" if opp_factory is None else opp_factory[3],
        "max_factory_energy": max_factory_energy,
        "max_gap": max_gap,
        "min_gap_after_scroll": "" if min_gap_after_scroll == 999 else min_gap_after_scroll,
        "max_mines": max_mines,
        **{f"final_{k}": v for k, v in team_summary.items()},
        **{f"opp_final_{k}": v for k, v in opp_summary.items()},
        **{f"final_{k}": v for k, v in team_mines.items()},
        **{f"opp_final_{k}": v for k, v in opp_mines.items()},
        **action_metrics(steps, team_index),
        **rows_at,
        "replay_path": str(path),
    }
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--team-name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = [row_for_replay(path, args.team_name) for path in sorted(args.replay_dir.glob("episode-*-replay.json"))]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
