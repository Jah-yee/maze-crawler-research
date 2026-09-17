#!/usr/bin/env python3
"""Shadow factory action safety-rank probe from phase-route step CSVs.

This is an approximate, read-only ranker. It uses existing probe columns rather
than replay-level global positions, so it should be used for candidate
selection and failure triage, not as proof of a deployable policy.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_STEPS = [
    "reports/probes/active_v51_53414790_phase_route_steps.csv",
    "reports/probes/active_v67_53414814_phase_route_steps.csv",
    "reports/probes/hist_v51_53412795_phase_route_steps.csv",
    "reports/probes/hist_v99_53412815_phase_route_steps.csv",
]

OUT_FIELDS = [
    "source_group",
    "agent_label",
    "episode_id",
    "step_idx",
    "phase",
    "result",
    "factory_gap",
    "factory_energy",
    "support_count",
    "support_energy",
    "factory_action",
    "actual_rank",
    "best_action",
    "best_score",
    "actual_score",
    "rank_gap",
    "recovery_class",
    "terminal_risk",
    "route_risk",
    "support_blocker_vacate_available",
    "reserved_vertex_conflict_t1",
    "enemy_conflict_t1",
    "resource_fragility",
    "death_next_step",
    "bad_labels",
]


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def num(row: dict[str, str], key: str, default: float = 0.0) -> float:
    raw = str(row.get(key, "")).strip()
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def legal_actions(row: dict[str, str]) -> list[str]:
    actions = ["IDLE"]
    for d in ("NORTH", "EAST", "WEST", "SOUTH"):
        if truthy(row.get(f"can_move_{d.lower()}")):
            actions.append(d)
    for d in ("NORTH", "EAST", "WEST", "SOUTH"):
        if truthy(row.get(f"can_jump_{d.lower()}")):
            actions.append(f"JUMP_{d}")
    if truthy(row.get("mine_build_candidate_north")):
        actions.append("BUILD_MINER_NORTH")
    if truthy(row.get("scout_build_candidate")):
        actions.append("BUILD_SCOUT")
    if truthy(row.get("worker_build_candidate")):
        actions.append("BUILD_WORKER")
    if truthy(row.get("r1_transfer_candidate")):
        actions.append("TRANSFER_NORTH")
    return actions


def row_delta(action: str) -> int:
    if action == "NORTH":
        return 1
    if action == "SOUTH":
        return -1
    if action == "JUMP_NORTH":
        return 2
    if action == "JUMP_SOUTH":
        return -2
    return 0


def is_spend(action: str) -> bool:
    return action.startswith(("BUILD_", "TRANSFER_", "REMOVE_")) or action == "TRANSFORM"


def support_conflict(row: dict[str, str], action: str) -> bool:
    if action in {"NORTH", "BUILD_MINER_NORTH", "BUILD_SCOUT", "BUILD_WORKER", "TRANSFER_NORTH"}:
        return truthy(row.get("north_cell_occupied")) or truthy(row.get("north_neighbor_is_friendly_support"))
    if action == "JUMP_NORTH":
        return truthy(row.get("jump_north_landing_occupied"))
    return False


def enemy_conflict(row: dict[str, str], action: str) -> bool:
    # Existing probe threat counts are computed for the actual action, so this is
    # a conservative approximation: only hard-penalize the actual action.
    actual = row.get("factory_action", "")
    if action != actual:
        return False
    return truthy(row.get("enemy_factory_threat_count")) or truthy(row.get("enemy_factory_jump_threat_count"))


def score_action(row: dict[str, str], action: str) -> float:
    phase = row.get("phase", "")
    gap = num(row, "factory_gap", 99)
    result = row.get("result", "")
    team_reward = num(row, "team_reward")
    support_energy = num(row, "support_energy")
    factory_energy = num(row, "factory_energy")
    route_score = num(row, "rq_oracle_score")
    f_move_cd = num(row, "f_move_cd")
    f_jump_cd = num(row, "f_jump_cd")
    f_build_cd = num(row, "f_build_cd")

    score = 0.0
    score += 5.0 * row_delta(action)
    score += route_score
    if action == row.get("rq_oracle_main_first_action"):
        score += 4.0
    if action == row.get("rq_oracle_closer_first_action"):
        score += 2.0

    if action.startswith("JUMP_"):
        score += 2.0
        if f_jump_cd > 0:
            score -= 8.0
    if action in {"NORTH", "EAST", "WEST", "SOUTH"} and f_move_cd > 1:
        score -= 8.0
    if action.startswith("BUILD_") and f_build_cd > 1:
        score -= 8.0

    stable_win_context = result == "win" and team_reward > 0 and factory_energy >= 2000 and gap > 6
    spend_penalty = 2.0 if stable_win_context else 7.0
    final_build_penalty = 4.0 if stable_win_context else 10.0
    if phase in {"PRESSURE", "FINAL_KICK"} and is_spend(action):
        score -= spend_penalty
    if phase == "FINAL_KICK" and action.startswith("BUILD_"):
        score -= final_build_penalty
    if gap <= 4 and action in {"SOUTH", "JUMP_SOUTH"}:
        score -= 12.0
    if gap <= 3 and row_delta(action) > 0:
        score += 5.0
    if gap <= 2 and action == "JUMP_NORTH":
        score += 8.0

    if support_conflict(row, action):
        score -= 7.0 if stable_win_context else 12.0
    if enemy_conflict(row, action):
        score -= 15.0
    if (
        phase in {"PRESSURE", "FINAL_KICK"}
        and support_energy < 80
        and action in {"IDLE", "SOUTH", "JUMP_SOUTH"}
        and not stable_win_context
    ):
        score -= 3.0
    return score


def classify_recovery(row: dict[str, str], best_action: str, actual_score: float, best_score: float) -> str:
    gap = num(row, "factory_gap", 99)
    stable_win_context = (
        row.get("result") == "win"
        and num(row, "team_reward") > 0
        and num(row, "factory_energy") >= 2000
        and gap > 6
    )
    if stable_win_context and not truthy(row.get("death_next_step")):
        if truthy(row.get("bad_support_blocking_factory")):
            return "support_blocking_stable_win"
        if truthy(row.get("late_spend_action")):
            return "late_spend_stable_win"
        return "stable_win_monitor"
    if gap <= 4 or row.get("phase") == "FINAL_KICK":
        if best_score - actual_score >= 8:
            return "terminal_safety_commit"
        return "terminal_monitor"
    if truthy(row.get("bad_support_blocking_factory")):
        return "support_vacate_shadow"
    if truthy(row.get("bad_route_blocked")):
        return "route_recovery_shadow"
    if truthy(row.get("late_spend_action")):
        return "resource_gate_shadow"
    if best_action != row.get("factory_action", "") and best_score - actual_score >= 8:
        return "controller_rank_shadow"
    return "none"


def rank_row(row: dict[str, str]) -> dict[str, str]:
    actions = legal_actions(row)
    scored = sorted(((score_action(row, action), action) for action in actions), reverse=True)
    best_score, best_action = scored[0]
    actual = row.get("factory_action", "") or "IDLE"
    actual_score = score_action(row, actual)
    actual_rank = 1 + sum(1 for score, _ in scored if score > actual_score)
    rank_gap = best_score - actual_score
    recovery = classify_recovery(row, best_action, actual_score, best_score)
    terminal_risk = int(row.get("phase") == "FINAL_KICK" or num(row, "factory_gap", 99) <= 4)
    route_risk = int(truthy(row.get("bad_route_blocked")) or num(row, "rq_oracle_score") <= 1)
    support_blocker = int(
        truthy(row.get("bad_support_blocking_factory"))
        and (truthy(row.get("can_move_east")) or truthy(row.get("can_move_west")))
    )
    reserved_vertex = int(support_conflict(row, actual))
    enemy = int(enemy_conflict(row, actual))
    resource_fragility = int(
        row.get("phase") in {"PRESSURE", "FINAL_KICK"}
        and num(row, "factory_energy") >= 1000
        and num(row, "support_energy") < 100
    )
    return {
        "source_group": row.get("source_group", ""),
        "agent_label": row.get("agent_label", ""),
        "episode_id": row.get("episode_id", ""),
        "step_idx": row.get("step_idx", ""),
        "phase": row.get("phase", ""),
        "result": row.get("result", ""),
        "factory_gap": row.get("factory_gap", ""),
        "factory_energy": row.get("factory_energy", ""),
        "support_count": row.get("support_count", ""),
        "support_energy": row.get("support_energy", ""),
        "factory_action": actual,
        "actual_rank": actual_rank,
        "best_action": best_action,
        "best_score": f"{best_score:.2f}",
        "actual_score": f"{actual_score:.2f}",
        "rank_gap": f"{rank_gap:.2f}",
        "recovery_class": recovery,
        "terminal_risk": terminal_risk,
        "route_risk": route_risk,
        "support_blocker_vacate_available": support_blocker,
        "reserved_vertex_conflict_t1": reserved_vertex,
        "enemy_conflict_t1": enemy,
        "resource_fragility": resource_fragility,
        "death_next_step": row.get("death_next_step", "0"),
        "bad_labels": row.get("bad_labels", ""),
    }


def read_rows(paths: list[Path]):
    for path in paths:
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source_group") == "source_group":
                    continue
                yield row


def write_report(path: Path, out_rows: list[dict[str, str]]) -> None:
    by_source = defaultdict(list)
    class_counts = Counter()
    death_classes = Counter()
    for row in out_rows:
        by_source[(row["source_group"], row["agent_label"])].append(row)
        class_counts[row["recovery_class"]] += 1
        if truthy(row["death_next_step"]):
            death_classes[row["recovery_class"]] += 1

    lines = [
        "# Safety Rank Shadow Probe - 2026-06-06",
        "",
        "Approximate read-only ranker over existing phase-route step CSVs. It is for triage, not runtime policy.",
        "",
        "## Source Summary",
        "",
        "| Source | Agent | Rows | Rank gap >= 8 | Terminal safety | Support vacate | Route recovery | Resource gate | Death rows |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for (source, agent), rows in sorted(by_source.items()):
        high_gap = sum(float(r["rank_gap"]) >= 8 for r in rows)
        term = sum(r["recovery_class"] == "terminal_safety_commit" for r in rows)
        vacate = sum(r["recovery_class"] == "support_vacate_shadow" for r in rows)
        route = sum(r["recovery_class"] == "route_recovery_shadow" for r in rows)
        resource = sum(r["recovery_class"] == "resource_gate_shadow" for r in rows)
        deaths = sum(truthy(r["death_next_step"]) for r in rows)
        lines.append(f"| {source} | {agent} | {len(rows)} | {high_gap} | {term} | {vacate} | {route} | {resource} | {deaths} |")

    lines += [
        "",
        "## Recovery Class Counts",
        "",
        "| Recovery class | Count | Death next rows |",
        "|---|---:|---:|",
    ]
    for cls, count in class_counts.most_common():
        lines.append(f"| {cls} | {count} | {death_classes[cls]} |")

    lines += [
        "",
        "## Highest Rank Gaps",
        "",
        "| Source | Phase | Step | Actual | Best | Gap | Bad labels |",
        "|---|---|---:|---|---|---:|---|",
    ]
    for row in sorted(out_rows, key=lambda r: float(r["rank_gap"]), reverse=True)[:30]:
        lines.append(
            f"| {row['source_group']} | {row['phase']} | {row['step_idx']} | "
            f"{row['factory_action']} | {row['best_action']} | {float(row['rank_gap']):.1f} | {row['bad_labels']} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", nargs="*", type=Path, default=[Path(p) for p in DEFAULT_STEPS])
    ap.add_argument("--out-prefix", type=Path, default=Path("reports/safety_rank_shadow_20260606"))
    args = ap.parse_args()

    paths = [p.expanduser().resolve() for p in args.steps]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise SystemExit(f"missing step CSV(s): {', '.join(missing)}")

    out_rows = [rank_row(row) for row in read_rows(paths)]
    prefix = args.out_prefix.expanduser()
    csv_path = Path(f"{prefix}.csv")
    report_path = Path(f"{prefix}.md")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        writer.writeheader()
        writer.writerows(out_rows)
    write_report(report_path, out_rows)
    print(f"wrote {csv_path}")
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
