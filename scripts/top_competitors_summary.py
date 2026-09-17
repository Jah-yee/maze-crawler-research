#!/usr/bin/env python3
"""Per-team profile.md generator and aggregate compendium for top competitors.

Consumes:
  reports/top_competitors/<slug>/strategy_metrics.csv
  reports/top_competitors/<slug>/failure_analysis.csv
  reports/top_competitors/<slug>/miner_events.csv
  reports/top_competitors/<slug>/focus_episodes.csv
  reports/top_competitors/<slug>/episodes.csv  (for full-population stats)

Produces:
  reports/top_competitors/<slug>/profile.md
  reports/top_competitors/aggregate_metrics.csv
  docs/top_competitors_compendium.md
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_DIR = ROOT / "reports" / "top_competitors"
DOCS = ROOT / "docs"

TEAMS = [
    {"rank": 2,  "team_id": 15912080, "team_name": "Андрей Савельев",             "slug": "02_andrey_saveliev",       "score": 1677.5},
    {"rank": 3,  "team_id": 16096591, "team_name": "Takahiro Matsumoto",          "slug": "03_takahiro_matsumoto",    "score": 1659.8},
    {"rank": 4,  "team_id": 16091355, "team_name": "Hazy Maze Crawler",           "slug": "04_hazy_maze_crawler",     "score": 1588.2},
    {"rank": 5,  "team_id": 16129175, "team_name": "PavelLiashkov",               "slug": "05_pavelliashkov",         "score": 1526.5},
    {"rank": 6,  "team_id": 16114141, "team_name": "Nicolas Klodt",               "slug": "06_nicolas_klodt",         "score": 1500.3},
    {"rank": 7,  "team_id": 16148325, "team_name": "Daniel Bekker",               "slug": "07_daniel_bekker",         "score": 1399.8},
    {"rank": 8,  "team_id": 15988966, "team_name": "AI TOOK MY JOB AND YOUR JOB!", "slug": "08_ai_took_my_job",       "score": 1398.6},
    {"rank": 9,  "team_id": 15844167, "team_name": "ZERO HQR",                    "slug": "09_zero_hqr",              "score": 1369.4},
    {"rank": 10, "team_id": 16103102, "team_name": "JosephMontana",               "slug": "10_josephmontana",         "score": 1338.4},
    {"rank": 11, "team_id": 16087640, "team_name": "harmo-miu",                   "slug": "11_harmo_miu",             "score": 1274.7},
    {"rank": 12, "team_id": 16050506, "team_name": "CurveCowboy",                 "slug": "12_curvecowboy",           "score": 1202.1},
    {"rank": 13, "team_id": 15854253, "team_name": "Pavlo Ivanin",                "slug": "13_pavlo_ivanin",          "score": 1193.8},
    {"rank": 14, "team_id": 16065837, "team_name": "Henry Solberg",               "slug": "14_henry_solberg",         "score": 1188.6},
    {"rank": 15, "team_id": 15926206, "team_name": "Nicolas Bridelance",          "slug": "15_nicolas_bridelance",    "score": 1176.8},
]

TOP15_NAMES = {t["team_name"] for t in TEAMS} | {"bunterrrrr"}


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def safe_int(x):
    try:
        return int(float(x))
    except Exception:
        return None


def fmt(x, decimals=1):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    if isinstance(x, float):
        return f"{x:.{decimals}f}"
    return str(x)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def median(seq):
    seq = [x for x in seq if x is not None]
    if not seq:
        return None
    return statistics.median(seq)


def mean(seq):
    seq = [x for x in seq if x is not None]
    if not seq:
        return None
    return statistics.mean(seq)


def percent(num, denom):
    if not denom:
        return None
    return 100.0 * num / denom


def compute_team_metrics(team: dict) -> dict:
    base = TOP_DIR / team["slug"]
    strat = read_csv(base / "strategy_metrics.csv")
    fail = read_csv(base / "failure_analysis.csv")
    miner = read_csv(base / "miner_events.csv")
    episodes_all = read_csv(base / "episodes.csv")

    # ---- focus-replay aggregates ----
    n = len(strat)
    wins = [r for r in strat if r.get("result") == "win"]
    losses = [r for r in strat if r.get("result") == "loss"]
    draws = [r for r in strat if r.get("result") == "draw"]

    team_rewards = [safe_float(r.get("team_reward")) for r in strat]
    final_fac_energy = [safe_float(r.get("final_factory_energy")) for r in strat]
    final_fac_row = [safe_float(r.get("final_factory_row")) for r in strat]
    max_fac_energy = [safe_float(r.get("max_factory_energy")) for r in strat]
    steps_seq = [safe_int(r.get("steps")) for r in strat]
    build_scouts = [safe_int(r.get("build_scout")) for r in strat]
    build_workers = [safe_int(r.get("build_worker")) for r in strat]
    build_miners = [safe_int(r.get("build_miner")) for r in strat]
    factory_jumps = [safe_int(r.get("factory_jump")) for r in strat]
    transforms = [safe_int(r.get("transform")) for r in strat]
    transfers = [safe_int(r.get("transfer")) for r in strat]
    remove_walls = [safe_int(r.get("remove_wall")) for r in strat]
    first_scout = [safe_int(r.get("first_build_scout")) for r in strat]
    first_worker = [safe_int(r.get("first_build_worker")) for r in strat]
    first_miner = [safe_int(r.get("first_build_miner")) for r in strat]
    max_mines = [safe_int(r.get("max_mines")) for r in strat]

    # Action mix from top_actions: a;-delimited string of action:count
    action_totals = Counter()
    south_actions = Counter()
    jump_dirs = Counter()
    idle_total = 0
    north_total = 0
    south_total = 0
    east_total = 0
    west_total = 0
    for r in strat:
        ta = r.get("top_actions") or ""
        for pair in ta.split(";"):
            if not pair:
                continue
            k, _, v = pair.partition(":")
            v = safe_int(v) or 0
            action_totals[k] += v
            if k == "IDLE":
                idle_total += v
            elif k == "NORTH":
                north_total += v
            elif k == "SOUTH":
                south_total += v
            elif k == "EAST":
                east_total += v
            elif k == "WEST":
                west_total += v
            elif k.startswith("JUMP_"):
                d = k.removeprefix("JUMP_")
                jump_dirs[d] += v
                if d == "SOUTH":
                    south_actions[k] += v

    south_save_total = south_total + jump_dirs.get("SOUTH", 0)

    # Miner direction distribution. The extractor normalizes plain BUILD_MINER
    # to NORTH because the environment uses NORTH as the legacy default.
    miner_dir = Counter()
    for r in miner:
        miner_dir[r.get("direction", "")] += 1
    total_miner_evt = sum(miner_dir.values())
    miner_dir_pct = {
        d: percent(miner_dir.get(d, 0), total_miner_evt) or 0.0
        for d in ("NORTH", "EAST", "WEST", "SOUTH")
    }

    # Failure causes (loss + draw only).
    cause_counter = Counter()
    for r in fail:
        if r.get("result") in ("loss", "draw"):
            cause_counter[r.get("cause", "")] += 1
    primary_failure = cause_counter.most_common(1)[0][0] if cause_counter else ""

    # Full-population win/loss/draw from episodes.csv (vs focus subset, which is biased).
    full_wins = full_losses = full_draws = 0
    vs_top15 = Counter()
    top_opp_results = Counter()
    for r in episodes_all:
        if r.get("type") != "EpisodeType.EPISODE_TYPE_PUBLIC":
            continue
        tr = safe_float(r.get("team_reward"))
        opr = safe_float(r.get("opponent_reward"))
        if tr is None or opr is None:
            continue
        if tr > opr:
            full_wins += 1
            res = "win"
        elif tr < opr:
            full_losses += 1
            res = "loss"
        else:
            full_draws += 1
            res = "draw"
        opp = r.get("opponent_team_name", "")
        if opp in TOP15_NAMES:
            vs_top15[opp] += 1
            top_opp_results[(opp, res)] += 1

    full_total = full_wins + full_losses + full_draws

    # Mid-game position telemetry.
    rows_at = {}
    for step in (50, 100, 200, 300, 400):
        rows_at[step] = mean([safe_float(r.get(f"row_{step}")) for r in strat])

    energies_at = {}
    for step in (50, 100, 200, 300, 400):
        energies_at[step] = mean([safe_float(r.get(f"energy_{step}")) for r in strat])

    return {
        "team": team,
        "n_focus": n,
        "focus_wld": (len(wins), len(losses), len(draws)),
        "team_rewards": team_rewards,
        "mean_reward": mean(team_rewards),
        "median_reward": median(team_rewards),
        "max_reward": max([x for x in team_rewards if x is not None], default=None),
        "mean_final_fac_energy": mean(final_fac_energy),
        "median_final_fac_energy": median(final_fac_energy),
        "mean_max_fac_energy": mean(max_fac_energy),
        "mean_final_row": mean(final_fac_row),
        "mean_steps": mean(steps_seq),
        "mean_build_scouts": mean(build_scouts),
        "median_build_scouts": median(build_scouts),
        "mean_build_workers": mean(build_workers),
        "mean_build_miners": mean(build_miners),
        "median_build_miners": median(build_miners),
        "mean_factory_jumps": mean(factory_jumps),
        "mean_transforms": mean(transforms),
        "mean_transfers": mean(transfers),
        "mean_remove_walls": mean(remove_walls),
        "median_first_scout": median(first_scout),
        "median_first_worker": median(first_worker),
        "median_first_miner": median(first_miner),
        "min_first_miner": min([x for x in first_miner if x is not None], default=None),
        "mean_max_mines": mean(max_mines),
        "idle_per_replay": idle_total / max(1, n),
        "north_per_replay": north_total / max(1, n),
        "south_save_per_replay": south_save_total / max(1, n),
        "jump_dirs_total": dict(jump_dirs),
        "miner_dir_pct": miner_dir_pct,
        "miner_dir_count": dict(miner_dir),
        "cause_counter": dict(cause_counter),
        "primary_failure": primary_failure,
        "full_population": {
            "total": full_total,
            "wins": full_wins,
            "losses": full_losses,
            "draws": full_draws,
            "win_pct": percent(full_wins, full_total) if full_total else None,
        },
        "vs_top15_counts": dict(vs_top15),
        "top_opp_results": {f"{k[0]}_{k[1]}": v for k, v in top_opp_results.items()},
        "rows_at": rows_at,
        "energies_at": energies_at,
        "action_totals": dict(action_totals.most_common(10)),
    }


def write_profile(m: dict) -> Path:
    t = m["team"]
    base = TOP_DIR / t["slug"]
    out = base / "profile.md"

    # Heuristic single-line summary built later in the compendium step; here keep facts.
    miner_pct = m["miner_dir_pct"]
    miner_count = sum(m["miner_dir_count"].values())
    main_dir = max(m["miner_dir_pct"].items(), key=lambda kv: kv[1])[0] if miner_count else "n/a"
    fmt_jump = ", ".join(f"{d}:{v}" for d, v in sorted(m["jump_dirs_total"].items(), key=lambda kv: -kv[1])) or "–"

    cause_str = ", ".join(f"{k}:{v}" for k, v in sorted(m["cause_counter"].items(), key=lambda kv: -kv[1])) or "–"
    fp = m["full_population"]
    fp_str = (f"{fp['wins']}-{fp['losses']}-{fp['draws']} "
              f"({fmt(fp['win_pct'], 1)}% W) over {fp['total']} public" if fp["total"] else "–")
    vs15 = ", ".join(f"{k}:{v}" for k, v in sorted(m["vs_top15_counts"].items(), key=lambda kv: -kv[1])) or "–"

    action_str = ", ".join(f"{k}:{v}" for k, v in m["action_totals"].items())

    lines: list[str] = []
    lines.append(f"# Rank {t['rank']}: {t['team_name']}")
    lines.append("")
    lines.append(f"- Team id: `{t['team_id']}`")
    lines.append(f"- Public score: `{t['score']}`")
    lines.append(f"- Public episodes record: {fp_str}")
    lines.append(f"- Replays studied: {m['n_focus']} (W-L-D {m['focus_wld'][0]}-{m['focus_wld'][1]}-{m['focus_wld'][2]})")
    lines.append("")
    lines.append("## Economy & length")
    lines.append("")
    lines.append(f"- Reward mean / median / max: **{fmt(m['mean_reward'])} / {fmt(m['median_reward'])} / {fmt(m['max_reward'])}**")
    lines.append(f"- Final factory energy mean / median: **{fmt(m['mean_final_fac_energy'])} / {fmt(m['median_final_fac_energy'])}**, peak mean: {fmt(m['mean_max_fac_energy'])}")
    lines.append(f"- Final factory row mean: {fmt(m['mean_final_row'])}; mean episode length: {fmt(m['mean_steps'])}")
    lines.append(f"- Row at step 50/100/200/300/400: "
                 f"{fmt(m['rows_at'].get(50))}/{fmt(m['rows_at'].get(100))}/{fmt(m['rows_at'].get(200))}/{fmt(m['rows_at'].get(300))}/{fmt(m['rows_at'].get(400))}")
    lines.append(f"- Factory energy at step 50/100/200/300/400: "
                 f"{fmt(m['energies_at'].get(50))}/{fmt(m['energies_at'].get(100))}/{fmt(m['energies_at'].get(200))}/{fmt(m['energies_at'].get(300))}/{fmt(m['energies_at'].get(400))}")
    lines.append("")
    lines.append("## Build mix (per replay)")
    lines.append("")
    lines.append(f"- Scouts: mean {fmt(m['mean_build_scouts'])} / median {fmt(m['median_build_scouts'])}")
    lines.append(f"- Workers: mean {fmt(m['mean_build_workers'])}")
    lines.append(f"- Miners: mean {fmt(m['mean_build_miners'])} / median {fmt(m['median_build_miners'])}")
    lines.append(f"- First-build steps (median): scout={fmt(m['median_first_scout'])}, worker={fmt(m['median_first_worker'])}, miner={fmt(m['median_first_miner'])} (min miner={fmt(m['min_first_miner'])})")
    lines.append(f"- Mean factory-jumps per replay: {fmt(m['mean_factory_jumps'])} (by dir: {fmt_jump})")
    lines.append(f"- TRANSFORM/TRANSFER/REMOVE per replay: {fmt(m['mean_transforms'])} / {fmt(m['mean_transfers'])} / {fmt(m['mean_remove_walls'])}")
    lines.append(f"- Mean max mines held simultaneously: {fmt(m['mean_max_mines'])}")
    lines.append("")
    lines.append("## Miner direction distribution")
    lines.append("")
    lines.append(f"- Total miner builds observed: {miner_count}")
    for d in ("NORTH", "EAST", "WEST", "SOUTH"):
        cnt = m["miner_dir_count"].get(d, 0)
        pct = m["miner_dir_pct"].get(d, 0.0)
        if cnt or pct:
            lines.append(f"  - {d}: {cnt} ({fmt(pct, 1)}%)")
    lines.append(f"- Dominant build direction: **{main_dir}**")
    lines.append("")
    lines.append("## Factory action mix (totals across focus replays)")
    lines.append("")
    lines.append(f"- IDLE per replay avg: {fmt(m['idle_per_replay'])}, NORTH per replay avg: {fmt(m['north_per_replay'])}")
    lines.append(f"- Survival-south actions per replay (SOUTH or JUMP_SOUTH): {fmt(m['south_save_per_replay'])}")
    lines.append(f"- Top actions: {action_str}")
    lines.append("")
    lines.append("## Failure analysis (losses + draws)")
    lines.append("")
    lines.append(f"- Causes: {cause_str}")
    lines.append(f"- Most common: **{m['primary_failure'] or 'n/a'}**")
    lines.append(f"- Public-population games vs top-15 opponents: {vs15}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Numbers are computed from the 25-episode focus set; see `strategy_metrics.csv`, `failure_analysis.csv`, `miner_events.csv` for raw rows.")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_aggregate(metrics_list: list[dict]) -> Path:
    out = TOP_DIR / "aggregate_metrics.csv"
    fieldnames = [
        "rank", "team_name", "slug", "score",
        "n_focus", "focus_wins", "focus_losses", "focus_draws",
        "mean_reward", "median_reward", "max_reward",
        "mean_final_fac_energy", "mean_max_fac_energy",
        "mean_final_row", "mean_steps",
        "mean_build_scouts", "mean_build_miners", "mean_build_workers",
        "median_first_scout", "median_first_miner", "min_first_miner",
        "mean_factory_jumps", "mean_max_mines",
        "miner_pct_north", "miner_pct_east", "miner_pct_west", "miner_pct_south",
        "miner_total",
        "idle_per_replay", "north_per_replay", "south_save_per_replay",
        "primary_failure", "cause_breakdown",
        "full_total", "full_wins", "full_losses", "full_draws", "full_win_pct",
    ]
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for m in metrics_list:
            t = m["team"]
            row = {
                "rank": t["rank"],
                "team_name": t["team_name"],
                "slug": t["slug"],
                "score": t["score"],
                "n_focus": m["n_focus"],
                "focus_wins": m["focus_wld"][0],
                "focus_losses": m["focus_wld"][1],
                "focus_draws": m["focus_wld"][2],
                "mean_reward": m["mean_reward"],
                "median_reward": m["median_reward"],
                "max_reward": m["max_reward"],
                "mean_final_fac_energy": m["mean_final_fac_energy"],
                "mean_max_fac_energy": m["mean_max_fac_energy"],
                "mean_final_row": m["mean_final_row"],
                "mean_steps": m["mean_steps"],
                "mean_build_scouts": m["mean_build_scouts"],
                "mean_build_miners": m["mean_build_miners"],
                "mean_build_workers": m["mean_build_workers"],
                "median_first_scout": m["median_first_scout"],
                "median_first_miner": m["median_first_miner"],
                "min_first_miner": m["min_first_miner"],
                "mean_factory_jumps": m["mean_factory_jumps"],
                "mean_max_mines": m["mean_max_mines"],
                "miner_pct_north": m["miner_dir_pct"].get("NORTH"),
                "miner_pct_east": m["miner_dir_pct"].get("EAST"),
                "miner_pct_west": m["miner_dir_pct"].get("WEST"),
                "miner_pct_south": m["miner_dir_pct"].get("SOUTH"),
                "miner_total": sum(m["miner_dir_count"].values()),
                "idle_per_replay": m["idle_per_replay"],
                "north_per_replay": m["north_per_replay"],
                "south_save_per_replay": m["south_save_per_replay"],
                "primary_failure": m["primary_failure"],
                "cause_breakdown": ";".join(f"{k}:{v}" for k, v in m["cause_counter"].items()),
                "full_total": m["full_population"]["total"],
                "full_wins": m["full_population"]["wins"],
                "full_losses": m["full_population"]["losses"],
                "full_draws": m["full_population"]["draws"],
                "full_win_pct": m["full_population"]["win_pct"],
            }
            writer.writerow(row)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ranks", default="2-15")
    args = parser.parse_args()

    if "-" in args.ranks:
        a, b = args.ranks.split("-", 1)
        keep = set(range(int(a), int(b) + 1))
    else:
        keep = {int(x) for x in args.ranks.split(",") if x.strip()}

    metrics_list = []
    for team in TEAMS:
        if team["rank"] not in keep:
            continue
        base = TOP_DIR / team["slug"]
        if not (base / "strategy_metrics.csv").exists():
            print(f"[skip] {team['slug']} has no strategy_metrics.csv")
            continue
        m = compute_team_metrics(team)
        out = write_profile(m)
        print(f"[profile] wrote {out}")
        metrics_list.append(m)

    if metrics_list:
        agg = write_aggregate(metrics_list)
        print(f"[aggregate] wrote {agg}")
        # also dump JSON for the compendium writer
        json_out = TOP_DIR / "aggregate_metrics.json"
        with json_out.open("w", encoding="utf-8") as fh:
            json.dump([{
                "rank": m["team"]["rank"],
                "team_name": m["team"]["team_name"],
                "slug": m["team"]["slug"],
                "score": m["team"]["score"],
                "n_focus": m["n_focus"],
                "focus_wld": m["focus_wld"],
                "mean_reward": m["mean_reward"],
                "median_reward": m["median_reward"],
                "max_reward": m["max_reward"],
                "mean_final_fac_energy": m["mean_final_fac_energy"],
                "mean_max_fac_energy": m["mean_max_fac_energy"],
                "mean_final_row": m["mean_final_row"],
                "mean_steps": m["mean_steps"],
                "mean_build_scouts": m["mean_build_scouts"],
                "median_build_scouts": m["median_build_scouts"],
                "mean_build_miners": m["mean_build_miners"],
                "median_build_miners": m["median_build_miners"],
                "mean_build_workers": m["mean_build_workers"],
                "median_first_scout": m["median_first_scout"],
                "median_first_miner": m["median_first_miner"],
                "min_first_miner": m["min_first_miner"],
                "mean_factory_jumps": m["mean_factory_jumps"],
                "mean_max_mines": m["mean_max_mines"],
                "miner_dir_pct": m["miner_dir_pct"],
                "miner_dir_count": m["miner_dir_count"],
                "idle_per_replay": m["idle_per_replay"],
                "north_per_replay": m["north_per_replay"],
                "south_save_per_replay": m["south_save_per_replay"],
                "jump_dirs_total": m["jump_dirs_total"],
                "primary_failure": m["primary_failure"],
                "cause_counter": m["cause_counter"],
                "full_population": m["full_population"],
                "vs_top15_counts": m["vs_top15_counts"],
                "top_opp_results": m["top_opp_results"],
                "rows_at": m["rows_at"],
                "energies_at": m["energies_at"],
                "action_totals": m["action_totals"],
            } for m in metrics_list], fh, indent=2, default=str)
        print(f"[aggregate] wrote {json_out}")


if __name__ == "__main__":
    main()
