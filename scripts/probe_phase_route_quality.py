#!/usr/bin/env python3
"""Read-only phase, route-quality, and support-distribution probe.

This script analyzes replay JSONs. It deliberately does not import agent
modules or modify submissions.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, deque
from pathlib import Path
from typing import Any


FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
TYPE_NAME = {FACTORY: "factory", SCOUT: "scout", WORKER: "worker", MINER: "miner"}
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}
PHASE_ID = {"MINE_SPRINT": 0, "CONVEYOR": 1, "PRESSURE": 2, "FINAL_KICK": 3}


STEP_FIELDS = [
    "source_group", "agent_label", "team_name", "team_index", "opponent", "episode_id", "seed",
    "replay_path", "step_idx", "obs_step", "action_step_idx", "result", "team_reward", "opp_reward",
    "width", "height", "south_bound", "north_bound", "scroll_counter", "scroll_start_interval",
    "scroll_end_interval", "scroll_ramp_steps", "factory_move_period", "factory_jump_cooldown_cfg",
    "factory_build_cooldown_cfg", "factory_alive", "factory_uid", "factory_col", "factory_row",
    "factory_gap", "factory_energy", "f_move_cd", "f_jump_cd", "f_build_cd", "factory_on_own_mine",
    "factory_on_mining_node", "scout_count", "worker_count", "miner_count", "support_count",
    "support_energy", "support_energy_max", "support_energy_p50", "north_neighbor_uid",
    "north_neighbor_type", "north_neighbor_energy", "north_neighbor_is_friendly_support",
    "side_miner_count", "north_miner_count", "south_miner_count", "worker_near_factory_count",
    "opp_factory_alive", "opp_factory_col", "opp_factory_row", "opp_factory_gap", "opp_factory_energy",
    "opp_support_count", "opp_support_energy", "collision_tiebreak_bad", "enemy_factory_near",
    "enemy_factory_threat_count", "enemy_factory_jump_threat_count", "phase", "phase_id", "phase_reason",
    "soft_transition", "next_phase", "step_to_phase_30", "step_to_phase_200", "step_to_phase_400",
    "gap_to_pressure_8", "gap_to_final_4", "rq_known_available", "rq_known_main_found",
    "rq_known_main_dist", "rq_known_main_first_action", "rq_known_main_uses_jump",
    "rq_known_closer_found", "rq_known_closer_dist", "rq_known_closer_first_action",
    "rq_known_bucket", "rq_known_score", "rq_oracle_main_found", "rq_oracle_main_dist",
    "rq_oracle_main_first_action", "rq_oracle_main_uses_jump", "rq_oracle_closer_found",
    "rq_oracle_closer_dist", "rq_oracle_closer_first_action", "rq_oracle_bucket", "rq_oracle_score",
    "can_move_north", "can_move_east", "can_move_west", "can_move_south", "can_jump_north",
    "can_jump_east", "can_jump_west", "can_jump_south", "north_wall_blocked", "north_cell_occupied",
    "north_cell_occupied_by", "jump_north_landing_occupied", "jump_north_landing_wall_full",
    "factory_action", "factory_action_head", "factory_action_dir", "factory_action_dest_col",
    "factory_action_dest_row", "factory_action_row_delta", "factory_action_is_build",
    "factory_action_is_transfer", "factory_action_is_remove", "factory_action_is_jump",
    "factory_action_is_south", "factory_action_is_lateral", "support_action_count",
    "support_build_count", "support_transfer_count", "support_remove_count", "support_transform_count",
    "all_actions_compact", "r1_transfer_candidate", "r1_transfer_fired", "r1_target_type",
    "r1_target_energy", "mine_build_candidate_north", "mine_relaxed_candidate_north",
    "mine_relaxed_candidate_side", "mine_relaxed_candidate_any", "mine_relaxed_candidate_dirs",
    "mine_shadow_blocked_by_energy", "mine_shadow_blocked_by_gap", "mine_shadow_blocked_by_build_cd",
    "mine_shadow_blocked_by_existing_miner", "mine_shadow_blocked_by_occupied",
    "mine_shadow_blocked_by_wall", "scout_build_candidate", "worker_build_candidate",
    "late_spend_action", "late_factory_spend_action", "late_support_spend_count", "bad_any",
    "bad_labels", "bad_phase_spend", "bad_final_build", "bad_final_transfer", "bad_final_remove",
    "bad_final_south_action", "bad_lateral_jcd_lock_risk", "bad_route_blocked", "bad_only_south_escape",
    "bad_support_void", "bad_support_blocking_factory", "bad_collision_tiebreak",
    "bad_high_factory_low_support_energy", "bad_mine_roi_low_lifetime", "death_next_step",
    "factory_dead_now",
]

BAD_FIELDS = [
    "source_group", "agent_label", "team_name", "team_index", "opponent", "episode_id", "seed",
    "result", "team_reward", "opp_reward", "step_idx", "action_step_idx", "phase", "factory_col",
    "factory_row", "factory_gap", "factory_energy", "support_count", "support_energy",
    "opp_support_count", "opp_support_energy", "f_move_cd", "f_jump_cd", "f_build_cd",
    "rq_known_bucket", "rq_oracle_bucket", "factory_action", "bad_labels", "death_next_step",
    "replay_path",
]

EPISODE_FIELDS = [
    "source_group", "agent_label", "team_name", "team_index", "opponent", "episode_id", "seed",
    "result", "team_reward", "opp_reward", "steps", "death_step", "death_cause", "final_factory_row",
    "final_factory_energy", "final_support_count", "final_support_energy", "max_factory_energy",
    "max_support_energy", "min_gap_after_scroll", "phase_counts", "phase_spend_counts",
    "bad_label_counts", "first_bad_step", "first_final_kick_step", "first_miner_step",
    "first_worker_step", "first_transfer_step", "first_side_miner_step", "late_spend_count",
    "late_build_count", "late_transfer_count", "route_blocked_steps", "only_south_escape_steps",
    "lateral_jcd_lock_events", "support_void_pressure_steps", "replay_path",
]


def parse_pos(text: str) -> tuple[int, int]:
    col, row = str(text).split(",", 1)
    return int(col), int(row)


def names_for(data: dict[str, Any]) -> list[str]:
    info = data.get("info", {})
    return info.get("TeamNames") or [a.get("Name", "") for a in info.get("Agents", [])]


def config_int(config: dict[str, Any], name: str, default: int = 0) -> int:
    return int(config.get(name, default) or default)


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
    for uid, data in robots.items():
        if int(data[0]) == FACTORY and int(data[4]) == owner:
            return uid, data
    return None, None


def support_robots(robots: dict[str, list[Any]], owner: int) -> list[tuple[str, list[Any]]]:
    return [(uid, data) for uid, data in robots.items() if int(data[4]) == owner and int(data[0]) != FACTORY]


def robot_counts(robots: dict[str, list[Any]], owner: int) -> dict[str, Any]:
    counts = Counter()
    energies: list[int] = []
    for _, data in support_robots(robots, owner):
        rtype = int(data[0])
        counts[rtype] += 1
        energies.append(int(data[3]))
    return {
        "scout_count": counts[SCOUT],
        "worker_count": counts[WORKER],
        "miner_count": counts[MINER],
        "support_count": sum(counts.values()),
        "support_energy": sum(energies),
        "support_energy_max": max(energies) if energies else 0,
        "support_energy_p50": statistics.median(energies) if energies else 0,
    }


def support_energy_count(robots: dict[str, list[Any]], owner: int) -> tuple[int, int]:
    stats = robot_counts(robots, owner)
    return int(stats["support_energy"]), int(stats["support_count"])


class WallView:
    def __init__(
        self,
        width: int,
        south: int,
        north: int,
        global_rows: dict[str, list[int]] | None = None,
        local_walls: list[int] | None = None,
    ) -> None:
        self.width = width
        self.south = south
        self.north = north
        self.global_rows = global_rows
        self.local_walls = local_walls

    def get_wall(self, col: int, row: int) -> int:
        if not (0 <= col < self.width and self.south <= row <= self.north):
            return 15
        if self.global_rows is not None:
            vals = self.global_rows.get(str(row))
            if vals is None or col >= len(vals):
                return 0
            return int(vals[col])
        if self.local_walls is not None:
            idx = (row - self.south) * self.width + col
            if idx < 0 or idx >= len(self.local_walls):
                return 0
            val = int(self.local_walls[idx])
            return 0 if val == -1 else val
        return 0


def can_move(view: WallView, col: int, row: int, direction: str) -> bool:
    dc, dr = OFFSETS[direction]
    nc, nr = col + dc, row + dr
    if not (0 <= nc < view.width and view.south <= nr <= view.north):
        return False
    return not (view.get_wall(col, row) & WALL_BITS[direction])


def can_jump(view: WallView, col: int, row: int, direction: str) -> bool:
    dc, dr = OFFSETS[direction]
    nc, nr = col + 2 * dc, row + 2 * dr
    if not (0 <= nc < view.width and view.south <= nr <= view.north):
        return False
    return view.get_wall(nc, nr) != 15


def adjacent_cell(col: int, row: int, direction: str) -> tuple[int, int]:
    dc, dr = OFFSETS[direction]
    return col + dc, row + dr


def action_head(action: str) -> str:
    if not action:
        return ""
    if action in OFFSETS:
        return "MOVE"
    return action.split("_", 1)[0]


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
    return col, row


def current_phase(step: int, factory_gap: int, factory_energy: int) -> tuple[str, str]:
    if step >= 400:
        return "FINAL_KICK", "step>=400"
    if factory_gap <= 4:
        return "FINAL_KICK", "gap<=4"
    if step >= 200:
        return "PRESSURE", "step>=200"
    if factory_gap <= 8:
        return "PRESSURE", "gap<=8"
    if step >= 30 and factory_gap > 8 and factory_energy >= 300:
        return "CONVEYOR", "step>=30_energy>=300_gap>8"
    return "MINE_SPRINT", "default"


def phase_row(step: int, gap: int, energy: int) -> dict[str, Any]:
    phase, reason = current_phase(step, gap, energy)
    next_phase, _ = current_phase(step + 1, max(0, gap - 1), energy)
    soft = int(
        any(abs(step - boundary) <= 5 for boundary in (30, 200, 400))
        or abs(gap - 8) <= 1
        or abs(gap - 4) <= 1
    )
    return {
        "phase": phase,
        "phase_id": PHASE_ID[phase],
        "phase_reason": reason,
        "soft_transition": soft,
        "next_phase": "" if next_phase == phase else next_phase,
        "step_to_phase_30": 30 - step,
        "step_to_phase_200": 200 - step,
        "step_to_phase_400": 400 - step,
        "gap_to_pressure_8": gap - 8,
        "gap_to_final_4": gap - 4,
    }


def route_goals(width: int, north: int, row: int) -> set[tuple[int, int]]:
    target_row = min(north, row)
    return {(col, target_row) for col in range(width)}


def bfs_first_step(
    view: WallView,
    start: tuple[int, int],
    goals: set[tuple[int, int]],
    depth: int,
    occupied: set[tuple[int, int]],
) -> tuple[str | None, int | None]:
    queue = deque([(start[0], start[1], 0, None)])
    seen = {start}
    while queue:
        col, row, dist, first = queue.popleft()
        if dist > 0 and (col, row) in goals:
            return first, dist
        if dist >= depth:
            continue
        for direction in DIRS:
            if not can_move(view, col, row, direction):
                continue
            dc, dr = OFFSETS[direction]
            nxt = (col + dc, row + dr)
            if nxt in seen or (nxt in occupied and nxt not in goals):
                continue
            seen.add(nxt)
            queue.append((nxt[0], nxt[1], dist + 1, first or direction))
    return None, None


def bfs_jump(
    view: WallView,
    start: tuple[int, int],
    goals: set[tuple[int, int]],
    jump_cd: int,
    jump_cooldown_cfg: int,
    depth: int,
    occupied: set[tuple[int, int]],
    north_only_jump: bool,
) -> tuple[str | None, int | None]:
    queue = deque([(start[0], start[1], max(0, jump_cd), 0, None)])
    seen = {(start[0], start[1], max(0, jump_cd))}
    while queue:
        col, row, jcd, dist, first = queue.popleft()
        if dist > 0 and (col, row) in goals:
            return first, dist
        if dist >= depth:
            continue
        if jcd <= 0:
            jump_dirs = ("NORTH",) if north_only_jump else DIRS
            for direction in jump_dirs:
                if not can_jump(view, col, row, direction):
                    continue
                dc, dr = OFFSETS[direction]
                nxt = (col + 2 * dc, row + 2 * dr)
                state = (nxt[0], nxt[1], jump_cooldown_cfg)
                if state in seen or (nxt in occupied and nxt not in goals):
                    continue
                seen.add(state)
                queue.append((nxt[0], nxt[1], jump_cooldown_cfg, dist + 1, first or f"JUMP_{direction}"))
        for direction in DIRS:
            if not can_move(view, col, row, direction):
                continue
            dc, dr = OFFSETS[direction]
            nxt = (col + dc, row + dr)
            njcd = max(0, jcd - 1)
            state = (nxt[0], nxt[1], njcd)
            if state in seen or (nxt in occupied and nxt not in goals):
                continue
            seen.add(state)
            queue.append((nxt[0], nxt[1], njcd, dist + 1, first or direction))
    return None, None


def route_bucket(main_dist: int | None, closer_dist: int | None, available: bool = True) -> tuple[str, Any]:
    if not available:
        return "unknown", ""
    if main_dist is not None:
        if main_dist <= 5:
            return "excellent", 4
        if main_dist <= 12:
            return "ok", 3
        return "long", 2
    if closer_dist is not None:
        return "closer_only", 1
    return "blocked", 0


def route_metrics(
    prefix: str,
    view: WallView | None,
    start: tuple[int, int],
    factory_row: int,
    factory_gap: int,
    jump_cd: int,
    jump_cooldown_cfg: int,
    depth: int,
    occupied: set[tuple[int, int]],
    available: bool = True,
) -> dict[str, Any]:
    if view is None or not available:
        return {
            f"rq_{prefix}_available": 0,
            f"rq_{prefix}_main_found": 0,
            f"rq_{prefix}_main_dist": "",
            f"rq_{prefix}_main_first_action": "",
            f"rq_{prefix}_main_uses_jump": 0,
            f"rq_{prefix}_closer_found": 0,
            f"rq_{prefix}_closer_dist": "",
            f"rq_{prefix}_closer_first_action": "",
            f"rq_{prefix}_bucket": "unknown",
            f"rq_{prefix}_score": "",
        }
    main_goals = route_goals(view.width, view.north, factory_row + 20)
    closer_goals = route_goals(view.width, view.north, factory_row + 5)
    main_first, main_dist = bfs_jump(
        view, start, main_goals, jump_cd, jump_cooldown_cfg, depth, occupied, factory_gap <= 8
    )
    closer_first, closer_dist = bfs_first_step(view, start, closer_goals, depth, occupied)
    bucket, score = route_bucket(main_dist, closer_dist)
    return {
        f"rq_{prefix}_available": 1,
        f"rq_{prefix}_main_found": int(main_dist is not None),
        f"rq_{prefix}_main_dist": "" if main_dist is None else main_dist,
        f"rq_{prefix}_main_first_action": main_first or "",
        f"rq_{prefix}_main_uses_jump": int(bool(main_first and main_first.startswith("JUMP_"))),
        f"rq_{prefix}_closer_found": int(closer_dist is not None),
        f"rq_{prefix}_closer_dist": "" if closer_dist is None else closer_dist,
        f"rq_{prefix}_closer_first_action": closer_first or "",
        f"rq_{prefix}_bucket": bucket,
        f"rq_{prefix}_score": score,
    }


def compact_counts(counts: Counter[str]) -> str:
    return ";".join(f"{key}:{counts[key]}" for key in sorted(counts))


def result_for(rewards: list[Any], team_index: int) -> tuple[str, Any, Any]:
    if len(rewards) != 2:
        return "", "", ""
    team_reward = rewards[team_index]
    opp_reward = rewards[1 - team_index]
    if team_reward > opp_reward:
        result = "win"
    elif team_reward < opp_reward:
        result = "loss"
    else:
        result = "draw"
    return result, team_reward, opp_reward


def death_info(data: dict[str, Any], team_index: int) -> tuple[int | None, str]:
    steps = data.get("steps") or []
    rewards = data.get("rewards") or []
    result, _, _ = result_for(rewards, team_index)
    death_step = None
    for idx, step in enumerate(steps):
        robots = global_robots(step)
        _, factory = factory_for_owner(robots, team_index)
        if factory is None:
            death_step = idx
            break
    if death_step is None:
        episode_steps = config_int(data.get("configuration", {}), "episodeSteps", 501)
        if result != "win" and len(steps) >= episode_steps - 1:
            return None, "timeout_tiebreak"
        if result != "win":
            return None, "loss_without_factory_death_detected"
        return None, "active_or_win"

    prev_idx = max(0, death_step - 1)
    prev_robots = global_robots(steps[prev_idx])
    curr_robots = global_robots(steps[death_step])
    south_at_death, _ = global_bounds(steps[death_step])
    our_uid, our_prev = factory_for_owner(prev_robots, team_index)
    opp_uid, opp_prev = factory_for_owner(prev_robots, 1 - team_index)
    _, our_curr = factory_for_owner(curr_robots, team_index)
    _, opp_curr = factory_for_owner(curr_robots, 1 - team_index)
    our_action = action_for(steps[death_step], team_index).get(str(our_uid), "") if our_uid else ""
    opp_action = action_for(steps[death_step], 1 - team_index).get(str(opp_uid), "") if opp_uid else ""
    our_dest = action_dest(int(our_prev[1]), int(our_prev[2]), our_action) if our_prev else None
    opp_dest = action_dest(int(opp_prev[1]), int(opp_prev[2]), opp_action) if opp_prev else None
    if our_prev is not None and int(our_prev[2]) < south_at_death:
        return death_step, "boundary_scroll"
    if our_curr is None and opp_curr is None and our_dest is not None and our_dest == opp_dest:
        return death_step, "factory_collision"
    if our_curr is None and opp_curr is None:
        return death_step, "simultaneous_tiebreak"
    if our_curr is None:
        return death_step, "single_factory_death"
    return death_step, "active_or_win"


def local_wall_view(
    obs: dict[str, Any],
    width: int,
    south: int,
    north: int,
    known_mode: str,
) -> tuple[WallView | None, bool]:
    if known_mode == "off":
        return None, False
    walls = obs.get("walls")
    if not isinstance(walls, list):
        return None, False
    local_south = obs.get("southBound", south if known_mode == "filled" else None)
    local_north = obs.get("northBound", north if known_mode == "filled" else None)
    if local_south is None or local_north is None:
        return None, False
    local_south, local_north = int(local_south), int(local_north)
    expected = width * (local_north - local_south + 1)
    if len(walls) != expected:
        return None, False
    return WallView(width, local_south, local_north, local_walls=[int(x) for x in walls]), True


def owned_mine_positions(obs: dict[str, Any], owner: int) -> set[tuple[int, int]]:
    out = set()
    for key, data in (obs.get("globalMines") or {}).items():
        vals = list(data)
        if len(vals) >= 3 and int(vals[2]) == owner:
            out.add(parse_pos(key))
    return out


def mining_node_positions(obs: dict[str, Any]) -> set[tuple[int, int]]:
    return {parse_pos(key) for key in (obs.get("globalMiningNodes") or {}).keys()}


def row_for_step(
    data: dict[str, Any],
    path: Path,
    source_group: str,
    agent_label: str,
    team_index: int,
    step_idx: int,
    death_step: int | None,
    death_cause: str,
    known_mode: str,
    route_depth: int,
) -> dict[str, Any] | None:
    steps = data.get("steps") or []
    step = steps[step_idx]
    next_step = steps[step_idx + 1]
    config = data.get("configuration", {})
    width = config_int(config, "width", 16)
    height = config_int(config, "height", 100)
    south, north = global_bounds(step)
    gobs = global_obs(step)
    obs = obs_for(step, team_index)
    robots = global_robots(step)
    factory_uid, factory = factory_for_owner(robots, team_index)
    if factory is None:
        return None
    opp_uid, opp_factory = factory_for_owner(robots, 1 - team_index)
    names = names_for(data)
    rewards = data.get("rewards") or []
    result, team_reward, opp_reward = result_for(rewards, team_index)
    opponent = names[1 - team_index] if len(names) > 1 else ""
    team_name = names[team_index] if len(names) > team_index else str(team_index)
    factory_col, factory_row, factory_energy = int(factory[1]), int(factory[2]), int(factory[3])
    factory_gap = factory_row - south
    f_move_cd = int(factory[5]) if len(factory) > 5 else 0
    f_jump_cd = int(factory[6]) if len(factory) > 6 else 0
    f_build_cd = int(factory[7]) if len(factory) > 7 else 0
    opp_energy, opp_count = support_energy_count(robots, 1 - team_index)
    stats = robot_counts(robots, team_index)
    own_positions = {
        (int(data_[1]), int(data_[2]))
        for _, data_ in robots.items()
        if int(data_[4]) == team_index and int(data_[0]) != FACTORY
    }
    all_positions = {
        (int(data_[1]), int(data_[2])): uid
        for uid, data_ in robots.items()
        if int(data_[4]) == team_index
    }

    oracle_view = WallView(width, south, north, global_rows=global_walls(step))
    known_view, known_available = local_wall_view(obs, width, south, north, known_mode)
    jump_cd_cfg = config_int(config, "factoryJumpCooldown", 20)
    oracle_route = route_metrics(
        "oracle", oracle_view, (factory_col, factory_row), factory_row, factory_gap,
        f_jump_cd, jump_cd_cfg, route_depth, own_positions, True,
    )
    known_route = route_metrics(
        "known", known_view, (factory_col, factory_row), factory_row, factory_gap,
        f_jump_cd, jump_cd_cfg, route_depth, own_positions, known_available,
    )
    known_route["rq_known_available"] = int(known_available)

    actions = action_for(next_step, team_index)
    factory_action = actions.get(str(factory_uid), "")
    head = action_head(factory_action)
    direction = action_dir(factory_action)
    dest_col, dest_row = action_dest(factory_col, factory_row, factory_action)
    support_actions = {
        uid: act for uid, act in actions.items()
        if uid in robots and int(robots[uid][4]) == team_index and int(robots[uid][0]) != FACTORY
    }
    support_heads = Counter(action_head(act) for act in support_actions.values())
    action_counts = Counter(actions.values())

    north_cell = (factory_col, factory_row + 1)
    north_neighbor_uid = ""
    north_neighbor_type = ""
    north_neighbor_energy = ""
    north_neighbor_is_friendly_support = 0
    for uid, data_ in robots.items():
        if (int(data_[1]), int(data_[2])) == north_cell:
            north_neighbor_uid = uid
            north_neighbor_type = TYPE_NAME.get(int(data_[0]), str(data_[0]))
            north_neighbor_energy = int(data_[3])
            north_neighbor_is_friendly_support = int(int(data_[4]) == team_index and int(data_[0]) != FACTORY)
            break

    side_miner_count = north_miner_count = south_miner_count = 0
    worker_near_factory_count = 0
    for _, data_ in support_robots(robots, team_index):
        rtype, col, row = int(data_[0]), int(data_[1]), int(data_[2])
        if rtype == MINER:
            if col != factory_col:
                side_miner_count += 1
            elif row > factory_row:
                north_miner_count += 1
            elif row < factory_row:
                south_miner_count += 1
        if rtype == WORKER and abs(col - factory_col) + abs(row - factory_row) <= 3:
            worker_near_factory_count += 1

    opp_factory_alive = int(opp_factory is not None)
    opp_factory_col = int(opp_factory[1]) if opp_factory else ""
    opp_factory_row = int(opp_factory[2]) if opp_factory else ""
    opp_factory_gap = int(opp_factory[2]) - south if opp_factory else ""
    opp_factory_energy = int(opp_factory[3]) if opp_factory else ""

    enemy_factory_near = 0
    threat_count = 0
    jump_threat_count = 0
    if opp_factory is not None:
        ec, er = int(opp_factory[1]), int(opp_factory[2])
        enemy_factory_near = int(abs(ec - factory_col) + abs(er - factory_row) <= 4)
        emove_cd = int(opp_factory[5]) if len(opp_factory) > 5 else 0
        ejump_cd = int(opp_factory[6]) if len(opp_factory) > 6 else 0
        if emove_cd <= 0:
            for enemy_dir in DIRS:
                if can_move(oracle_view, ec, er, enemy_dir):
                    edest = action_dest(ec, er, enemy_dir)
                    if edest == (dest_col, dest_row):
                        threat_count += 1
        if ejump_cd <= 0:
            for enemy_dir in DIRS:
                if can_jump(oracle_view, ec, er, enemy_dir):
                    edest = action_dest(ec, er, f"JUMP_{enemy_dir}")
                    if edest == (dest_col, dest_row):
                        jump_threat_count += 1
    own_energy = int(stats["support_energy"])
    own_count = int(stats["support_count"])
    collision_tiebreak_bad = int((threat_count or jump_threat_count) and (own_energy, own_count) <= (opp_energy, opp_count))

    phase = phase_row(int(gobs.get("step", step_idx) or step_idx), factory_gap, factory_energy)
    mining_nodes = mining_node_positions(gobs)
    owned_mines = owned_mine_positions(gobs, team_index)
    spawn_ok = (
        south <= north_cell[1] <= north and 0 <= north_cell[0] < width
        and not (oracle_view.get_wall(factory_col, factory_row) & WALL_BITS["NORTH"])
        and north_cell not in all_positions
    )
    r1_candidate = int(
        f_move_cd <= 1
        and int(stats["miner_count"]) == 0
        and north_neighbor_is_friendly_support
        and isinstance(north_neighbor_energy, int)
        and 280 <= north_neighbor_energy <= 600
        and not (oracle_view.get_wall(factory_col, factory_row) & WALL_BITS["NORTH"])
        and south <= north_cell[1] <= north
    )
    mine_original_energy_ok = factory_energy >= 650
    mine_original_gap_ok = factory_gap > 6
    mine_relaxed_energy_ok = factory_energy >= 350
    mine_relaxed_gap_ok = factory_gap > 3
    mine_build_cd_ok = f_build_cd <= 1
    no_existing_miner = int(stats["miner_count"]) < 1
    mine_dir_status: dict[str, dict[str, Any]] = {}
    for d in DIRS:
        mpos = adjacent_cell(factory_col, factory_row, d)
        mine_dir_status[d] = {
            "node": mpos in mining_nodes,
            "occupied": mpos in all_positions,
            "wall": not can_move(oracle_view, factory_col, factory_row, d),
        }
    north_mine_status = mine_dir_status["NORTH"]
    mine_candidate = int(
        mine_build_cd_ok
        and mine_original_energy_ok
        and mine_original_gap_ok
        and no_existing_miner
        and north_mine_status["node"]
        and not north_mine_status["occupied"]
        and not north_mine_status["wall"]
    )
    relaxed_dirs = [
        d for d, status in mine_dir_status.items()
        if (
            mine_build_cd_ok
            and mine_relaxed_energy_ok
            and mine_relaxed_gap_ok
            and no_existing_miner
            and status["node"]
            and not status["occupied"]
            and not status["wall"]
        )
    ]
    side_relaxed_dirs = [d for d in relaxed_dirs if d in {"EAST", "WEST"}]
    mine_relaxed_candidate_north = int("NORTH" in relaxed_dirs)
    mine_relaxed_candidate_side = int(bool(side_relaxed_dirs))
    mine_relaxed_candidate_any = int(bool(relaxed_dirs))
    adjacent_mining_node_dirs = [d for d, status in mine_dir_status.items() if status["node"]]
    mine_shadow_blocked_by_energy = int(bool(adjacent_mining_node_dirs) and not mine_relaxed_energy_ok)
    mine_shadow_blocked_by_gap = int(bool(adjacent_mining_node_dirs) and mine_relaxed_energy_ok and not mine_relaxed_gap_ok)
    mine_shadow_blocked_by_build_cd = int(bool(adjacent_mining_node_dirs) and mine_relaxed_energy_ok and mine_relaxed_gap_ok and not mine_build_cd_ok)
    mine_shadow_blocked_by_existing_miner = int(
        bool(adjacent_mining_node_dirs)
        and mine_relaxed_energy_ok
        and mine_relaxed_gap_ok
        and mine_build_cd_ok
        and not no_existing_miner
    )
    mine_shadow_blocked_by_occupied = int(
        bool(adjacent_mining_node_dirs)
        and mine_relaxed_energy_ok
        and mine_relaxed_gap_ok
        and mine_build_cd_ok
        and no_existing_miner
        and any(mine_dir_status[d]["occupied"] for d in adjacent_mining_node_dirs)
    )
    mine_shadow_blocked_by_wall = int(
        bool(adjacent_mining_node_dirs)
        and mine_relaxed_energy_ok
        and mine_relaxed_gap_ok
        and mine_build_cd_ok
        and no_existing_miner
        and any(mine_dir_status[d]["wall"] for d in adjacent_mining_node_dirs)
    )
    scout_candidate = int(
        int(gobs.get("step", step_idx) or step_idx) >= 24
        and f_build_cd <= 1
        and spawn_ok
        and int(stats["scout_count"]) < 1
        and factory_energy >= 50
        and factory_gap > 4
    )
    worker_candidate = int(
        int(stats["worker_count"]) < 1 and factory_energy >= 200 and factory_gap <= 4 and spawn_ok
    )

    factory_spend = int(
        factory_action.startswith(("BUILD_", "TRANSFER_", "REMOVE_"))
        or factory_action == "TRANSFORM"
    )
    support_spend = sum(
        1 for act in support_actions.values()
        if act.startswith(("BUILD_", "TRANSFER_", "REMOVE_")) or act == "TRANSFORM"
    )
    late_phase = phase["phase"] in {"PRESSURE", "FINAL_KICK"}
    late_factory_spend = int(late_phase and factory_spend)
    late_support_spend = support_spend if late_phase else 0
    late_spend = int(late_factory_spend or late_support_spend)

    can_moves = {d: int(can_move(oracle_view, factory_col, factory_row, d)) for d in DIRS}
    can_jumps = {d: int(can_jump(oracle_view, factory_col, factory_row, d)) for d in DIRS}
    jump_north_landing = (factory_col, factory_row + 2)
    north_wall_blocked = int(bool(oracle_view.get_wall(factory_col, factory_row) & WALL_BITS["NORTH"]))
    north_cell_occupied = int(north_cell in all_positions)
    jump_north_landing_occupied = int(jump_north_landing in all_positions)
    jump_north_landing_wall_full = int(oracle_view.get_wall(*jump_north_landing) == 15)

    labels: list[str] = []
    if late_spend:
        labels.append("bad_phase_spend")
    if phase["phase"] == "FINAL_KICK" and factory_action.startswith("BUILD_"):
        labels.append("bad_final_build")
    if phase["phase"] == "FINAL_KICK" and factory_action.startswith("TRANSFER_"):
        labels.append("bad_final_transfer")
    if phase["phase"] == "FINAL_KICK" and factory_action.startswith("REMOVE_"):
        labels.append("bad_final_remove")
    if phase["phase"] == "FINAL_KICK" and factory_action in {"SOUTH", "JUMP_SOUTH"}:
        labels.append("bad_final_south_action")
    if phase["phase"] in {"PRESSURE", "FINAL_KICK"} and factory_action in {"JUMP_EAST", "JUMP_WEST"} and factory_gap <= 8:
        labels.append("bad_lateral_jcd_lock_risk")
    if oracle_route["rq_oracle_bucket"] == "blocked" or (
        known_available and known_route["rq_known_bucket"] == "blocked"
    ):
        labels.append("bad_route_blocked")
    if can_moves["SOUTH"] and not any(can_moves[d] or can_jumps[d] for d in ("NORTH", "EAST", "WEST")) and factory_gap <= 4:
        labels.append("bad_only_south_escape")
    if phase["phase"] in {"PRESSURE", "FINAL_KICK"} and int(stats["support_count"]) == 0:
        labels.append("bad_support_void")
    if north_neighbor_is_friendly_support and can_moves["NORTH"]:
        labels.append("bad_support_blocking_factory")
    if collision_tiebreak_bad or (death_step == step_idx + 1 and death_cause == "factory_collision"):
        labels.append("bad_collision_tiebreak")
    if factory_energy >= 1000 and int(stats["support_energy"]) < 100 and phase["phase"] in {"PRESSURE", "FINAL_KICK"}:
        labels.append("bad_high_factory_low_support_energy")
    if factory_action.startswith("BUILD_MINER") and (phase["phase"] in {"PRESSURE", "FINAL_KICK"} or factory_gap <= 8):
        labels.append("bad_mine_roi_low_lifetime")

    row: dict[str, Any] = {
        "source_group": source_group,
        "agent_label": agent_label,
        "team_name": team_name,
        "team_index": team_index,
        "opponent": opponent,
        "episode_id": data.get("info", {}).get("EpisodeId") or path.stem,
        "seed": config.get("seed", config.get("randomSeed", "")),
        "replay_path": str(path),
        "step_idx": step_idx,
        "obs_step": gobs.get("step", step_idx),
        "action_step_idx": step_idx + 1,
        "result": result,
        "team_reward": team_reward,
        "opp_reward": opp_reward,
        "width": width,
        "height": height,
        "south_bound": south,
        "north_bound": north,
        "scroll_counter": gobs.get("scrollCounter", ""),
        "scroll_start_interval": config.get("scrollStartInterval", ""),
        "scroll_end_interval": config.get("scrollEndInterval", ""),
        "scroll_ramp_steps": config.get("scrollRampSteps", ""),
        "factory_move_period": config.get("factoryMovePeriod", ""),
        "factory_jump_cooldown_cfg": jump_cd_cfg,
        "factory_build_cooldown_cfg": config.get("factoryBuildCooldown", ""),
        "factory_alive": 1,
        "factory_uid": factory_uid,
        "factory_col": factory_col,
        "factory_row": factory_row,
        "factory_gap": factory_gap,
        "factory_energy": factory_energy,
        "f_move_cd": f_move_cd,
        "f_jump_cd": f_jump_cd,
        "f_build_cd": f_build_cd,
        "factory_on_own_mine": int((factory_col, factory_row) in owned_mines),
        "factory_on_mining_node": int((factory_col, factory_row) in mining_nodes),
        **stats,
        "north_neighbor_uid": north_neighbor_uid,
        "north_neighbor_type": north_neighbor_type,
        "north_neighbor_energy": north_neighbor_energy,
        "north_neighbor_is_friendly_support": north_neighbor_is_friendly_support,
        "side_miner_count": side_miner_count,
        "north_miner_count": north_miner_count,
        "south_miner_count": south_miner_count,
        "worker_near_factory_count": worker_near_factory_count,
        "opp_factory_alive": opp_factory_alive,
        "opp_factory_col": opp_factory_col,
        "opp_factory_row": opp_factory_row,
        "opp_factory_gap": opp_factory_gap,
        "opp_factory_energy": opp_factory_energy,
        "opp_support_count": opp_count,
        "opp_support_energy": opp_energy,
        "collision_tiebreak_bad": collision_tiebreak_bad,
        "enemy_factory_near": enemy_factory_near,
        "enemy_factory_threat_count": threat_count,
        "enemy_factory_jump_threat_count": jump_threat_count,
        **phase,
        **known_route,
        **oracle_route,
        "can_move_north": can_moves["NORTH"],
        "can_move_east": can_moves["EAST"],
        "can_move_west": can_moves["WEST"],
        "can_move_south": can_moves["SOUTH"],
        "can_jump_north": can_jumps["NORTH"],
        "can_jump_east": can_jumps["EAST"],
        "can_jump_west": can_jumps["WEST"],
        "can_jump_south": can_jumps["SOUTH"],
        "north_wall_blocked": north_wall_blocked,
        "north_cell_occupied": north_cell_occupied,
        "north_cell_occupied_by": all_positions.get(north_cell, ""),
        "jump_north_landing_occupied": jump_north_landing_occupied,
        "jump_north_landing_wall_full": jump_north_landing_wall_full,
        "factory_action": factory_action,
        "factory_action_head": head,
        "factory_action_dir": direction,
        "factory_action_dest_col": dest_col,
        "factory_action_dest_row": dest_row,
        "factory_action_row_delta": dest_row - factory_row,
        "factory_action_is_build": int(factory_action.startswith("BUILD_")),
        "factory_action_is_transfer": int(factory_action.startswith("TRANSFER_")),
        "factory_action_is_remove": int(factory_action.startswith("REMOVE_")),
        "factory_action_is_jump": int(factory_action.startswith("JUMP_")),
        "factory_action_is_south": int(factory_action in {"SOUTH", "JUMP_SOUTH"}),
        "factory_action_is_lateral": int(factory_action in {"EAST", "WEST", "JUMP_EAST", "JUMP_WEST"}),
        "support_action_count": len(support_actions),
        "support_build_count": support_heads["BUILD"],
        "support_transfer_count": support_heads["TRANSFER"],
        "support_remove_count": support_heads["REMOVE"],
        "support_transform_count": support_heads["TRANSFORM"],
        "all_actions_compact": compact_counts(action_counts),
        "r1_transfer_candidate": r1_candidate,
        "r1_transfer_fired": int(factory_action == "TRANSFER_NORTH"),
        "r1_target_type": north_neighbor_type if north_neighbor_is_friendly_support else "",
        "r1_target_energy": north_neighbor_energy if north_neighbor_is_friendly_support else "",
        "mine_build_candidate_north": mine_candidate,
        "mine_relaxed_candidate_north": mine_relaxed_candidate_north,
        "mine_relaxed_candidate_side": mine_relaxed_candidate_side,
        "mine_relaxed_candidate_any": mine_relaxed_candidate_any,
        "mine_relaxed_candidate_dirs": ";".join(relaxed_dirs),
        "mine_shadow_blocked_by_energy": mine_shadow_blocked_by_energy,
        "mine_shadow_blocked_by_gap": mine_shadow_blocked_by_gap,
        "mine_shadow_blocked_by_build_cd": mine_shadow_blocked_by_build_cd,
        "mine_shadow_blocked_by_existing_miner": mine_shadow_blocked_by_existing_miner,
        "mine_shadow_blocked_by_occupied": mine_shadow_blocked_by_occupied,
        "mine_shadow_blocked_by_wall": mine_shadow_blocked_by_wall,
        "scout_build_candidate": scout_candidate,
        "worker_build_candidate": worker_candidate,
        "late_spend_action": late_spend,
        "late_factory_spend_action": late_factory_spend,
        "late_support_spend_count": late_support_spend,
        "bad_any": int(bool(labels)),
        "bad_labels": ";".join(labels),
        "bad_phase_spend": int("bad_phase_spend" in labels),
        "bad_final_build": int("bad_final_build" in labels),
        "bad_final_transfer": int("bad_final_transfer" in labels),
        "bad_final_remove": int("bad_final_remove" in labels),
        "bad_final_south_action": int("bad_final_south_action" in labels),
        "bad_lateral_jcd_lock_risk": int("bad_lateral_jcd_lock_risk" in labels),
        "bad_route_blocked": int("bad_route_blocked" in labels),
        "bad_only_south_escape": int("bad_only_south_escape" in labels),
        "bad_support_void": int("bad_support_void" in labels),
        "bad_support_blocking_factory": int("bad_support_blocking_factory" in labels),
        "bad_collision_tiebreak": int("bad_collision_tiebreak" in labels),
        "bad_high_factory_low_support_energy": int("bad_high_factory_low_support_energy" in labels),
        "bad_mine_roi_low_lifetime": int("bad_mine_roi_low_lifetime" in labels),
        "death_next_step": int(death_step == step_idx + 1),
        "factory_dead_now": 0,
    }
    return row


def episode_summary(
    data: dict[str, Any],
    path: Path,
    source_group: str,
    agent_label: str,
    team_index: int,
    step_rows: list[dict[str, Any]],
    death_step: int | None,
    death_cause: str,
) -> dict[str, Any]:
    steps = data.get("steps") or []
    config = data.get("configuration", {})
    names = names_for(data)
    rewards = data.get("rewards") or []
    result, team_reward, opp_reward = result_for(rewards, team_index)
    final_robots = global_robots(steps[-1]) if steps else {}
    _, final_factory = factory_for_owner(final_robots, team_index)
    final_stats = robot_counts(final_robots, team_index)
    max_factory_energy = 0
    max_support_energy = 0
    min_gap_after_scroll: int | None = None
    for step in steps:
        robots = global_robots(step)
        south, _ = global_bounds(step)
        _, factory = factory_for_owner(robots, team_index)
        support_energy, _ = support_energy_count(robots, team_index)
        max_support_energy = max(max_support_energy, support_energy)
        if factory is not None:
            max_factory_energy = max(max_factory_energy, int(factory[3]))
            if south > 0:
                gap = int(factory[2]) - south
                min_gap_after_scroll = gap if min_gap_after_scroll is None else min(min_gap_after_scroll, gap)

    phase_counts = Counter(str(row["phase"]) for row in step_rows)
    phase_spend_counts = Counter(str(row["phase"]) for row in step_rows if int(row["late_spend_action"]))
    bad_counts: Counter[str] = Counter()
    for row in step_rows:
        for label in str(row["bad_labels"]).split(";"):
            if label:
                bad_counts[label] += 1

    def first_step(predicate) -> Any:
        for row in step_rows:
            if predicate(row):
                return row["step_idx"]
        return ""

    return {
        "source_group": source_group,
        "agent_label": agent_label,
        "team_name": names[team_index] if len(names) > team_index else str(team_index),
        "team_index": team_index,
        "opponent": names[1 - team_index] if len(names) > 1 else "",
        "episode_id": data.get("info", {}).get("EpisodeId") or path.stem,
        "seed": config.get("seed", config.get("randomSeed", "")),
        "result": result,
        "team_reward": team_reward,
        "opp_reward": opp_reward,
        "steps": len(steps),
        "death_step": "" if death_step is None else death_step,
        "death_cause": death_cause,
        "final_factory_row": "" if final_factory is None else final_factory[2],
        "final_factory_energy": "" if final_factory is None else final_factory[3],
        "final_support_count": final_stats["support_count"],
        "final_support_energy": final_stats["support_energy"],
        "max_factory_energy": max_factory_energy,
        "max_support_energy": max_support_energy,
        "min_gap_after_scroll": "" if min_gap_after_scroll is None else min_gap_after_scroll,
        "phase_counts": compact_counts(phase_counts),
        "phase_spend_counts": compact_counts(phase_spend_counts),
        "bad_label_counts": compact_counts(bad_counts),
        "first_bad_step": first_step(lambda row: int(row["bad_any"])),
        "first_final_kick_step": first_step(lambda row: row["phase"] == "FINAL_KICK"),
        "first_miner_step": first_step(lambda row: str(row["factory_action"]).startswith("BUILD_MINER")),
        "first_worker_step": first_step(lambda row: str(row["factory_action"]).startswith("BUILD_WORKER")),
        "first_transfer_step": first_step(lambda row: str(row["factory_action"]).startswith("TRANSFER_")),
        "first_side_miner_step": first_step(
            lambda row: str(row["factory_action"]).startswith("BUILD_MINER")
            and row["factory_action"] in {"BUILD_MINER_EAST", "BUILD_MINER_WEST", "BUILD_MINER"}
        ),
        "late_spend_count": sum(int(row["late_spend_action"]) for row in step_rows),
        "late_build_count": sum(1 for row in step_rows if row["phase"] in {"PRESSURE", "FINAL_KICK"} and str(row["factory_action"]).startswith("BUILD_")),
        "late_transfer_count": sum(1 for row in step_rows if row["phase"] in {"PRESSURE", "FINAL_KICK"} and str(row["factory_action"]).startswith("TRANSFER_")),
        "route_blocked_steps": sum(int(row["bad_route_blocked"]) for row in step_rows),
        "only_south_escape_steps": sum(int(row["bad_only_south_escape"]) for row in step_rows),
        "lateral_jcd_lock_events": sum(int(row["bad_lateral_jcd_lock_risk"]) for row in step_rows),
        "support_void_pressure_steps": sum(int(row["bad_support_void"]) for row in step_rows),
        "replay_path": str(path),
    }


def team_indices(args: argparse.Namespace, data: dict[str, Any]) -> list[int]:
    if getattr(args, "episode_team_indices", None):
        episode_id = str(data.get("info", {}).get("EpisodeId") or "")
        if episode_id in args.episode_team_indices:
            return [args.episode_team_indices[episode_id]]
    if args.all_sides:
        return [0, 1]
    if args.team_index is not None:
        return [int(args.team_index)]
    names = names_for(data)
    if args.team_name:
        if args.team_name not in names:
            return []
        return [names.index(args.team_name)]
    return [0]


def analyze_replay(path: Path, args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(path.read_text())
    steps = data.get("steps") or []
    if len(steps) < 2:
        return [], []
    all_step_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    for team_index in team_indices(args, data):
        death_step, death_cause = death_info(data, team_index)
        side_rows: list[dict[str, Any]] = []
        for step_idx in range(len(steps) - 1):
            row = row_for_step(
                data, path, args.group, args.agent_label, team_index, step_idx,
                death_step, death_cause, args.known_mode, args.route_depth,
            )
            if row is not None:
                side_rows.append(row)
        all_step_rows.extend(side_rows)
        episode_rows.append(
            episode_summary(data, path, args.group, args.agent_label, team_index, side_rows, death_step, death_cause)
        )
    return all_step_rows, episode_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
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
    parser.add_argument("--known-mode", choices=("local", "filled", "off"), default="filled")
    parser.add_argument("--route-depth", type=int, default=20)
    parser.add_argument("--allow-schema-warnings", action="store_true")
    args = parser.parse_args()
    args.episode_team_indices = {}
    if args.episodes_csv is not None:
        with args.episodes_csv.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                episode_id = str(row.get("id") or row.get("episode_id") or "")
                team_index = str(row.get("team_index") or "").strip()
                if episode_id and team_index != "":
                    args.episode_team_indices[episode_id] = int(team_index)

    replay_set = set(args.replay_dir.rglob("episode-*-replay.json"))
    replay_set.update(args.replay_dir.rglob("*-replay.json"))
    replays = sorted(replay_set)
    if args.max_replays is not None:
        replays = replays[: args.max_replays]
    if not replays:
        raise SystemExit(f"No replay JSONs found under {args.replay_dir}")

    step_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    for path in replays:
        rows, episodes = analyze_replay(path, args)
        step_rows.extend(rows)
        episode_rows.extend(episodes)

    bad_rows = [{field: row.get(field, "") for field in BAD_FIELDS} for row in step_rows if int(row["bad_any"])]
    prefix = args.out_prefix
    write_csv(Path(f"{prefix}_steps.csv"), step_rows, STEP_FIELDS)
    write_csv(Path(f"{prefix}_bad_states.csv"), bad_rows, BAD_FIELDS)
    write_csv(Path(f"{prefix}_episodes.csv"), episode_rows, EPISODE_FIELDS)

    result_counts = Counter(row["result"] for row in episode_rows)
    death_counts = Counter(row["death_cause"] for row in episode_rows)
    bad_counts = Counter()
    for row in bad_rows:
        for label in str(row["bad_labels"]).split(";"):
            if label:
                bad_counts[label] += 1
    print(f"replays={len(replays)} sides={len(episode_rows)} steps={len(step_rows)} bad_steps={len(bad_rows)}")
    print("results", dict(sorted(result_counts.items())))
    print("death_causes", dict(sorted(death_counts.items())))
    print("top_bad", bad_counts.most_common(12))
    print(f"wrote {prefix}_steps.csv")
    print(f"wrote {prefix}_bad_states.csv")
    print(f"wrote {prefix}_episodes.csv")


if __name__ == "__main__":
    main()
