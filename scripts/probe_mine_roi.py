#!/usr/bin/env python3
"""Read-only mine ROI and harvest-feasibility probe for Crawl replays.

The probe has two deliberately separate outputs:

* candidate rows: counterfactual adjacent mining-node opportunities;
* lifecycle rows: mines that actually existed in the replay.

Candidate ROI is a feasibility estimate, not an outcome estimate. Actual mine
collection is reported as a conservative lower-bound proxy from mine-energy
changes plus observed friendly occupancy.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any


FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
TYPE_NAME = {FACTORY: "factory", SCOUT: "scout", WORKER: "worker", MINER: "miner"}
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}


CANDIDATE_FIELDS = [
    "source_group", "agent_label", "team_name", "team_index", "opponent", "episode_id", "seed",
    "replay_path", "step_idx", "result", "factory_col", "factory_row", "factory_gap",
    "factory_energy", "f_move_cd", "f_jump_cd", "f_build_cd", "support_count", "support_energy",
    "miner_count", "direction", "target_col", "target_row", "actual_factory_action",
    "actual_build_matches", "gate_adjacent_node", "gate_unoccupied", "gate_wall_open",
    "gate_no_existing_miner", "gate_build_cd", "gate_energy650", "gate_gap_gt8",
    "strict_v116_candidate", "build_uses_ready_move_slot", "collect_next_turn_move_ready",
    "north_progress_available", "collection_steals_north_slot", "route_base_dist",
    "route_after_collect_dist", "route_detour_moves", "node_lifetime_turns",
    "safe_hold_turns_gap8", "safe_hold_turns_gap4", "break_even_hold_turns",
    "break_even_before_gap8", "break_even_before_scroll", "initial_mine_energy_est",
    "break_even_energy_est", "feasible_build_on_cooldown", "feasible_north_route",
    "feasible_side_detour", "roi_class",
]

LIFECYCLE_FIELDS = [
    "source_group", "agent_label", "team_name", "team_index", "opponent", "episode_id", "seed",
    "replay_path", "mine_col", "mine_row", "first_seen_step", "last_seen_step",
    "lifetime_rows", "direction_from_factory_at_build", "build_step", "transform_step",
    "first_energy", "max_energy_seen", "final_energy", "rate", "owner",
    "friendly_occupied_rows", "factory_occupied_rows", "support_occupied_rows",
    "known_collection_lower_bound", "removed_below_boundary", "result",
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
    return {str(uid): list(robot) for uid, robot in robots.items()}


def global_mines(step: list[dict[str, Any]]) -> dict[tuple[int, int], list[Any]]:
    return {
        parse_pos(key): list(value)
        for key, value in (global_obs(step).get("globalMines") or {}).items()
    }


def global_nodes(step: list[dict[str, Any]]) -> set[tuple[int, int]]:
    return {parse_pos(key) for key in (global_obs(step).get("globalMiningNodes") or {})}


def global_walls(step: list[dict[str, Any]]) -> dict[str, list[int]]:
    return {
        str(row): [int(value) for value in values]
        for row, values in (global_obs(step).get("globalWalls") or {}).items()
    }


def global_bounds(step: list[dict[str, Any]]) -> tuple[int, int]:
    obs = global_obs(step)
    return int(obs.get("southBound", 0)), int(obs.get("northBound", 0))


def action_for(step: list[dict[str, Any]], agent_index: int) -> dict[str, str]:
    if 0 <= agent_index < len(step):
        return {str(k): str(v) for k, v in (step[agent_index].get("action") or {}).items()}
    return {}


def factory_for_owner(
    robots: dict[str, list[Any]], owner: int
) -> tuple[str, list[Any]] | tuple[None, None]:
    for uid, robot in robots.items():
        if int(robot[0]) == FACTORY and int(robot[4]) == owner:
            return uid, robot
    return None, None


def result_for(rewards: list[Any], team_index: int) -> tuple[str, Any, Any]:
    if len(rewards) != 2:
        return "", "", ""
    ours, theirs = rewards[team_index], rewards[1 - team_index]
    if ours > theirs:
        return "win", ours, theirs
    if ours < theirs:
        return "loss", ours, theirs
    return "draw", ours, theirs


def action_dir(action: str) -> str:
    if action in DIRS:
        return action
    if action.startswith("BUILD_MINER"):
        parts = action.split("_")
        return parts[2] if len(parts) >= 3 and parts[2] in DIRS else "NORTH"
    return ""


class WallView:
    def __init__(self, width: int, south: int, north: int, walls: dict[str, list[int]]) -> None:
        self.width = width
        self.south = south
        self.north = north
        self.walls = walls

    def wall(self, col: int, row: int) -> int:
        if not (0 <= col < self.width and self.south <= row <= self.north):
            return 15
        values = self.walls.get(str(row))
        if values is None or col >= len(values):
            return 0
        return int(values[col])

    def can_move(self, col: int, row: int, direction: str) -> bool:
        dc, dr = OFFSETS[direction]
        nc, nr = col + dc, row + dr
        return (
            0 <= nc < self.width
            and self.south <= nr <= self.north
            and not (self.wall(col, row) & WALL_BITS[direction])
        )


def bfs_distance(
    view: WallView,
    start: tuple[int, int],
    goals: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    depth: int = 20,
) -> int | None:
    if start in goals:
        return 0
    queue = deque([(start[0], start[1], 0)])
    seen = {start}
    while queue:
        col, row, dist = queue.popleft()
        if dist >= depth:
            continue
        for direction in DIRS:
            if not view.can_move(col, row, direction):
                continue
            dc, dr = OFFSETS[direction]
            nxt = (col + dc, row + dr)
            if nxt in seen or (nxt in occupied and nxt not in goals):
                continue
            if nxt in goals:
                return dist + 1
            seen.add(nxt)
            queue.append((nxt[0], nxt[1], dist + 1))
    return None


def future_turns_until(
    steps: list[list[dict[str, Any]]],
    step_idx: int,
    predicate,
) -> int:
    for future_idx in range(step_idx + 1, len(steps)):
        south, _ = global_bounds(steps[future_idx])
        if predicate(south):
            return future_idx - step_idx
    return len(steps) - 1 - step_idx


def team_indices(args: argparse.Namespace, data: dict[str, Any]) -> list[int]:
    if args.all_sides:
        return [0, 1]
    if args.team_index is not None:
        return [args.team_index]
    names = names_for(data)
    if args.team_name:
        return [names.index(args.team_name)] if args.team_name in names else []
    return [0]


def candidate_rows_for_side(
    data: dict[str, Any],
    path: Path,
    args: argparse.Namespace,
    team_index: int,
) -> list[dict[str, Any]]:
    steps = data.get("steps") or []
    config = data.get("configuration") or {}
    width = int(config.get("width", 20))
    names = names_for(data)
    result, _, _ = result_for(data.get("rewards") or [], team_index)
    rows: list[dict[str, Any]] = []
    for step_idx in range(len(steps) - 1):
        step = steps[step_idx]
        robots = global_robots(step)
        factory_uid, factory = factory_for_owner(robots, team_index)
        if factory is None:
            continue
        factory_col, factory_row = int(factory[1]), int(factory[2])
        south, north = global_bounds(step)
        view = WallView(width, south, north, global_walls(step))
        nodes = global_nodes(step)
        occupied = {(int(robot[1]), int(robot[2])) for robot in robots.values()}
        own_occupied = {
            (int(robot[1]), int(robot[2]))
            for robot in robots.values()
            if int(robot[4]) == team_index
        }
        supports = [
            robot for robot in robots.values()
            if int(robot[4]) == team_index and int(robot[0]) != FACTORY
        ]
        miner_count = sum(int(robot[0]) == MINER for robot in supports)
        action = action_for(steps[step_idx + 1], team_index).get(str(factory_uid), "IDLE")
        factory_gap = factory_row - south
        f_move_cd = int(factory[5]) if len(factory) > 5 else 0
        f_jump_cd = int(factory[6]) if len(factory) > 6 else 0
        f_build_cd = int(factory[7]) if len(factory) > 7 else 0
        target_row = min(north, factory_row + 5)
        goals = {(col, target_row) for col in range(width)}
        route_base = bfs_distance(view, (factory_col, factory_row), goals, own_occupied)
        north_progress_available = int(
            view.can_move(factory_col, factory_row, "NORTH")
            or route_base is not None
        )

        for direction in DIRS:
            dc, dr = OFFSETS[direction]
            target = (factory_col + dc, factory_row + dr)
            adjacent_node = target in nodes
            if not adjacent_node and not args.include_non_nodes:
                continue
            unoccupied = target not in occupied
            wall_open = view.can_move(factory_col, factory_row, direction)
            no_existing_miner = miner_count < 1
            build_cd_ok = f_build_cd <= 1
            energy_ok = int(factory[3]) >= 650
            gap_ok = factory_gap > 8
            strict = int(
                adjacent_node and unoccupied and wall_open and no_existing_miner
                and build_cd_ok and energy_ok and gap_ok
            )
            route_after = (
                bfs_distance(view, target, goals, own_occupied - {target})
                if wall_open else None
            )
            route_detour = ""
            if route_base is not None and route_after is not None:
                route_detour = 1 + route_after - route_base
            node_lifetime = future_turns_until(
                steps, step_idx, lambda future_south: future_south > target[1]
            )
            safe_gap8 = future_turns_until(
                steps, step_idx, lambda future_south: target[1] - future_south <= 8
            )
            safe_gap4 = future_turns_until(
                steps, step_idx, lambda future_south: target[1] - future_south <= 4
            )
            break_even_hold_turns = 3
            build_uses_ready_slot = int(f_move_cd <= 1)
            collect_next_ready = int(f_move_cd <= 2)
            steals_north = int(direction != "NORTH" and north_progress_available)
            feasible_build_on_cooldown = int(strict and not build_uses_ready_slot)
            feasible_north_route = int(
                strict and direction == "NORTH" and collect_next_ready
                and safe_gap8 >= break_even_hold_turns
            )
            feasible_side_detour = int(
                strict and direction in {"EAST", "WEST"}
                and not build_uses_ready_slot and collect_next_ready
                and route_detour != "" and int(route_detour) <= 1
                and safe_gap8 >= break_even_hold_turns
            )
            if feasible_north_route:
                roi_class = "north_route_collect"
            elif feasible_side_detour:
                roi_class = "side_low_detour_collect"
            elif strict and safe_gap8 < break_even_hold_turns:
                roi_class = "insufficient_safe_dwell"
            elif strict and build_uses_ready_slot:
                roi_class = "build_steals_move_slot"
            elif strict and direction != "NORTH" and (
                route_detour == "" or int(route_detour) > 1
            ):
                roi_class = "side_route_detour"
            elif strict:
                roi_class = "strict_unproven"
            else:
                roi_class = "not_strict"
            rows.append({
                "source_group": args.group,
                "agent_label": args.agent_label,
                "team_name": names[team_index] if len(names) > team_index else str(team_index),
                "team_index": team_index,
                "opponent": names[1 - team_index] if len(names) > 1 else "",
                "episode_id": data.get("info", {}).get("EpisodeId") or path.stem,
                "seed": config.get("seed", ""),
                "replay_path": str(path),
                "step_idx": step_idx,
                "result": result,
                "factory_col": factory_col,
                "factory_row": factory_row,
                "factory_gap": factory_gap,
                "factory_energy": int(factory[3]),
                "f_move_cd": f_move_cd,
                "f_jump_cd": f_jump_cd,
                "f_build_cd": f_build_cd,
                "support_count": len(supports),
                "support_energy": sum(int(robot[3]) for robot in supports),
                "miner_count": miner_count,
                "direction": direction,
                "target_col": target[0],
                "target_row": target[1],
                "actual_factory_action": action,
                "actual_build_matches": int(
                    action.startswith("BUILD_MINER") and action_dir(action) == direction
                ),
                "gate_adjacent_node": int(adjacent_node),
                "gate_unoccupied": int(unoccupied),
                "gate_wall_open": int(wall_open),
                "gate_no_existing_miner": int(no_existing_miner),
                "gate_build_cd": int(build_cd_ok),
                "gate_energy650": int(energy_ok),
                "gate_gap_gt8": int(gap_ok),
                "strict_v116_candidate": strict,
                "build_uses_ready_move_slot": build_uses_ready_slot,
                "collect_next_turn_move_ready": collect_next_ready,
                "north_progress_available": north_progress_available,
                "collection_steals_north_slot": steals_north,
                "route_base_dist": "" if route_base is None else route_base,
                "route_after_collect_dist": "" if route_after is None else route_after,
                "route_detour_moves": route_detour,
                "node_lifetime_turns": node_lifetime,
                "safe_hold_turns_gap8": safe_gap8,
                "safe_hold_turns_gap4": safe_gap4,
                "break_even_hold_turns": break_even_hold_turns,
                "break_even_before_gap8": int(safe_gap8 >= break_even_hold_turns),
                "break_even_before_scroll": int(node_lifetime >= break_even_hold_turns),
                "initial_mine_energy_est": int(config.get("minerCost", 300))
                - int(config.get("energyPerTurn", 1))
                - int(config.get("transformCost", 100)),
                "break_even_energy_est": int(config.get("minerCost", 300)),
                "feasible_build_on_cooldown": feasible_build_on_cooldown,
                "feasible_north_route": feasible_north_route,
                "feasible_side_detour": feasible_side_detour,
                "roi_class": roi_class,
            })
    return rows


def find_build_and_transform(
    data: dict[str, Any],
    team_index: int,
    mine_pos: tuple[int, int],
    first_seen_step: int,
) -> tuple[str, Any, Any]:
    steps = data.get("steps") or []
    build_direction = ""
    build_step: Any = ""
    transform_step: Any = ""
    for step_idx in range(max(0, first_seen_step - 8), first_seen_step):
        robots = global_robots(steps[step_idx])
        actions = action_for(steps[step_idx + 1], team_index) if step_idx + 1 < len(steps) else {}
        factory_uid, factory = factory_for_owner(robots, team_index)
        if factory_uid and factory is not None:
            action = actions.get(str(factory_uid), "")
            if action.startswith("BUILD_MINER"):
                direction = action_dir(action)
                dc, dr = OFFSETS[direction]
                if (int(factory[1]) + dc, int(factory[2]) + dr) == mine_pos:
                    build_direction = direction
                    build_step = step_idx
        for uid, robot in robots.items():
            if (
                int(robot[4]) == team_index and int(robot[0]) == MINER
                and (int(robot[1]), int(robot[2])) == mine_pos
                and actions.get(uid, "") == "TRANSFORM"
            ):
                transform_step = step_idx
    return build_direction, build_step, transform_step


def lifecycle_rows_for_side(
    data: dict[str, Any],
    path: Path,
    args: argparse.Namespace,
    team_index: int,
) -> list[dict[str, Any]]:
    steps = data.get("steps") or []
    config = data.get("configuration") or {}
    names = names_for(data)
    result, _, _ = result_for(data.get("rewards") or [], team_index)
    mine_seen: dict[tuple[int, int], list[tuple[int, list[Any], dict[str, list[Any]], int]]] = {}
    for step_idx, step in enumerate(steps):
        robots = global_robots(step)
        south, _ = global_bounds(step)
        for pos, mine in global_mines(step).items():
            if len(mine) >= 3 and int(mine[2]) == team_index:
                mine_seen.setdefault(pos, []).append((step_idx, mine, robots, south))

    rows = []
    for pos, sightings in sorted(mine_seen.items()):
        first_step, first_mine, _, _ = sightings[0]
        last_step, last_mine, _, last_south = sightings[-1]
        build_direction, build_step, transform_step = find_build_and_transform(
            data, team_index, pos, first_step
        )
        friendly_occupied = factory_occupied = support_occupied = 0
        lower_bound = 0
        previous_energy: int | None = None
        previous_max: int | None = None
        rate = int(first_mine[3]) if len(first_mine) > 3 else int(config.get("mineRate", 50))
        for _, mine, robots, _ in sightings:
            energy = int(mine[0])
            max_energy = int(mine[1])
            if previous_energy is not None and previous_max is not None:
                no_collection_next = min(previous_energy + rate, previous_max)
                lower_bound += max(0, no_collection_next - energy)
            occupants = [
                robot for robot in robots.values()
                if int(robot[4]) == team_index
                and (int(robot[1]), int(robot[2])) == pos
            ]
            if occupants:
                friendly_occupied += 1
                if any(int(robot[0]) == FACTORY for robot in occupants):
                    factory_occupied += 1
                if any(int(robot[0]) != FACTORY for robot in occupants):
                    support_occupied += 1
            previous_energy, previous_max = energy, max_energy
        removed_below = int(
            last_step + 1 < len(steps)
            and global_bounds(steps[last_step + 1])[0] > pos[1]
        )
        rows.append({
            "source_group": args.group,
            "agent_label": args.agent_label,
            "team_name": names[team_index] if len(names) > team_index else str(team_index),
            "team_index": team_index,
            "opponent": names[1 - team_index] if len(names) > 1 else "",
            "episode_id": data.get("info", {}).get("EpisodeId") or path.stem,
            "seed": config.get("seed", ""),
            "replay_path": str(path),
            "mine_col": pos[0],
            "mine_row": pos[1],
            "first_seen_step": first_step,
            "last_seen_step": last_step,
            "lifetime_rows": len(sightings),
            "direction_from_factory_at_build": build_direction,
            "build_step": build_step,
            "transform_step": transform_step,
            "first_energy": int(first_mine[0]),
            "max_energy_seen": max(int(mine[0]) for _, mine, _, _ in sightings),
            "final_energy": int(last_mine[0]),
            "rate": rate,
            "owner": team_index,
            "friendly_occupied_rows": friendly_occupied,
            "factory_occupied_rows": factory_occupied,
            "support_occupied_rows": support_occupied,
            "known_collection_lower_bound": lower_bound,
            "removed_below_boundary": removed_below,
            "result": result,
        })
    return rows


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
    parser.add_argument("--max-replays", type=int, default=None)
    parser.add_argument("--include-non-nodes", action="store_true")
    args = parser.parse_args()

    replay_set = set(args.replay_dir.rglob("episode-*-replay.json"))
    replay_set.update(args.replay_dir.rglob("*-replay.json"))
    replays = sorted(replay_set)
    if args.max_replays is not None:
        replays = replays[:args.max_replays]
    if not replays:
        raise SystemExit(f"No replay JSONs found under {args.replay_dir}")

    candidates: list[dict[str, Any]] = []
    lifecycles: list[dict[str, Any]] = []
    sides = 0
    for replay in replays:
        data = json.loads(replay.read_text(encoding="utf-8"))
        for team_index in team_indices(args, data):
            sides += 1
            candidates.extend(candidate_rows_for_side(data, replay, args, team_index))
            lifecycles.extend(lifecycle_rows_for_side(data, replay, args, team_index))

    candidate_path = Path(f"{args.out_prefix}_candidates.csv")
    lifecycle_path = Path(f"{args.out_prefix}_lifecycles.csv")
    write_csv(candidate_path, candidates, CANDIDATE_FIELDS)
    write_csv(lifecycle_path, lifecycles, LIFECYCLE_FIELDS)
    strict = [row for row in candidates if int(row["strict_v116_candidate"])]
    roi_counts = Counter(str(row["roi_class"]) for row in strict)
    directions = Counter(str(row["direction"]) for row in strict)
    collected = sum(int(row["known_collection_lower_bound"]) for row in lifecycles)
    occupied = sum(int(row["friendly_occupied_rows"]) for row in lifecycles)
    print(
        f"replays={len(replays)} sides={sides} candidates={len(candidates)} "
        f"strict={len(strict)} lifecycles={len(lifecycles)}"
    )
    print("strict_directions", directions.most_common())
    print("strict_roi_classes", roi_counts.most_common())
    print(f"actual_collection_lower_bound={collected} occupied_rows={occupied}")
    print(f"wrote {candidate_path}")
    print(f"wrote {lifecycle_path}")


if __name__ == "__main__":
    main()
