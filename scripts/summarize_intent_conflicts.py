#!/usr/bin/env python3
"""Summarize intent/owner/conflict signals from phase-route probe CSVs.

This is a read-only bridge from the current distribution/probe layer to the
"action arbitration" research line. It does not import agents or parse replays;
it consumes the corrected step CSVs emitted by probe_phase_route_quality.py.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


DEFAULT_STEPS = [
    "reports/probes/active_v51_53414790_phase_route_steps.csv",
    "reports/probes/active_v67_53414814_phase_route_steps.csv",
    "reports/probes/hist_v51_53412795_phase_route_steps.csv",
    "reports/probes/hist_v99_53412815_phase_route_steps.csv",
]

OWNER_FIELDS = [
    "source_group",
    "agent_label",
    "phase",
    "owner",
    "rows",
    "episodes",
    "bad_any",
    "death_next_step",
    "bad_route_blocked",
    "bad_support_void",
    "bad_support_blocking_factory",
    "bad_collision_tiebreak",
    "late_spend_action",
    "bad_final_build",
    "bad_final_transfer",
    "factory_action_is_build",
    "factory_action_is_transfer",
    "factory_action_is_jump",
    "factory_action_is_lateral",
    "mean_factory_gap",
    "mean_factory_energy",
    "mean_support_count",
    "mean_support_energy",
    "bad_any_rate",
    "route_blocked_rate",
    "support_void_rate",
    "support_blocking_rate",
    "late_spend_rate",
]

CONFLICT_FIELDS = [
    "source_group",
    "agent_label",
    "phase",
    "owner",
    "conflict",
    "count",
    "death_next_step_count",
    "rows_for_owner_phase",
    "conflict_rate",
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


def classify_owner(row: dict[str, str]) -> str:
    """Approximate which macro owner should have been responsible for the row."""
    action = row.get("factory_action", "")
    phase = row.get("phase", "")
    gap = number(row, "factory_gap", 99)
    if truthy(row.get("factory_dead_now")):
        return "dead_state"
    if gap <= 3 or truthy(row.get("bad_final_south_action")):
        return "survival_boundary"
    if truthy(row.get("bad_support_blocking_factory")) or truthy(row.get("north_neighbor_is_friendly_support")):
        return "support_unblock"
    if truthy(row.get("r1_transfer_fired")) or truthy(row.get("factory_action_is_transfer")):
        return "transfer_support"
    if truthy(row.get("factory_action_is_build")):
        if phase == "FINAL_KICK" or truthy(row.get("late_spend_action")):
            return "late_economy_spend"
        return "economy_build"
    if truthy(row.get("bad_route_blocked")):
        return "route_recovery"
    if action.startswith("JUMP_") or action in {"NORTH", "EAST", "WEST", "SOUTH"}:
        return "route_progress"
    if action == "IDLE":
        return "idle_fallback"
    return "other"


def conflict_labels(row: dict[str, str]) -> list[str]:
    labels = []
    for key in (
        "bad_route_blocked",
        "bad_support_void",
        "bad_support_blocking_factory",
        "bad_collision_tiebreak",
        "bad_high_factory_low_support_energy",
        "bad_mine_roi_low_lifetime",
        "bad_lateral_jcd_lock_risk",
        "bad_final_build",
        "bad_final_transfer",
        "bad_final_remove",
        "bad_final_south_action",
        "death_next_step",
    ):
        if truthy(row.get(key)):
            labels.append(key)
    if truthy(row.get("late_spend_action")):
        labels.append("late_spend_action")
    if truthy(row.get("north_cell_occupied")):
        labels.append("north_cell_occupied")
    if truthy(row.get("jump_north_landing_occupied")):
        labels.append("jump_north_landing_occupied")
    if not labels and truthy(row.get("bad_any")):
        labels.append("bad_any_unclassified")
    return labels


def read_rows(paths: Iterable[Path]) -> Iterable[dict[str, str]]:
    for path in paths:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("source_group") == "source_group":
                    continue
                yield row


def summarize(rows: Iterable[dict[str, str]]) -> tuple[list[dict], list[dict], list[dict]]:
    owner_stats: dict[tuple[str, str, str, str], dict] = {}
    conflict_counts: Counter[tuple[str, str, str, str, str]] = Counter()
    conflict_deaths: Counter[tuple[str, str, str, str, str]] = Counter()
    owner_rows: Counter[tuple[str, str, str, str]] = Counter()
    source_stats: dict[tuple[str, str], dict] = {}

    for row in rows:
        owner = classify_owner(row)
        key = (
            row.get("source_group", ""),
            row.get("agent_label", ""),
            row.get("phase", ""),
            owner,
        )
        owner_rows[key] += 1
        if key not in owner_stats:
            owner_stats[key] = {
                "source_group": key[0],
                "agent_label": key[1],
                "phase": key[2],
                "owner": key[3],
                "rows": 0,
                "episodes_set": set(),
                "factory_gap_sum": 0.0,
                "factory_energy_sum": 0.0,
                "support_count_sum": 0.0,
                "support_energy_sum": 0.0,
            }
            for field in OWNER_FIELDS:
                owner_stats[key].setdefault(field, 0)
        stat = owner_stats[key]
        stat["rows"] += 1
        stat["episodes_set"].add(row.get("episode_id", ""))
        stat["factory_gap_sum"] += number(row, "factory_gap")
        stat["factory_energy_sum"] += number(row, "factory_energy")
        stat["support_count_sum"] += number(row, "support_count")
        stat["support_energy_sum"] += number(row, "support_energy")
        for flag in (
            "bad_any",
            "death_next_step",
            "bad_route_blocked",
            "bad_support_void",
            "bad_support_blocking_factory",
            "bad_collision_tiebreak",
            "late_spend_action",
            "bad_final_build",
            "bad_final_transfer",
            "factory_action_is_build",
            "factory_action_is_transfer",
            "factory_action_is_jump",
            "factory_action_is_lateral",
        ):
            if truthy(row.get(flag)):
                stat[flag] += 1

        skey = (row.get("source_group", ""), row.get("agent_label", ""))
        if skey not in source_stats:
            source_stats[skey] = defaultdict(int)
            source_stats[skey]["source_group"] = skey[0]
            source_stats[skey]["agent_label"] = skey[1]
            source_stats[skey]["episodes_set"] = set()
        source_stats[skey]["rows"] += 1
        source_stats[skey]["episodes_set"].add(row.get("episode_id", ""))
        for label in conflict_labels(row):
            ckey = (*key, label)
            conflict_counts[ckey] += 1
            if truthy(row.get("death_next_step")):
                conflict_deaths[ckey] += 1
            source_stats[skey][label] += 1

    owner_rows_out = []
    for stat in owner_stats.values():
        rows_count = int(stat["rows"])
        out = {field: stat.get(field, 0) for field in OWNER_FIELDS}
        out["episodes"] = len(stat.pop("episodes_set"))
        out["mean_factory_gap"] = stat["factory_gap_sum"] / rows_count if rows_count else 0
        out["mean_factory_energy"] = stat["factory_energy_sum"] / rows_count if rows_count else 0
        out["mean_support_count"] = stat["support_count_sum"] / rows_count if rows_count else 0
        out["mean_support_energy"] = stat["support_energy_sum"] / rows_count if rows_count else 0
        out["bad_any_rate"] = out["bad_any"] / rows_count if rows_count else 0
        out["route_blocked_rate"] = out["bad_route_blocked"] / rows_count if rows_count else 0
        out["support_void_rate"] = out["bad_support_void"] / rows_count if rows_count else 0
        out["support_blocking_rate"] = out["bad_support_blocking_factory"] / rows_count if rows_count else 0
        out["late_spend_rate"] = out["late_spend_action"] / rows_count if rows_count else 0
        owner_rows_out.append(out)

    conflict_rows = []
    for key, count in conflict_counts.items():
        owner_key = key[:4]
        conflict_rows.append(
            {
                "source_group": key[0],
                "agent_label": key[1],
                "phase": key[2],
                "owner": key[3],
                "conflict": key[4],
                "count": count,
                "death_next_step_count": conflict_deaths[key],
                "rows_for_owner_phase": owner_rows[owner_key],
                "conflict_rate": count / owner_rows[owner_key] if owner_rows[owner_key] else 0,
            }
        )

    source_rows = []
    for stat in source_stats.values():
        out = dict(stat)
        out["episodes"] = len(out.pop("episodes_set"))
        source_rows.append(out)

    owner_rows_out.sort(
        key=lambda r: (
            -int(r["death_next_step"]),
            -int(r["bad_support_blocking_factory"]),
            -int(r["bad_route_blocked"]),
            -int(r["bad_support_void"]),
            r["source_group"],
        )
    )
    conflict_rows.sort(key=lambda r: (-int(r["death_next_step_count"]), -int(r["count"]), r["conflict"]))
    source_rows.sort(key=lambda r: r["source_group"])
    return owner_rows_out, conflict_rows, source_rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, owner_rows: list[dict], conflict_rows: list[dict], source_rows: list[dict]) -> None:
    def top(rows: list[dict], n: int = 12) -> list[dict]:
        return rows[:n]

    lines = [
        "# Intent / Owner / Conflict Matrix - 2026-06-06",
        "",
        "Input: phase-route probe step CSVs. This is read-only telemetry; no agent code was imported or changed.",
        "",
        "## Source Totals",
        "",
        "| Source | Agent | Episodes | Rows | Route blocked | Support void | Support blocking | Late spend | Death next |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in source_rows:
        lines.append(
            f"| {row.get('source_group','')} | {row.get('agent_label','')} | "
            f"{row.get('episodes',0)} | {row.get('rows',0)} | "
            f"{row.get('bad_route_blocked',0)} | {row.get('bad_support_void',0)} | "
            f"{row.get('bad_support_blocking_factory',0)} | {row.get('late_spend_action',0)} | "
            f"{row.get('death_next_step',0)} |"
        )

    lines += [
        "",
        "## Top Owner-Phase Risk Rows",
        "",
        "| Source | Phase | Owner | Rows | Bad rate | Route blocked | Support void | Support block | Late spend | Death next |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in top(owner_rows):
        lines.append(
            f"| {row['source_group']} | {row['phase']} | {row['owner']} | {row['rows']} | "
            f"{float(row['bad_any_rate']):.2f} | {row['bad_route_blocked']} | "
            f"{row['bad_support_void']} | {row['bad_support_blocking_factory']} | "
            f"{row['late_spend_action']} | {row['death_next_step']} |"
        )

    lines += [
        "",
        "## Top Conflicts",
        "",
        "| Source | Phase | Owner | Conflict | Count | Death next | Rate within owner/phase |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for row in top(conflict_rows, 16):
        lines.append(
            f"| {row['source_group']} | {row['phase']} | {row['owner']} | {row['conflict']} | "
            f"{row['count']} | {row['death_next_step_count']} | {float(row['conflict_rate']):.2f} |"
        )

    lines += [
        "",
        "## Engineering Reading",
        "",
        "1. If `support_unblock` or `route_recovery` dominates bad rows, the next candidate should be a reservation/safety-commit or PIBT-lite vacate patch, not another build threshold.",
        "2. If `late_economy_spend` dominates only wins or weak rows, Final Kick gating should remain a tunable helper, not a main promotion reason.",
        "3. If v51 and v67 show different owner/conflict shapes, keep them as scenario specialists and test a portfolio selector before merging modules.",
        "4. Treat support void as a distribution gap: it points to support-energy insurance and worker/miner portfolio design, but it is too broad to patch with one unconditional build.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", nargs="*", type=Path, default=[Path(p) for p in DEFAULT_STEPS])
    ap.add_argument("--out-prefix", type=Path, default=Path("reports/intent_conflict_matrix_20260606"))
    args = ap.parse_args()

    paths = [p.expanduser().resolve() for p in args.steps]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise SystemExit(f"missing step CSV(s): {', '.join(missing)}")

    owner_rows, conflict_rows, source_rows = summarize(read_rows(paths))
    prefix = args.out_prefix.expanduser()
    owner_path = Path(f"{prefix}_owner_phase.csv")
    conflict_path = Path(f"{prefix}_conflicts.csv")
    source_path = Path(f"{prefix}_sources.csv")
    report_path = Path(f"{prefix}.md")

    source_fields = sorted({k for row in source_rows for k in row})
    write_csv(owner_path, owner_rows, OWNER_FIELDS)
    write_csv(conflict_path, conflict_rows, CONFLICT_FIELDS)
    write_csv(source_path, source_rows, source_fields)
    write_markdown(report_path, owner_rows, conflict_rows, source_rows)

    print(f"wrote {owner_path}")
    print(f"wrote {conflict_path}")
    print(f"wrote {source_path}")
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
