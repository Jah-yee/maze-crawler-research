#!/usr/bin/env python3
"""Classify Maze Crawler replay outcomes from downloaded Kaggle JSON files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FACTORY = 0
OFFSETS = {
    "NORTH": (0, 1),
    "EAST": (1, 0),
    "WEST": (-1, 0),
    "SOUTH": (0, -1),
}


def global_robots(step: list[dict]) -> dict[str, list]:
    for agent_step in step:
        obs = agent_step.get("observation") or {}
        robots = obs.get("globalRobots")
        if robots is not None:
            return {str(uid): list(data) for uid, data in robots.items()}
    obs = step[0].get("observation") or {}
    return {str(uid): list(data) for uid, data in (obs.get("robots") or {}).items()}


def bounds(step: list[dict]) -> tuple[int | None, int | None]:
    obs = step[0].get("observation") or {}
    return obs.get("southBound"), obs.get("northBound")


def factory_for_owner(robots: dict[str, list], owner: int) -> tuple[str, list] | None:
    for uid, data in robots.items():
        if data[0] == FACTORY and data[4] == owner:
            return uid, data
    return None


def support_summary(robots: dict[str, list], owner: int) -> tuple[int, int]:
    energy = 0
    count = 0
    for data in robots.values():
        if data[4] == owner and data[0] != FACTORY:
            energy += int(data[3])
            count += 1
    return energy, count


def rough_dest(robot: list | None, action: str | None) -> tuple[int, int] | None:
    if robot is None:
        return None
    col, row = int(robot[1]), int(robot[2])
    if not action or action == "IDLE":
        return col, row
    if action.startswith("JUMP_"):
        direction = action.split("_", 1)[1]
        dc, dr = OFFSETS.get(direction, (0, 0))
        return col + 2 * dc, row + 2 * dr
    if action in OFFSETS:
        dc, dr = OFFSETS[action]
        return col + dc, row + dr
    return col, row


def classify(data: dict, team_name: str) -> dict[str, object]:
    info = data.get("info", {})
    names = info.get("TeamNames") or [a.get("Name") for a in info.get("Agents", [])]
    steps = data.get("steps") or []
    rewards = data.get("rewards") or []

    our_index = 0
    for idx, name in enumerate(names):
        if name == team_name:
            our_index = idx
            break
    opp_index = 1 - our_index
    owners = {0: 0, 1: 1}

    death_step = None
    for idx, step in enumerate(steps):
        robots = global_robots(step)
        if factory_for_owner(robots, owners[our_index]) is None:
            death_step = idx
            break

    final_robots = global_robots(steps[-1]) if steps else {}
    our_support_energy, our_support_count = support_summary(final_robots, owners[our_index])
    opp_support_energy, opp_support_count = support_summary(final_robots, owners[opp_index])

    winner = "draw"
    if len(rewards) == 2 and rewards[0] != rewards[1]:
        winner = names[0] if rewards[0] > rewards[1] else names[1]
    our_reward = rewards[our_index] if len(rewards) > our_index else ""
    opp_reward = rewards[opp_index] if len(rewards) > opp_index else ""
    if isinstance(our_reward, (int, float)) and isinstance(opp_reward, (int, float)):
        result = "win" if our_reward > opp_reward else ("loss" if our_reward < opp_reward else "draw")
    else:
        result = "win" if winner == team_name else ("draw" if winner == "draw" else "loss")

    cause = "active_or_win"
    prev_our_factory = None
    prev_opp_factory = None
    our_action = ""
    opp_action = ""
    our_dest = None
    opp_dest = None
    south_at_death = None

    if death_step is None:
        if result != "win" and len(steps) >= int((data.get("configuration") or {}).get("episodeSteps", 501)) - 1:
            cause = "timeout_tiebreak"
        elif result != "win":
            cause = "loss_without_factory_death_detected"
    else:
        prev_idx = max(0, death_step - 1)
        prev_robots = global_robots(steps[prev_idx])
        curr_robots = global_robots(steps[death_step])
        south_at_death, _ = bounds(steps[death_step])

        our_prev = factory_for_owner(prev_robots, owners[our_index])
        opp_prev = factory_for_owner(prev_robots, owners[opp_index])
        our_curr = factory_for_owner(curr_robots, owners[our_index])
        opp_curr = factory_for_owner(curr_robots, owners[opp_index])

        if our_prev is not None:
            our_uid, prev_our_factory = our_prev
            our_action = (steps[death_step][our_index].get("action") or {}).get(our_uid, "")
            our_dest = rough_dest(prev_our_factory, our_action)
        if opp_prev is not None:
            opp_uid, prev_opp_factory = opp_prev
            opp_action = (steps[death_step][opp_index].get("action") or {}).get(opp_uid, "")
            opp_dest = rough_dest(prev_opp_factory, opp_action)

        if prev_our_factory is not None and south_at_death is not None and prev_our_factory[2] < south_at_death:
            cause = "boundary_scroll"
        elif our_curr is None and opp_curr is None and our_dest is not None and our_dest == opp_dest:
            cause = "factory_collision"
        elif our_curr is None and opp_curr is None:
            cause = "simultaneous_tiebreak"
        elif our_curr is None:
            cause = "single_factory_death"

    return {
        "episode_id": info.get("EpisodeId") or data.get("id", ""),
        "seed": (data.get("configuration") or {}).get("seed", ""),
        "opponent": names[opp_index] if len(names) > opp_index else "",
        "result": result,
        "our_reward": our_reward,
        "opp_reward": opp_reward,
        "steps": len(steps),
        "death_step": "" if death_step is None else death_step,
        "cause": cause,
        "south_at_death": "" if south_at_death is None else south_at_death,
        "prev_our_factory": prev_our_factory or "",
        "prev_opp_factory": prev_opp_factory or "",
        "our_factory_action": our_action,
        "opp_factory_action": opp_action,
        "our_factory_dest": our_dest or "",
        "opp_factory_dest": opp_dest or "",
        "our_support_energy": our_support_energy,
        "opp_support_energy": opp_support_energy,
        "our_support_count": our_support_count,
        "opp_support_count": opp_support_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--team-name", default="Jiayi Du")
    args = parser.parse_args()

    rows = []
    for path in sorted(args.replay_dir.glob("episode-*-replay.json")):
        rows.append(classify(json.loads(path.read_text()), args.team_name))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for row in rows:
        key = (row["result"], row["cause"])
        counts[key] = counts.get(key, 0) + 1
    for key, count in sorted(counts.items()):
        print(f"{key[0]} {key[1]}: {count}")
    print(f"wrote {args.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
