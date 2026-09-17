#!/usr/bin/env python3
"""Join route-quality and reservation probes into route-owner shadow rows.

This is deliberately read-only. It consumes CSVs emitted by
probe_phase_route_quality.py and probe_reservation_intent.py, then asks a
smaller question than either source can answer alone:

When the factory has a ready route-progress cell, who "owns" that cell, what is
currently occupying it, and what happens in the next one or two rows?
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}


ROW_FIELDS = [
    "source_group",
    "agent_label",
    "team_name",
    "team_index",
    "opponent",
    "episode_id",
    "seed",
    "replay_path",
    "step_idx",
    "result",
    "phase",
    "factory_col",
    "factory_row",
    "factory_gap",
    "factory_energy",
    "f_move_cd",
    "f_jump_cd",
    "support_count",
    "support_energy",
    "factory_action",
    "factory_action_dir",
    "factory_action_dest_col",
    "factory_action_dest_row",
    "route_first_action",
    "route_action_source",
    "route_bucket",
    "alternate_route_found",
    "owned_cell_source",
    "owned_cell_col",
    "owned_cell_row",
    "owned_cell_is_adjacent",
    "owned_cell_occupant_uid",
    "owned_cell_occupant_type",
    "owned_cell_occupant_energy",
    "occupant_action",
    "occupant_dest_col",
    "occupant_dest_row",
    "occupant_vacates",
    "occupant_transforms",
    "owner_conflict_class",
    "route_owner_intent",
    "factory_route_commit",
    "jump_cd_cost",
    "death_next_step",
    "route_blocked_now",
    "route_blocked_t1",
    "route_blocked_t2",
    "gap_delta_t1",
    "gap_delta_t2",
    "support_count_delta_t1",
    "support_count_delta_t2",
    "support_energy_delta_t1",
    "support_energy_delta_t2",
    "trigger_support_lateral_vacate_candidate",
    "trigger_reason",
]


SUMMARY_FIELDS = [
    "source_group",
    "agent_label",
    "phase",
    "route_owner_intent",
    "owner_conflict_class",
    "rows",
    "episodes",
    "loss_rows",
    "death_next_rows",
    "route_blocked_now_rows",
    "route_blocked_t1_rows",
    "route_blocked_t2_rows",
    "trigger_rows",
    "mean_gap_delta_t1",
    "mean_gap_delta_t2",
    "mean_support_energy_delta_t1",
    "mean_support_energy_delta_t2",
]


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def number(row: dict[str, str], key: str, default: float = 0.0) -> float:
    raw = str(row.get(key, "")).strip()
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def int_text(value: float | int | str) -> str:
    if value == "":
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)


def action_dir(action: str) -> str:
    if action in DIRS:
        return action
    if action.startswith("JUMP_"):
        direction = action.split("_", 1)[1]
        return direction if direction in DIRS else ""
    if "_" in action:
        tail = action.rsplit("_", 1)[1]
        return tail if tail in DIRS else ""
    return ""


def is_route_action(action: str) -> bool:
    return action in DIRS or action.startswith("JUMP_")


def action_dest(col: int, row: int, action: str) -> tuple[int, int]:
    direction = action_dir(action)
    if not direction:
        return col, row
    dc, dr = OFFSETS[direction]
    if action.startswith("JUMP_"):
        return col + 2 * dc, row + 2 * dr
    return col + dc, row + dr


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def route_first_action(phase_row: dict[str, str]) -> tuple[str, str, str]:
    if truthy(phase_row.get("rq_known_main_found")):
        return (
            phase_row.get("rq_known_main_first_action", ""),
            "known_main",
            phase_row.get("rq_known_bucket", ""),
        )
    if truthy(phase_row.get("rq_oracle_main_found")):
        return (
            phase_row.get("rq_oracle_main_first_action", ""),
            "oracle_main",
            phase_row.get("rq_oracle_bucket", ""),
        )
    return "", "", ""


def route_ready(phase_row: dict[str, str], action: str) -> bool:
    if not is_route_action(action):
        return False
    if number(phase_row, "f_move_cd", 99) > 0:
        return False
    if action.startswith("JUMP_") and number(phase_row, "f_jump_cd", 99) > 0:
        return False
    direction = action_dir(action).lower()
    if action.startswith("JUMP_"):
        return truthy(phase_row.get(f"can_jump_{direction}"))
    return truthy(phase_row.get(f"can_move_{direction}"))


def phase_key(row: dict[str, str], step_delta: int = 0) -> tuple[str, str, int]:
    return (
        row.get("replay_path", ""),
        row.get("team_index", ""),
        int(number(row, "step_idx")) + step_delta,
    )


def deltas(
    phase_row: dict[str, str],
    phase_by_key: dict[tuple[str, str, int], dict[str, str]],
    step_delta: int,
) -> dict[str, str]:
    future = phase_by_key.get(phase_key(phase_row, step_delta))
    if not future:
        return {
            f"route_blocked_t{step_delta}": "",
            f"gap_delta_t{step_delta}": "",
            f"support_count_delta_t{step_delta}": "",
            f"support_energy_delta_t{step_delta}": "",
        }
    return {
        f"route_blocked_t{step_delta}": int(truthy(future.get("bad_route_blocked"))),
        f"gap_delta_t{step_delta}": int_text(
            number(future, "factory_gap") - number(phase_row, "factory_gap")
        ),
        f"support_count_delta_t{step_delta}": int_text(
            number(future, "support_count") - number(phase_row, "support_count")
        ),
        f"support_energy_delta_t{step_delta}": int_text(
            number(future, "support_energy") - number(phase_row, "support_energy")
        ),
    }


def occupant_for_owned_cell(
    phase_row: dict[str, str],
    reservation_row: dict[str, str],
    owned_cell: tuple[int, int],
    route_action: str,
) -> dict[str, str]:
    factory_dest = (
        int(number(reservation_row, "factory_action_dest_col", -999)),
        int(number(reservation_row, "factory_action_dest_row", -999)),
    )
    factory_self = reservation_row.get("factory_uid", "")
    if owned_cell == factory_dest and truthy(reservation_row.get("factory_dest_occupied_by_friendly")):
        uid = reservation_row.get("factory_dest_occupant_uid", "")
        return {
            "owned_cell_occupant_uid": uid,
            "owned_cell_occupant_type": reservation_row.get("factory_dest_occupant_type", ""),
            "owned_cell_occupant_energy": "",
            "occupant_action": reservation_row.get("factory_dest_occupant_action", ""),
            "occupant_dest_col": reservation_row.get("factory_dest_occupant_dest_col", ""),
            "occupant_dest_row": reservation_row.get("factory_dest_occupant_dest_row", ""),
            "occupant_vacates": int(truthy(reservation_row.get("factory_dest_occupant_vacates"))),
            "occupant_transforms": int(
                truthy(reservation_row.get("factory_dest_occupant_transforms"))
            ),
        }

    direction = action_dir(route_action)
    adjacent = not route_action.startswith("JUMP_")
    if direction == "NORTH" and adjacent:
        uid = phase_row.get("north_neighbor_uid") or reservation_row.get("north_blocker_uid", "")
        if uid and uid != factory_self:
            return {
                "owned_cell_occupant_uid": uid,
                "owned_cell_occupant_type": (
                    phase_row.get("north_neighbor_type")
                    or reservation_row.get("north_blocker_type", "")
                ),
                "owned_cell_occupant_energy": phase_row.get("north_neighbor_energy", ""),
                "occupant_action": reservation_row.get("north_blocker_action", ""),
                "occupant_dest_col": "",
                "occupant_dest_row": "",
                "occupant_vacates": int(truthy(reservation_row.get("north_blocker_vacates"))),
                "occupant_transforms": int(
                    reservation_row.get("north_blocker_action", "") == "TRANSFORM"
                ),
            }

    if direction == "NORTH" and route_action.startswith("JUMP_"):
        if truthy(reservation_row.get("jump_landing_occupied")):
            return {
                "owned_cell_occupant_uid": "",
                "owned_cell_occupant_type": reservation_row.get("jump_landing_occupant_type", ""),
                "owned_cell_occupant_energy": "",
                "occupant_action": "",
                "occupant_dest_col": "",
                "occupant_dest_row": "",
                "occupant_vacates": "",
                "occupant_transforms": "",
            }

    return {
        "owned_cell_occupant_uid": "",
        "owned_cell_occupant_type": "",
        "owned_cell_occupant_energy": "",
        "occupant_action": "",
        "occupant_dest_col": "",
        "occupant_dest_row": "",
        "occupant_vacates": 0,
        "occupant_transforms": 0,
    }


def conflict_class(reservation_row: dict[str, str], occ: dict[str, str]) -> str:
    occupied = bool(occ.get("owned_cell_occupant_uid") or occ.get("owned_cell_occupant_type"))
    if truthy(reservation_row.get("enemy_vertex_conflict_t1")) or truthy(
        reservation_row.get("enemy_edge_swap_t1")
    ):
        return "enemy_contest"
    if truthy(reservation_row.get("friendly_edge_swap_t1")):
        return "edge_swap"
    if truthy(occ.get("occupant_transforms")):
        return "transform_vacate_ok"
    if occupied and truthy(occ.get("occupant_vacates")):
        return "friendly_vacate_ok"
    if occupied:
        return "friendly_hold_block"
    if truthy(reservation_row.get("friendly_vertex_conflict_t1")) or number(
        reservation_row, "reserved_next_conflict_count"
    ) > 0:
        return "reservation_collision"
    return "clean"


def owner_intent(phase_row: dict[str, str], reservation_row: dict[str, str], conflict: str) -> str:
    if conflict == "transform_vacate_ok":
        return "mine_transform"
    if conflict == "friendly_vacate_ok":
        return "support_vacate"
    if truthy(reservation_row.get("factory_dest_occupant_sacrificed")):
        return "sacrifice"
    if conflict == "friendly_hold_block":
        return "support_hold"
    if truthy(phase_row.get("bad_route_blocked")) or number(phase_row, "factory_gap", 99) <= 6:
        return "route_recovery"
    if is_route_action(reservation_row.get("factory_action", "")):
        return "factory_progress"
    return "unknown"


def trigger_candidate(
    phase_row: dict[str, str],
    reservation_row: dict[str, str],
    route_action: str,
    conflict: str,
    occ: dict[str, str],
) -> tuple[int, str]:
    if conflict != "friendly_hold_block":
        return 0, ""
    if route_action != "NORTH":
        return 0, ""
    if truthy(reservation_row.get("enemy_vertex_conflict_t1")):
        return 0, ""
    if occ.get("owned_cell_occupant_type") not in {"scout", "worker"}:
        return 0, ""
    action = occ.get("occupant_action", "")
    if action not in {"", "IDLE"}:
        return 0, ""
    if number(phase_row, "f_move_cd", 99) > 0:
        return 0, ""
    if truthy(occ.get("occupant_transforms")):
        return 0, ""
    return 1, "ready_north_route_idle_support_blocker"


def row_for(
    phase_row: dict[str, str],
    reservation_row: dict[str, str],
    phase_by_key: dict[tuple[str, str, int], dict[str, str]],
) -> dict[str, str] | None:
    factory_action = reservation_row.get("factory_action", "") or phase_row.get("factory_action", "")
    route_action, route_source, route_bucket = route_first_action(phase_row)
    owned_action = ""
    owned_source = ""

    if is_route_action(factory_action):
        owned_action = factory_action
        owned_source = "actual_factory_route"
    elif route_ready(phase_row, route_action):
        owned_action = route_action
        owned_source = "shadow_ready_route"
    else:
        return None

    col = int(number(phase_row, "factory_col"))
    row = int(number(phase_row, "factory_row"))
    owned_cell = action_dest(col, row, owned_action)
    occ = occupant_for_owned_cell(phase_row, reservation_row, owned_cell, owned_action)
    conflict = conflict_class(reservation_row, occ)
    intent = owner_intent(phase_row, reservation_row, conflict)
    trigger, trigger_reason = trigger_candidate(
        phase_row, reservation_row, owned_action, conflict, occ
    )
    t1 = deltas(phase_row, phase_by_key, 1)
    t2 = deltas(phase_row, phase_by_key, 2)
    route_dir = action_dir(owned_action)

    out = {
        "source_group": phase_row.get("source_group", ""),
        "agent_label": phase_row.get("agent_label", ""),
        "team_name": phase_row.get("team_name", ""),
        "team_index": phase_row.get("team_index", ""),
        "opponent": phase_row.get("opponent", ""),
        "episode_id": phase_row.get("episode_id", ""),
        "seed": phase_row.get("seed", ""),
        "replay_path": phase_row.get("replay_path", ""),
        "step_idx": phase_row.get("step_idx", ""),
        "result": phase_row.get("result", ""),
        "phase": phase_row.get("phase", ""),
        "factory_col": phase_row.get("factory_col", ""),
        "factory_row": phase_row.get("factory_row", ""),
        "factory_gap": phase_row.get("factory_gap", ""),
        "factory_energy": phase_row.get("factory_energy", ""),
        "f_move_cd": phase_row.get("f_move_cd", ""),
        "f_jump_cd": phase_row.get("f_jump_cd", ""),
        "support_count": phase_row.get("support_count", ""),
        "support_energy": phase_row.get("support_energy", ""),
        "factory_action": factory_action,
        "factory_action_dir": action_dir(factory_action),
        "factory_action_dest_col": reservation_row.get("factory_action_dest_col", ""),
        "factory_action_dest_row": reservation_row.get("factory_action_dest_row", ""),
        "route_first_action": route_action,
        "route_action_source": route_source,
        "route_bucket": route_bucket,
        "alternate_route_found": int(
            truthy(phase_row.get("rq_known_closer_found"))
            or truthy(phase_row.get("rq_oracle_closer_found"))
        ),
        "owned_cell_source": owned_source,
        "owned_cell_col": owned_cell[0],
        "owned_cell_row": owned_cell[1],
        "owned_cell_is_adjacent": int(not owned_action.startswith("JUMP_")),
        **occ,
        "owner_conflict_class": conflict,
        "route_owner_intent": intent,
        "factory_route_commit": f"{owned_action}:{owned_cell[0]},{owned_cell[1]}:{route_bucket}",
        "jump_cd_cost": int(owned_action.startswith("JUMP_")),
        "death_next_step": int(
            truthy(phase_row.get("death_next_step"))
            or truthy(reservation_row.get("death_next_step"))
        ),
        "route_blocked_now": int(truthy(phase_row.get("bad_route_blocked"))),
        **t1,
        **t2,
        "trigger_support_lateral_vacate_candidate": trigger,
        "trigger_reason": trigger_reason,
    }
    return {field: out.get(field, "") for field in ROW_FIELDS}


def write_csv(path: Path, rows: Iterable[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    stats: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
    for row in rows:
        key = (
            row["source_group"],
            row["agent_label"],
            row["phase"],
            row["route_owner_intent"],
            row["owner_conflict_class"],
        )
        if key not in stats:
            stats[key] = defaultdict(float)
            stats[key]["source_group"] = key[0]
            stats[key]["agent_label"] = key[1]
            stats[key]["phase"] = key[2]
            stats[key]["route_owner_intent"] = key[3]
            stats[key]["owner_conflict_class"] = key[4]
            stats[key]["episodes_set"] = set()
        stat = stats[key]
        stat["rows"] += 1
        stat["episodes_set"].add(row["episode_id"])
        if row.get("result") == "loss":
            stat["loss_rows"] += 1
        for key_flag, field_name in (
            ("death_next_step", "death_next_rows"),
            ("route_blocked_now", "route_blocked_now_rows"),
            ("route_blocked_t1", "route_blocked_t1_rows"),
            ("route_blocked_t2", "route_blocked_t2_rows"),
            ("trigger_support_lateral_vacate_candidate", "trigger_rows"),
        ):
            if truthy(row.get(key_flag)):
                stat[field_name] += 1
        for numeric_field in (
            "gap_delta_t1",
            "gap_delta_t2",
            "support_energy_delta_t1",
            "support_energy_delta_t2",
        ):
            if row.get(numeric_field) != "":
                stat[f"{numeric_field}_sum"] += number(row, numeric_field)
                stat[f"{numeric_field}_n"] += 1

    out_rows = []
    for stat in stats.values():
        rows_count = int(stat["rows"])
        out = {field: stat.get(field, 0) for field in SUMMARY_FIELDS}
        out["rows"] = rows_count
        out["episodes"] = len(stat.pop("episodes_set"))
        for mean_field, sum_field, n_field in (
            ("mean_gap_delta_t1", "gap_delta_t1_sum", "gap_delta_t1_n"),
            ("mean_gap_delta_t2", "gap_delta_t2_sum", "gap_delta_t2_n"),
            (
                "mean_support_energy_delta_t1",
                "support_energy_delta_t1_sum",
                "support_energy_delta_t1_n",
            ),
            (
                "mean_support_energy_delta_t2",
                "support_energy_delta_t2_sum",
                "support_energy_delta_t2_n",
            ),
        ):
            out[mean_field] = (
                float(stat.get(sum_field, 0.0)) / float(stat.get(n_field, 0.0))
                if stat.get(n_field)
                else ""
            )
        out_rows.append(out)
    out_rows.sort(
        key=lambda r: (
            -int(r.get("death_next_rows") or 0),
            -int(r.get("trigger_rows") or 0),
            -int(r.get("route_blocked_t1_rows") or 0),
            -int(r.get("rows") or 0),
        )
    )
    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase-steps", type=Path, required=True)
    parser.add_argument("--reservation-steps", type=Path, required=True)
    parser.add_argument("--out-prefix", type=Path, required=True)
    args = parser.parse_args()

    phase_rows = read_csv(args.phase_steps)
    reservation_rows = read_csv(args.reservation_steps)
    phase_by_key = {phase_key(row): row for row in phase_rows}
    reservation_by_key = {phase_key(row): row for row in reservation_rows}

    rows: list[dict[str, str]] = []
    missing_reservation = 0
    for phase_row in phase_rows:
        reservation_row = reservation_by_key.get(phase_key(phase_row))
        if reservation_row is None:
            missing_reservation += 1
            continue
        out = row_for(phase_row, reservation_row, phase_by_key)
        if out is not None:
            rows.append(out)

    summary_rows = summarize(rows)
    row_path = Path(f"{args.out_prefix}_rows.csv")
    summary_path = Path(f"{args.out_prefix}_summary.csv")
    write_csv(row_path, rows, ROW_FIELDS)
    write_csv(summary_path, summary_rows, SUMMARY_FIELDS)

    conflict_counts = Counter(row["owner_conflict_class"] for row in rows)
    trigger_count = sum(int(row["trigger_support_lateral_vacate_candidate"]) for row in rows)
    print(
        f"phase_rows={len(phase_rows)} reservation_rows={len(reservation_rows)} "
        f"shadow_rows={len(rows)} missing_reservation={missing_reservation}"
    )
    print("top_conflicts", conflict_counts.most_common(8))
    print(f"trigger_support_lateral_vacate_candidate={trigger_count}")
    print(f"wrote {row_path}")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
