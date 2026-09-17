#!/usr/bin/env python3
"""Consolidate per-team strategy_metrics CSVs into a master matrix for top1-10
analysis.

Each row in the output corresponds to one episode. Adds a few derived columns
that downstream analysis (clustering, classifier, rule mining) will rely on.

Inputs (relative to repo root):
  reports/top_competitors/<rank>_<slug>/strategy_metrics.csv
  reports/bunterrrrr_focus_strategy_metrics.csv
  reports/top10_analysis/jiayi_v24_combined_strategy_metrics.csv

Output:
  reports/top10_analysis/master_episode_matrix.csv
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
TC_DIR = ROOT / "reports" / "top_competitors"
OUT_DIR = ROOT / "reports" / "top10_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TEAM_RANK = {
    "bunterrrrr": 1,
    "Андрей Савельев": 2,
    "Takahiro Matsumoto": 3,
    "Hazy Maze Crawler": 4,
    "PavelLiashkov": 5,
    "Nicolas Klodt": 6,
    "Daniel Bekker": 7,
    "AI TOOK MY JOB AND YOUR JOB!": 8,
    "ZERO HQR": 9,
    "JosephMontana": 10,
    "harmo-miu": 11,
    "CurveCowboy": 12,
    "Pavlo Ivanin": 13,
    "Henry Solberg": 14,
    "Nicolas Bridelance": 15,
    "Jiayi Du": 24,
}

TEAM_SCORE = {
    "bunterrrrr": 2221.4,
    "Андрей Савельев": 1677.5,
    "Takahiro Matsumoto": 1659.8,
    "Hazy Maze Crawler": 1588.2,
    "PavelLiashkov": 1526.5,
    "Nicolas Klodt": 1500.3,
    "Daniel Bekker": 1399.8,
    "AI TOOK MY JOB AND YOUR JOB!": 1398.6,
    "ZERO HQR": 1369.4,
    "JosephMontana": 1338.4,
    "harmo-miu": 1274.7,
    "CurveCowboy": 1202.1,
    "Pavlo Ivanin": 1193.8,
    "Henry Solberg": 1188.6,
    "Nicolas Bridelance": 1176.8,
    "Jiayi Du": 1142.4,
}

# Episode CSVs we will read. (team_name, csv_path)
SOURCES = []
for d in sorted(TC_DIR.glob("*/")):
    metrics = d / "strategy_metrics.csv"
    if not metrics.exists():
        continue
    profile = d / "profile.md"
    team_name = None
    if profile.exists():
        for line in profile.read_text().splitlines()[:3]:
            m = re.match(r"^#\s*Rank\s*\d+:\s*(.+?)\s*$", line)
            if m:
                team_name = m.group(1).strip()
                break
    if team_name is None:
        continue
    SOURCES.append((team_name, metrics))

# Bunterrrrr explicit
SOURCES.append(("bunterrrrr", ROOT / "reports" / "bunterrrrr_focus_strategy_metrics.csv"))
# Our v24 (combined with v30, same code)
SOURCES.append(("Jiayi Du", OUT_DIR / "jiayi_v24_combined_strategy_metrics.csv"))


def _to_float(value: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_top_actions(field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    if not field:
        return out
    for chunk in field.split(";"):
        if ":" not in chunk:
            continue
        key, val = chunk.split(":", 1)
        try:
            out[key.strip()] = int(val.strip())
        except ValueError:
            continue
    return out


def derived(row: dict[str, str]) -> dict[str, float | int | str | None]:
    # Counts useful for clustering / rule mining
    actions = parse_top_actions(row.get("top_actions", "") or "")
    total = sum(actions.values()) or 1
    idle = actions.get("IDLE", 0)
    north = actions.get("NORTH", 0)
    south = actions.get("SOUTH", 0)
    east = actions.get("EAST", 0)
    west = actions.get("WEST", 0)
    jump_north = actions.get("JUMP_NORTH", 0)
    jump_east = actions.get("JUMP_EAST", 0)
    jump_west = actions.get("JUMP_WEST", 0)
    jump_south = actions.get("JUMP_SOUTH", 0)
    remove_north = actions.get("REMOVE_NORTH", 0)
    transfer_north = actions.get("TRANSFER_NORTH", 0)
    transfer_south = actions.get("TRANSFER_SOUTH", 0)
    transfer_east = actions.get("TRANSFER_EAST", 0)
    transfer_west = actions.get("TRANSFER_WEST", 0)
    build_scout_actions = sum(v for k, v in actions.items() if k.startswith("BUILD_SCOUT"))
    build_worker_actions = sum(v for k, v in actions.items() if k.startswith("BUILD_WORKER"))
    transform = actions.get("TRANSFORM", 0)

    energy_50 = _to_float(row.get("energy_50"))
    energy_100 = _to_float(row.get("energy_100"))
    energy_200 = _to_float(row.get("energy_200"))
    energy_300 = _to_float(row.get("energy_300"))
    energy_400 = _to_float(row.get("energy_400"))
    row_50 = _to_float(row.get("row_50"))
    row_100 = _to_float(row.get("row_100"))
    row_200 = _to_float(row.get("row_200"))
    row_300 = _to_float(row.get("row_300"))
    row_400 = _to_float(row.get("row_400"))

    first_miner = _to_float(row.get("first_build_miner"))
    first_scout = _to_float(row.get("first_build_scout"))
    first_worker = _to_float(row.get("first_build_worker"))

    build_miner = _to_float(row.get("build_miner")) or 0.0
    build_scout = _to_float(row.get("build_scout")) or 0.0
    build_worker = _to_float(row.get("build_worker")) or 0.0
    factory_jump = _to_float(row.get("factory_jump")) or 0.0
    transfer = _to_float(row.get("transfer")) or 0.0
    remove_wall = _to_float(row.get("remove_wall")) or 0.0
    transform_total = _to_float(row.get("transform")) or 0.0
    max_factory_energy = _to_float(row.get("max_factory_energy")) or 0.0
    final_factory_energy = _to_float(row.get("final_factory_energy"))
    max_mines = _to_float(row.get("max_mines")) or 0.0

    steps = _to_float(row.get("steps")) or 1.0
    team_reward = _to_float(row.get("team_reward")) or 0.0
    opp_reward = _to_float(row.get("opp_reward")) or 0.0
    result = row.get("result")

    # Velocity proxies
    rows_per_100_early = None
    if row_100 is not None:
        rows_per_100_early = row_100 / 100.0
    rows_per_step_200 = None
    if row_200 is not None:
        rows_per_step_200 = row_200 / 200.0
    energy_growth_50_200 = None
    if energy_50 is not None and energy_200 is not None:
        energy_growth_50_200 = energy_200 - energy_50

    return {
        "first_miner": first_miner,
        "first_scout": first_scout,
        "first_worker": first_worker,
        "build_miner": build_miner,
        "build_scout": build_scout,
        "build_worker": build_worker,
        "factory_jump": factory_jump,
        "transfer_total": transfer,
        "remove_wall_total": remove_wall,
        "transform_total": transform_total,
        "max_factory_energy": max_factory_energy,
        "final_factory_energy": final_factory_energy,
        "max_mines": max_mines,
        "steps": steps,
        "result": result,
        "team_reward": team_reward,
        "opp_reward": opp_reward,
        "row_50": row_50,
        "row_100": row_100,
        "row_200": row_200,
        "row_300": row_300,
        "row_400": row_400,
        "energy_50": energy_50,
        "energy_100": energy_100,
        "energy_200": energy_200,
        "energy_300": energy_300,
        "energy_400": energy_400,
        "rows_per_step_to_100": rows_per_100_early,
        "rows_per_step_to_200": rows_per_step_200,
        "energy_growth_50_200": energy_growth_50_200,
        # action mix
        "action_total": total,
        "idle_pct": 100.0 * idle / total,
        "north_pct": 100.0 * north / total,
        "south_pct": 100.0 * south / total,
        "east_pct": 100.0 * east / total,
        "west_pct": 100.0 * west / total,
        "jump_north_pct": 100.0 * jump_north / total,
        "jump_side_pct": 100.0 * (jump_east + jump_west + jump_south) / total,
        "transfer_north_pct": 100.0 * transfer_north / total,
        "transfer_side_pct": 100.0 * (transfer_south + transfer_east + transfer_west) / total,
        "remove_north_pct": 100.0 * remove_north / total,
        "build_scout_action_total": build_scout_actions,
        "build_worker_action_total": build_worker_actions,
        "transform_action": transform,
        # short-form
        "miner_per_minute": 60.0 * build_miner / steps,
        "scout_per_minute": 60.0 * build_scout / steps,
    }


def main() -> None:
    rows_out = []
    for team_name, src in SOURCES:
        if not src.exists():
            print(f"missing: {src}")
            continue
        with src.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                derived_row = derived(row)
                derived_row["team_name"] = team_name
                derived_row["rank"] = TEAM_RANK.get(team_name, 99)
                derived_row["team_score"] = TEAM_SCORE.get(team_name, 0.0)
                derived_row["episode_id"] = row.get("episode_id")
                derived_row["opponent"] = row.get("opponent")
                derived_row["replay_path"] = row.get("replay_path")
                rows_out.append(derived_row)

    fieldnames = sorted({k for r in rows_out for k in r})
    out_path = OUT_DIR / "master_episode_matrix.csv"
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"wrote {out_path} ({len(rows_out)} episodes)")

    # Aggregate per team
    by_team: dict[str, list[dict]] = defaultdict(list)
    for r in rows_out:
        by_team[r["team_name"]].append(r)
    agg = []
    for team, rs in by_team.items():
        n = len(rs)
        wins = sum(1 for r in rs if r["result"] == "win")
        losses = sum(1 for r in rs if r["result"] == "loss")
        draws = sum(1 for r in rs if r["result"] == "draw")
        agg_row = {
            "team_name": team,
            "rank": TEAM_RANK.get(team, 99),
            "team_score": TEAM_SCORE.get(team, 0.0),
            "n_episodes": n,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_pct": 100.0 * wins / n if n else 0,
        }
        # Numeric aggregates
        for key in (
            "first_miner",
            "first_scout",
            "build_miner",
            "build_scout",
            "build_worker",
            "factory_jump",
            "transfer_total",
            "remove_wall_total",
            "transform_total",
            "max_factory_energy",
            "final_factory_energy",
            "max_mines",
            "steps",
            "team_reward",
            "energy_50",
            "energy_100",
            "energy_200",
            "energy_300",
            "energy_400",
            "row_50",
            "row_100",
            "row_200",
            "row_300",
            "row_400",
            "idle_pct",
            "north_pct",
            "south_pct",
            "east_pct",
            "west_pct",
            "jump_north_pct",
            "jump_side_pct",
            "transfer_north_pct",
            "remove_north_pct",
            "miner_per_minute",
            "scout_per_minute",
        ):
            vals = [r[key] for r in rs if r.get(key) is not None]
            if not vals:
                agg_row[f"{key}_mean"] = None
                agg_row[f"{key}_median"] = None
                continue
            vals.sort()
            mean = sum(vals) / len(vals)
            median = vals[len(vals) // 2]
            agg_row[f"{key}_mean"] = round(mean, 3)
            agg_row[f"{key}_median"] = round(median, 3)
        # never_build_scout fraction (rare for some, common for others)
        agg_row["pct_episodes_no_scout"] = round(
            100.0 * sum(1 for r in rs if (r.get("build_scout") or 0) == 0) / n, 2
        ) if n else 0
        agg_row["pct_episodes_no_miner"] = round(
            100.0 * sum(1 for r in rs if (r.get("build_miner") or 0) == 0) / n, 2
        ) if n else 0
        agg.append(agg_row)

    agg.sort(key=lambda r: r["rank"])
    agg_path = OUT_DIR / "team_aggregate.csv"
    fields_agg = sorted({k for r in agg for k in r})
    with agg_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields_agg)
        writer.writeheader()
        writer.writerows(agg)
    print(f"wrote {agg_path} ({len(agg)} teams)")


if __name__ == "__main__":
    main()
