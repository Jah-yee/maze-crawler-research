#!/usr/bin/env python3
"""Extract detailed BUILD_MINER event context from Maze Crawler replays."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FACTORY = 0
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}


def parse_pos(text: str) -> tuple[int, int]:
    col, row = text.split(",", 1)
    return int(col), int(row)


def factory_for_uid(robots: dict[str, list], uid: str) -> list | None:
    data = robots.get(uid)
    if data and data[0] == FACTORY:
        return data
    return None


def factory_for_owner(robots: dict[str, list], owner: int) -> tuple[str, list] | tuple[None, None]:
    for uid, data in robots.items():
        if data[0] == FACTORY and data[4] == owner:
            return uid, data
    return None, None


def row_for_event(path: Path, team_name: str, step_no: int, agent_index: int, uid: str, action: str) -> dict[str, object]:
    data = json.loads(path.read_text())
    step = data["steps"][step_no][agent_index]
    obs = step.get("observation") or {}
    robots = {str(k): list(v) for k, v in (obs.get("robots") or {}).items()}
    factory = factory_for_uid(robots, uid)
    if factory is None:
        _, factory = factory_for_owner(robots, obs.get("player", agent_index))

    direction = "NORTH" if action == "BUILD_MINER" else action.removeprefix("BUILD_MINER_")
    dc, dr = OFFSETS.get(direction, (0, 0))
    mining_nodes = {parse_pos(k) for k in (obs.get("miningNodes") or {})}
    south = obs.get("southBound")
    north = obs.get("northBound")
    if factory is None:
        factory_col = factory_row = factory_energy = move_cd = jump_cd = build_cd = ""
        target = ("", "")
        gap = ""
        target_visible_mining_node = ""
    else:
        factory_col, factory_row, factory_energy = factory[1], factory[2], factory[3]
        move_cd = factory[5] if len(factory) > 5 else ""
        jump_cd = factory[6] if len(factory) > 6 else ""
        build_cd = factory[7] if len(factory) > 7 else ""
        target = (factory_col + dc, factory_row + dr)
        gap = "" if south is None else factory_row - int(south)
        target_visible_mining_node = target in mining_nodes

    names = data.get("info", {}).get("TeamNames") or [a.get("Name") for a in data.get("info", {}).get("Agents", [])]
    rewards = data.get("rewards") or []
    result = ""
    if len(rewards) == 2:
        result = "win" if rewards[agent_index] > rewards[1 - agent_index] else (
            "loss" if rewards[agent_index] < rewards[1 - agent_index] else "draw"
        )

    return {
        "episode_id": data.get("info", {}).get("EpisodeId") or path.stem,
        "path": str(path),
        "team": team_name,
        "opponent": names[1 - agent_index] if len(names) == 2 else "",
        "team_index": agent_index,
        "result": result,
        "team_reward": rewards[agent_index] if len(rewards) > agent_index else "",
        "opp_reward": rewards[1 - agent_index] if len(rewards) == 2 else "",
        "step": step_no,
        "uid": uid,
        "action": action,
        "direction": direction,
        "factory_col": factory_col,
        "factory_row": factory_row,
        "target_col": target[0],
        "target_row": target[1],
        "factory_energy": factory_energy,
        "factory_gap": gap,
        "move_cd": move_cd,
        "jump_cd": jump_cd,
        "build_cd": build_cd,
        "south": south,
        "north": north,
        "target_visible_mining_node": target_visible_mining_node,
    }


def rows_for_replay(path: Path, team_name: str) -> list[dict[str, object]]:
    data = json.loads(path.read_text())
    names = data.get("info", {}).get("TeamNames") or [a.get("Name") for a in data.get("info", {}).get("Agents", [])]
    if team_name not in names:
        return []
    agent_index = names.index(team_name)
    rows = []
    for step_no, step in enumerate(data.get("steps") or []):
        actions = step[agent_index].get("action") or {}
        for uid, action in actions.items():
            act = str(action)
            if act == "BUILD_MINER" or act.startswith("BUILD_MINER_"):
                rows.append(row_for_event(path, team_name, step_no, agent_index, str(uid), act))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--team-name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for path in sorted(args.replay_dir.glob("episode-*-replay.json")):
        rows.extend(rows_for_replay(path, args.team_name))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "episode_id", "path", "team", "opponent", "team_index", "result", "team_reward", "opp_reward",
        "step", "uid", "action", "direction", "factory_col", "factory_row", "target_col", "target_row",
        "factory_energy", "factory_gap", "move_cd", "jump_cd", "build_cd", "south", "north",
        "target_visible_mining_node",
    ]
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    by_direction: dict[str, int] = {}
    for row in rows:
        direction = str(row["direction"])
        by_direction[direction] = by_direction.get(direction, 0) + 1
    print(f"wrote {args.out} ({len(rows)} rows)")
    print("directions", dict(sorted(by_direction.items())))


if __name__ == "__main__":
    main()
