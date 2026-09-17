#!/usr/bin/env python3
"""Read-only reservation/intent probe for Crawl replays.

This script focuses on one-turn action ownership signals that are hard to see
from aggregate strategy metrics: factory destination conflicts, friendly
blockers that do or do not vacate, edge swaps, and build/transform reservation
side effects.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
TYPE_NAME = {FACTORY: "factory", SCOUT: "scout", WORKER: "worker", MINER: "miner"}
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}


STEP_FIELDS = [
    "source_group", "agent_label", "team_name", "team_index", "episode_id", "seed", "replay_path",
    "step_idx", "result", "team_reward", "opp_reward", "death_next_step", "death_cause",
    "factory_alive", "factory_uid", "factory_col", "factory_row", "factory_gap", "factory_energy",
    "factory_action", "factory_action_dest_col", "factory_action_dest_row",
    "factory_dest_occupied_by_friendly", "factory_dest_occupant_uid", "factory_dest_occupant_type",
    "factory_dest_occupant_action", "factory_dest_occupant_dest_col", "factory_dest_occupant_dest_row",
    "factory_dest_occupant_vacates", "factory_dest_occupant_transforms",
    "factory_dest_occupant_sacrificed", "friendly_vertex_conflict_t1", "friendly_edge_swap_t1",
    "friendly_conflict_uids", "enemy_vertex_conflict_t1", "enemy_edge_swap_t1",
    "support_into_factory_dest_count", "support_into_factory_dest_uids", "build_action_count",
    "build_spawn_conflict_count", "build_spawn_conflict_uids", "transform_count",
    "transform_on_factory_dest", "reserved_next_count", "reserved_next_conflict_count",
    "north_blocker_uid", "north_blocker_type", "north_blocker_action", "north_blocker_vacates",
    "jump_landing_occupied", "jump_landing_occupant_type", "labels",
]

EPISODE_FIELDS = [
    "source_group", "agent_label", "team_name", "team_index", "episode_id", "seed", "result",
    "team_reward", "opp_reward", "steps", "death_step", "death_cause",
    "factory_dest_occupied_rows", "friendly_vertex_conflict_rows", "friendly_edge_swap_rows",
    "enemy_vertex_conflict_rows", "enemy_edge_swap_rows", "support_into_factory_dest_rows",
    "build_spawn_conflict_rows", "north_blocker_rows", "north_blocker_not_vacate_rows",
    "transform_on_factory_dest_rows", "death_next_conflict_rows", "top_labels", "replay_path",
]


def parse_pos(text: str) -> tuple[int, int]:
    col, row = str(text).split(",", 1)
    return int(col), int(row)


def names_for(data: dict[str, Any]) -> list[str]:
    info = data.get("info", {})
    return info.get("TeamNames") or [a.get("Name", "") for a in info.get("Agents", [])]


def obs_for(step: list[dict[str, Any]], agent_index: int) -> dict[str, Any]:
    if 0 <= agent_index < len(step):
        return step[agent_index].get("observation") or {}
    return {}


def action_for(step: list[dict[str, Any]], agent_index: int) -> dict[str, str]:
    if 0 <= agent_index < len(step):
        return {str(k): str(v) for k, v in (step[agent_index].get("action") or {}).items()}
    return {}


def global_obs(step: list[dict[str, Any]]) -> dict[str, Any]:
    for agent_step in step:
        obs = agent_step.get("observation") or {}
        if obs.get("globalRobots") is not None:
            return obs
    return obs_for(step, 0)


def global_robots(step: list[dict[str, Any]]) -> dict[str, list[Any]]:
    obs = global_obs(step)
    robots = obs.get("globalRobots")
    if robots is None:
        robots = obs.get("robots") or {}
    return {str(uid): list(data) for uid, data in robots.items()}


def global_walls(step: list[dict[str, Any]]) -> dict[str, list[int]]:
    walls = global_obs(step).get("globalWalls") or {}
    return {str(row): list(vals) for row, vals in walls.items()}


def global_bounds(step: list[dict[str, Any]]) -> tuple[int, int]:
    obs = global_obs(step)
    return int(obs.get("southBound", 0)), int(obs.get("northBound", 0))


def factory_for_owner(robots: dict[str, list[Any]], owner: int) -> tuple[str, list[Any]] | tuple[None, None]:
    for uid, robot in robots.items():
        if int(robot[0]) == FACTORY and int(robot[4]) == owner:
            return uid, robot
    return None, None


def result_for(rewards: list[Any], team_index: int) -> tuple[str, Any, Any]:
    if len(rewards) < 2:
        return "", "", ""
    team_reward = rewards[team_index]
    opp_reward = rewards[1 - team_index]
    if team_reward is None or opp_reward is None:
        return "unknown", team_reward, opp_reward
    if team_reward > opp_reward:
        return "win", team_reward, opp_reward
    if team_reward < opp_reward:
        return "loss", team_reward, opp_reward
    return "draw", team_reward, opp_reward


def action_dir(action: str) -> str:
    if action in OFFSETS:
        return action
    if "_" in action:
        tail = action.rsplit("_", 1)[1]
        if tail in OFFSETS:
            return tail
    return ""


def action_dest(col: int, row: int, action: str) -> tuple[int, int]:
    if action.startswith("JUMP_"):
        direction = action.split("_", 1)[1]
        dc, dr = OFFSETS.get(direction, (0, 0))
        return col + 2 * dc, row + 2 * dr
    if action in OFFSETS:
        dc, dr = OFFSETS[action]
        return col + dc, row + dr
    if action.startswith("BUILD_"):
        direction = action_dir(action) or "NORTH"
        dc, dr = OFFSETS.get(direction, (0, 1))
        return col + dc, row + dr
    return col, row


def action_origin_dest(uid: str, robot: list[Any], action: str) -> tuple[tuple[int, int], tuple[int, int]]:
    pos = (int(robot[1]), int(robot[2]))
    return pos, action_dest(pos[0], pos[1], action)


def compact(counter: Counter[str]) -> str:
    return ";".join(f"{k}:{counter[k]}" for k in sorted(counter))


def death_info(data: dict[str, Any], team_index: int) -> tuple[int | None, str]:
    prev_alive = True
    for idx, step in enumerate(data.get("steps") or []):
        robots = global_robots(step)
        _, factory = factory_for_owner(robots, team_index)
        alive = factory is not None
        if prev_alive and not alive:
            if idx > 0:
                prev = data["steps"][idx - 1]
                south, _ = global_bounds(prev)
                prev_robots = global_robots(prev)
                _, prev_factory = factory_for_owner(prev_robots, team_index)
                if prev_factory is not None and int(prev_factory[2]) - south <= 0:
                    return idx, "boundary_scroll"
                return idx, "factory_collision"
            return idx, "single_factory_death"
        prev_alive = alive
    rewards = data.get("rewards") or []
    if len(rewards) >= 2 and rewards[team_index] == rewards[1 - team_index]:
        return None, "timeout_tiebreak"
    return None, "active_or_win"


def load_episode_team_indices(path: Path | None) -> dict[str, int]:
    if path is None:
        return {}
    out = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            episode_id = str(row.get("id") or row.get("episode_id") or "")
            team_index = row.get("team_index")
            if episode_id and team_index not in (None, ""):
                out[episode_id] = int(team_index)
    return out


def team_indices(args: argparse.Namespace, data: dict[str, Any]) -> list[int]:
    episode_id = str(data.get("info", {}).get("EpisodeId") or "")
    if getattr(args, "episode_team_indices", None) and episode_id in args.episode_team_indices:
        return [args.episode_team_indices[episode_id]]
    if args.all_sides:
        return [0, 1]
    if args.team_index is not None:
        return [int(args.team_index)]
    names = names_for(data)
    if args.team_name:
        return [names.index(args.team_name)] if args.team_name in names else []
    return [0]


def row_for_step(
    data: dict[str, Any],
    path: Path,
    args: argparse.Namespace,
    team_index: int,
    step_idx: int,
    death_step: int | None,
    death_cause: str,
) -> dict[str, Any] | None:
    steps = data.get("steps") or []
    step = steps[step_idx]
    next_step = steps[step_idx + 1]
    robots = global_robots(step)
    factory_uid, factory = factory_for_owner(robots, team_index)
    if factory is None:
        return None
    names = names_for(data)
    rewards = data.get("rewards") or []
    result, team_reward, opp_reward = result_for(rewards, team_index)
    south, _ = global_bounds(step)
    gobs = global_obs(step)
    actions = action_for(next_step, team_index)
    opp_actions = action_for(next_step, 1 - team_index)

    factory_col, factory_row = int(factory[1]), int(factory[2])
    factory_action = actions.get(str(factory_uid), "IDLE")
    factory_dest = action_dest(factory_col, factory_row, factory_action)

    own_positions = {
        (int(robot[1]), int(robot[2])): uid
        for uid, robot in robots.items()
        if int(robot[4]) == team_index
    }
    enemy_positions = {
        (int(robot[1]), int(robot[2])): uid
        for uid, robot in robots.items()
        if int(robot[4]) == 1 - team_index
    }

    own_moves = {}
    for uid, robot in robots.items():
        if int(robot[4]) != team_index:
            continue
        action = actions.get(uid, "IDLE")
        own_moves[uid] = (*action_origin_dest(uid, robot, action), action)
    enemy_moves = {}
    for uid, robot in robots.items():
        if int(robot[4]) != 1 - team_index:
            continue
        action = opp_actions.get(uid, "IDLE")
        enemy_moves[uid] = (*action_origin_dest(uid, robot, action), action)

    factory_dest_uid = own_positions.get(factory_dest, "")
    dest_occupant = robots.get(factory_dest_uid) if factory_dest_uid else None
    dest_occupant_action = actions.get(factory_dest_uid, "") if factory_dest_uid else ""
    dest_occupant_dest = ("", "")
    if dest_occupant is not None:
        dest_occupant_dest = action_dest(int(dest_occupant[1]), int(dest_occupant[2]), dest_occupant_action)
    dest_vacates = int(bool(factory_dest_uid) and dest_occupant_dest != factory_dest)
    dest_transforms = int(bool(factory_dest_uid) and dest_occupant_action == "TRANSFORM")
    dest_sacrificed = int(bool(factory_dest_uid) and not dest_vacates and not dest_transforms and factory_dest != (factory_col, factory_row))

    friendly_vertex_conflict_uids = []
    support_into_factory_dest_uids = []
    friendly_edge_swaps = 0
    reserved_targets = Counter()
    for uid, (origin, dest, action) in own_moves.items():
        reserved_targets[dest] += 1
        if uid == str(factory_uid):
            continue
        if dest == factory_dest:
            friendly_vertex_conflict_uids.append(uid)
            support_into_factory_dest_uids.append(uid)
        if dest == (factory_col, factory_row) and origin == factory_dest:
            friendly_edge_swaps += 1

    enemy_vertex_conflict = 0
    enemy_edge_swap = 0
    for _, (origin, dest, _) in enemy_moves.items():
        if dest == factory_dest:
            enemy_vertex_conflict += 1
        if dest == (factory_col, factory_row) and origin == factory_dest:
            enemy_edge_swap += 1

    build_spawn_conflict_uids = []
    build_count = 0
    transform_count = 0
    transform_on_factory_dest = 0
    for uid, (origin, dest, action) in own_moves.items():
        if action.startswith("BUILD_"):
            build_count += 1
            if dest in own_positions and own_positions[dest] != uid:
                build_spawn_conflict_uids.append(own_positions[dest])
        if action == "TRANSFORM":
            transform_count += 1
            if origin == factory_dest:
                transform_on_factory_dest = 1

    north_cell = (factory_col, factory_row + 1)
    north_uid = own_positions.get(north_cell, "")
    north_robot = robots.get(north_uid) if north_uid else None
    north_action = actions.get(north_uid, "") if north_uid else ""
    north_dest = action_dest(int(north_robot[1]), int(north_robot[2]), north_action) if north_robot else ("", "")
    north_vacates = int(bool(north_uid) and north_dest != north_cell)

    jump_landing = (factory_col, factory_row + 2)
    landing_uid = own_positions.get(jump_landing, "")
    landing_robot = robots.get(landing_uid) if landing_uid else None

    labels = []
    if factory_dest_uid and factory_dest_uid != str(factory_uid):
        labels.append("factory_dest_occupied_by_friendly")
    if friendly_vertex_conflict_uids:
        labels.append("friendly_vertex_conflict_t1")
    if friendly_edge_swaps:
        labels.append("friendly_edge_swap_t1")
    if enemy_vertex_conflict:
        labels.append("enemy_vertex_conflict_t1")
    if enemy_edge_swap:
        labels.append("enemy_edge_swap_t1")
    if build_spawn_conflict_uids:
        labels.append("build_spawn_conflict")
    if north_uid and not north_vacates:
        labels.append("north_blocker_not_vacate")
    if transform_on_factory_dest:
        labels.append("transform_on_factory_dest")
    if reserved_targets and max(reserved_targets.values()) > 1:
        labels.append("reserved_next_conflict")
    if death_step == step_idx + 1 and labels:
        labels.append("death_next_conflict")

    return {
        "source_group": args.group,
        "agent_label": args.agent_label,
        "team_name": names[team_index] if len(names) > team_index else str(team_index),
        "team_index": team_index,
        "episode_id": data.get("info", {}).get("EpisodeId") or path.stem,
        "seed": (data.get("configuration") or {}).get("seed", ""),
        "replay_path": str(path),
        "step_idx": step_idx,
        "result": result,
        "team_reward": team_reward,
        "opp_reward": opp_reward,
        "death_next_step": int(death_step == step_idx + 1),
        "death_cause": death_cause,
        "factory_alive": 1,
        "factory_uid": factory_uid,
        "factory_col": factory_col,
        "factory_row": factory_row,
        "factory_gap": factory_row - south,
        "factory_energy": int(factory[3]),
        "factory_action": factory_action,
        "factory_action_dest_col": factory_dest[0],
        "factory_action_dest_row": factory_dest[1],
        "factory_dest_occupied_by_friendly": int(bool(factory_dest_uid) and factory_dest_uid != str(factory_uid)),
        "factory_dest_occupant_uid": factory_dest_uid,
        "factory_dest_occupant_type": TYPE_NAME.get(int(dest_occupant[0]), "") if dest_occupant is not None else "",
        "factory_dest_occupant_action": dest_occupant_action,
        "factory_dest_occupant_dest_col": dest_occupant_dest[0],
        "factory_dest_occupant_dest_row": dest_occupant_dest[1],
        "factory_dest_occupant_vacates": dest_vacates,
        "factory_dest_occupant_transforms": dest_transforms,
        "factory_dest_occupant_sacrificed": dest_sacrificed,
        "friendly_vertex_conflict_t1": int(bool(friendly_vertex_conflict_uids)),
        "friendly_edge_swap_t1": int(bool(friendly_edge_swaps)),
        "friendly_conflict_uids": ";".join(friendly_vertex_conflict_uids),
        "enemy_vertex_conflict_t1": int(enemy_vertex_conflict > 0),
        "enemy_edge_swap_t1": int(enemy_edge_swap > 0),
        "support_into_factory_dest_count": len(support_into_factory_dest_uids),
        "support_into_factory_dest_uids": ";".join(support_into_factory_dest_uids),
        "build_action_count": build_count,
        "build_spawn_conflict_count": len(build_spawn_conflict_uids),
        "build_spawn_conflict_uids": ";".join(build_spawn_conflict_uids),
        "transform_count": transform_count,
        "transform_on_factory_dest": transform_on_factory_dest,
        "reserved_next_count": len(reserved_targets),
        "reserved_next_conflict_count": sum(1 for count in reserved_targets.values() if count > 1),
        "north_blocker_uid": north_uid,
        "north_blocker_type": TYPE_NAME.get(int(north_robot[0]), "") if north_robot is not None else "",
        "north_blocker_action": north_action,
        "north_blocker_vacates": north_vacates,
        "jump_landing_occupied": int(bool(landing_uid)),
        "jump_landing_occupant_type": TYPE_NAME.get(int(landing_robot[0]), "") if landing_robot is not None else "",
        "labels": ";".join(labels),
    }


def summarize_episode(
    data: dict[str, Any],
    path: Path,
    args: argparse.Namespace,
    team_index: int,
    rows: list[dict[str, Any]],
    death_step: int | None,
    death_cause: str,
) -> dict[str, Any]:
    names = names_for(data)
    result, team_reward, opp_reward = result_for(data.get("rewards") or [], team_index)
    labels = Counter()
    for row in rows:
        for label in str(row["labels"]).split(";"):
            if label:
                labels[label] += 1
    return {
        "source_group": args.group,
        "agent_label": args.agent_label,
        "team_name": names[team_index] if len(names) > team_index else str(team_index),
        "team_index": team_index,
        "episode_id": data.get("info", {}).get("EpisodeId") or path.stem,
        "seed": (data.get("configuration") or {}).get("seed", ""),
        "result": result,
        "team_reward": team_reward,
        "opp_reward": opp_reward,
        "steps": len(data.get("steps") or []),
        "death_step": "" if death_step is None else death_step,
        "death_cause": death_cause,
        "factory_dest_occupied_rows": sum(int(r["factory_dest_occupied_by_friendly"]) for r in rows),
        "friendly_vertex_conflict_rows": sum(int(r["friendly_vertex_conflict_t1"]) for r in rows),
        "friendly_edge_swap_rows": sum(int(r["friendly_edge_swap_t1"]) for r in rows),
        "enemy_vertex_conflict_rows": sum(int(r["enemy_vertex_conflict_t1"]) for r in rows),
        "enemy_edge_swap_rows": sum(int(r["enemy_edge_swap_t1"]) for r in rows),
        "support_into_factory_dest_rows": sum(int(r["support_into_factory_dest_count"] > 0) for r in rows),
        "build_spawn_conflict_rows": sum(int(r["build_spawn_conflict_count"] > 0) for r in rows),
        "north_blocker_rows": sum(int(bool(r["north_blocker_uid"])) for r in rows),
        "north_blocker_not_vacate_rows": sum(
            int(bool(r["north_blocker_uid"]) and not int(r["north_blocker_vacates"])) for r in rows
        ),
        "transform_on_factory_dest_rows": sum(int(r["transform_on_factory_dest"]) for r in rows),
        "death_next_conflict_rows": sum(int("death_next_conflict" in str(r["labels"]).split(";")) for r in rows),
        "top_labels": compact(labels),
        "replay_path": str(path),
    }


def analyze_replay(path: Path, args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(path.read_text())
    steps = data.get("steps") or []
    if len(steps) < 2:
        return [], []
    step_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    for team_index in team_indices(args, data):
        death_step, death_cause = death_info(data, team_index)
        rows = []
        for step_idx in range(len(steps) - 1):
            row = row_for_step(data, path, args, team_index, step_idx, death_step, death_cause)
            if row is not None:
                rows.append(row)
        step_rows.extend(rows)
        episode_rows.append(summarize_episode(data, path, args, team_index, rows, death_step, death_cause))
    return step_rows, episode_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--out-prefix", type=Path, required=True)
    parser.add_argument("--group", default="")
    parser.add_argument("--agent-label", default="")
    parser.add_argument("--team-name", default="")
    parser.add_argument("--team-index", type=int, default=None)
    parser.add_argument("--all-sides", action="store_true")
    parser.add_argument("--episodes-csv", type=Path, default=None)
    parser.add_argument("--max-replays", type=int, default=None)
    args = parser.parse_args()

    args.episode_team_indices = load_episode_team_indices(args.episodes_csv)
    replay_set = set(args.replay_dir.rglob("episode-*-replay.json"))
    replay_set.update(args.replay_dir.rglob("*-replay.json"))
    replays = sorted(replay_set)
    if args.max_replays is not None:
        replays = replays[: args.max_replays]
    if not replays:
        raise SystemExit(f"No replay JSONs found under {args.replay_dir}")

    step_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    for replay in replays:
        rows, episodes = analyze_replay(replay, args)
        step_rows.extend(rows)
        episode_rows.extend(episodes)

    write_csv(Path(f"{args.out_prefix}_steps.csv"), step_rows, STEP_FIELDS)
    write_csv(Path(f"{args.out_prefix}_episodes.csv"), episode_rows, EPISODE_FIELDS)
    label_counts = Counter()
    for row in step_rows:
        for label in str(row["labels"]).split(";"):
            if label:
                label_counts[label] += 1
    print(f"replays={len(replays)} sides={len(episode_rows)} steps={len(step_rows)}")
    print("top_labels", label_counts.most_common(12))
    print(f"wrote {args.out_prefix}_steps.csv")
    print(f"wrote {args.out_prefix}_episodes.csv")


if __name__ == "__main__":
    main()
