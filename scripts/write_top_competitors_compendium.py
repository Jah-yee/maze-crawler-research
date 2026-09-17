#!/usr/bin/env python3
"""Aggregate per-team metrics into docs/top_competitors_compendium.md.

Adds bunterrrrr's row from reports/bunterrrrr_focus_strategy_metrics.csv where possible
so that the compendium covers all 15 top teams.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TOP_DIR = ROOT / "reports" / "top_competitors"


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


def median(seq):
    seq = [x for x in seq if x is not None]
    return statistics.median(seq) if seq else None


def mean(seq):
    seq = [x for x in seq if x is not None]
    return statistics.mean(seq) if seq else None


def percent(num, denom):
    if not denom:
        return None
    return 100.0 * num / denom


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_bunterrrrr_row() -> dict | None:
    src = ROOT / "reports" / "bunterrrrr_focus_strategy_metrics.csv"
    if not src.exists():
        return None
    with src.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return None
    res = lambda r: r.get("result") or ""
    team_rewards = [safe_float(r.get("team_reward")) for r in rows]
    final_fac_energy = [safe_float(r.get("final_factory_energy")) for r in rows]
    max_fac_energy = [safe_float(r.get("max_factory_energy")) for r in rows]
    final_row = [safe_float(r.get("final_factory_row")) for r in rows]
    steps_seq = [safe_int(r.get("steps")) for r in rows]
    build_scouts = [safe_int(r.get("build_scout")) for r in rows]
    build_miners = [safe_int(r.get("build_miner")) for r in rows]
    build_workers = [safe_int(r.get("build_worker")) for r in rows]
    first_scout = [safe_int(r.get("first_build_scout")) for r in rows]
    first_miner = [safe_int(r.get("first_build_miner")) for r in rows]
    factory_jumps = [safe_int(r.get("factory_jump")) for r in rows]
    max_mines = [safe_int(r.get("max_mines")) for r in rows]

    # Miner direction estimation from miner_events file if it exists.
    miner_dir = Counter()
    miner_csv = ROOT / "reports" / "bunterrrrr_miner_events.csv"
    if miner_csv.exists():
        with miner_csv.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                miner_dir[r.get("direction", "")] += 1

    # Failure / cause from failure analysis CSV.
    cause_counter = Counter()
    fail_csv = ROOT / "reports" / "bunterrrrr_focus_failure_analysis.csv"
    if fail_csv.exists():
        with fail_csv.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("result") in ("loss", "draw"):
                    cause_counter[r.get("cause", "")] += 1

    n = len(rows)
    wld = (sum(1 for r in rows if res(r) == "win"),
           sum(1 for r in rows if res(r) == "loss"),
           sum(1 for r in rows if res(r) == "draw"))

    return {
        "rank": 1,
        "team_name": "bunterrrrr",
        "slug": "bunterrrrr_focus",
        "score": 2221.4,
        "n_focus": n,
        "focus_wld": wld,
        "mean_reward": mean(team_rewards),
        "median_reward": median(team_rewards),
        "max_reward": max([x for x in team_rewards if x is not None], default=None),
        "mean_final_fac_energy": mean(final_fac_energy),
        "mean_max_fac_energy": mean(max_fac_energy),
        "mean_final_row": mean(final_row),
        "mean_steps": mean(steps_seq),
        "mean_build_scouts": mean(build_scouts),
        "median_build_scouts": median(build_scouts),
        "mean_build_miners": mean(build_miners),
        "median_build_miners": median(build_miners),
        "mean_build_workers": mean(build_workers),
        "median_first_scout": median(first_scout),
        "median_first_miner": median(first_miner),
        "min_first_miner": min([x for x in first_miner if x is not None], default=None),
        "mean_factory_jumps": mean(factory_jumps),
        "mean_max_mines": mean(max_mines),
        "miner_dir_pct": {
            d: percent(miner_dir.get(d, 0), sum(miner_dir.values())) or 0.0
            for d in ("NORTH", "EAST", "WEST", "SOUTH")
        },
        "miner_dir_count": dict(miner_dir),
        "idle_per_replay": None,
        "north_per_replay": None,
        "south_save_per_replay": None,
        "primary_failure": cause_counter.most_common(1)[0][0] if cause_counter else "",
        "cause_counter": dict(cause_counter),
        "full_population": {"total": 0, "wins": 0, "losses": 0, "draws": 0, "win_pct": None},
        "rows_at": {},
        "energies_at": {},
        "action_totals": {},
        "jump_dirs_total": {},
        "vs_top15_counts": {},
        "top_opp_results": {},
    }


def write_compendium(rows: list[dict]) -> Path:
    rows_sorted = sorted(rows, key=lambda r: r["rank"])
    out = DOCS / "top_competitors_compendium.md"

    # ---- aggregated views for prose sections ----
    no_scout = [r for r in rows_sorted if (r.get("median_build_scouts") or 0) == 0
                or (r.get("mean_build_scouts") or 0) < 0.5]
    high_scout = [r for r in rows_sorted if (r.get("mean_build_scouts") or 0) >= 2.0]
    early_miner = [r for r in rows_sorted if (r.get("median_first_miner") or 999) <= 40]
    late_miner = [r for r in rows_sorted if (r.get("median_first_miner") or 0) >= 80]
    high_jump = [r for r in rows_sorted if (r.get("mean_factory_jumps") or 0) >= 15.0]
    timeout_tied = [r for r in rows_sorted if r.get("primary_failure") == "timeout_tiebreak"]
    boundary_lost = [r for r in rows_sorted if r.get("primary_failure") == "boundary_scroll"]
    collide_lost = [r for r in rows_sorted if r.get("primary_failure") == "factory_collision"]
    directional_teams = [
        r for r in rows_sorted if sum(r["miner_dir_count"].values()) > 0
    ]
    legacy_plain_teams = [
        r for r in rows_sorted
        if any(
            row.get("action") == "BUILD_MINER"
            for row in read_csv(TOP_DIR / r["slug"] / "miner_events.csv")
        )
    ]
    no_miner_teams = [r for r in rows_sorted if sum(r["miner_dir_count"].values()) == 0
                      and (r.get("mean_build_miners") or 0) < 0.5]
    side_miners = sorted(
        directional_teams,
        key=lambda r: (r["miner_dir_pct"].get("EAST", 0) + r["miner_dir_pct"].get("WEST", 0)),
        reverse=True,
    )
    pure_north_miners = [r for r in directional_teams
                         if r["miner_dir_pct"].get("NORTH", 0) >= 80]
    south_savers = sorted([r for r in rows_sorted if r.get("south_save_per_replay") is not None],
                          key=lambda r: r["south_save_per_replay"], reverse=True)

    lines: list[str] = []
    lines.append("# Top-15 Competitor Compendium (maze-crawler)")
    lines.append("")
    lines.append("Snapshot: 2026-06-03; data drawn from per-team focus sets (25 high-signal replays per team for ranks 2-15) plus the existing 60-replay bunterrrrr focus set for rank 1. Public score numbers are from `data/raw/leaderboard_v37_check3/maze-crawler-publicleaderboard-2026-06-03T07:55:58.csv`. Our baseline for the executive summary is `experiments/v37` (Jiayi Du, rank 24, score 1129.0).")
    lines.append("")
    lines.append("## 1. Executive summary")
    lines.append("")
    lines.append("- The whole top-15 stratum is built around the **factory-as-greedy-collector + early miner economy** that we identified in the bunterrrrr study. Across 14 newly-studied teams plus bunterrrrr, **every** team's median first miner step is well before our v37's typical first miner (≈95-159 in our online replays), and many already build their first miner before step 30.")
    lines.append("- Our v37 leans heavily on routine `BUILD_SCOUT` while the top-15 either skip scouts entirely or build at most one or two. The most direct economy gap to rank-15 is **'less scout, faster first miner, more directional miner spam onto adjacent mines'**, not 'better path planning'.")
    lines.append("- The single most under-used class of action by our agent is **directional miner builds toward EAST/WEST mining nodes when the factory has a comfortable south gap**. About half of the top-15 derives a significant share of their miner builds from side directions; v37 only mines north.")
    lines.append("- The dominant failure mode at the top of the leaderboard is **`timeout_tiebreak`** (game reaches step 500 then loses on tiebreak), not boundary scroll or factory collision. Several teams have 70-100% of their losses falling into `timeout_tiebreak`. The implication is that getting to step 500 alive is necessary but not sufficient: the tiebreak is decided by support energy and final row, both of which the mine economy directly boosts.")
    lines.append("- Conclusion: a +200-300 score jump from rank 24 to rank 15 is almost entirely an economy upgrade (earlier+cheaper miners, less scout overhead, opportunistic side mines, late wall removal). It is **not** an algorithmic search overhaul.")
    lines.append("")
    lines.append("## 1.5 Counter-intuitive findings")
    lines.append("")
    lines.append("These are the findings that don't follow from extrapolating the bunterrrrr study:")
    lines.append("")
    lines.append("- **Two spellings, one NORTH miner mechanic.** Four teams (ranks 3, 8, 9, 13) use the legacy plain `BUILD_MINER` action for most miner builds. Current environment code defaults a build without a direction suffix to NORTH, so this is not an in-factory spawn and should be grouped with `BUILD_MINER_NORTH` when inferring geometry. Rank 3 Takahiro Matsumoto uses the legacy spelling for 100% of 134 observed miner builds.")
    lines.append("- **A pure-scout strategy still reaches rank 15.** Rank 15 Nicolas Bridelance builds **zero miners** across 777 public episodes (and zero in our 25-replay focus set), averaging 7.8 scouts per game and 0 workers. They reach rank 15 with the same strategy class as our v37 (and our older v1/v6/v7/v11). The gap from our rank 24 to their rank 15 is therefore **execution detail, not strategy class**: collision avoidance, careful row management, and the occasional opportunistic miner. We do not need to adopt the mine economy to reach rank 15.")
    lines.append("- **Heavy SOUTH usage is routine at the top.** Rank 3 Takahiro Matsumoto averages 89 SOUTH/JUMP_SOUTH actions per replay. Rank 6 Nicolas Klodt averages 71. Rank 13 Pavlo Ivanin averages 61. v37 treats SOUTH as a near-error and almost never plays it. The data shows SOUTH is a routine survival tool — racing south refreshes movement/jump cooldowns and avoids head-on factory collisions, then JUMP_NORTH bursts back. v37's scroll-fear is over-tuned.")
    lines.append("")
    lines.append("## 2. Shared patterns (top-15 does, we don't)")
    lines.append("")
    lines.append("1. **First miner well before step 50.** Median first-miner step across the studied focus replays:")
    for r in rows_sorted:
        if r.get("median_first_miner") is not None:
            lines.append(f"   - rank {r['rank']} {r['team_name']}: {fmt(r['median_first_miner'])} (min observed {fmt(r['min_first_miner'])})")
    lines.append("   Our v37 typically first-builds a miner only after step 90, frequently never; closing this gap is the single highest-EV change.")
    lines.append("")
    lines.append(f"2. **Drastically fewer scouts than v37.** Mean scouts per game by team:")
    for r in rows_sorted:
        lines.append(f"   - rank {r['rank']} {r['team_name']}: {fmt(r.get('mean_build_scouts'))} (median {fmt(r.get('median_build_scouts'))})")
    lines.append(f"   {len(no_scout)}/{len(rows_sorted)} teams essentially **never** build routine scouts (mean<0.5). Our v37 still spends energy on BUILD_SCOUT every 5-10 steps even when vision is no longer the bottleneck.")
    lines.append("")
    lines.append("3. **Factory uses JUMP_* heavily as a fast NORTH and survival tool.** Average factory jumps per replay:")
    for r in rows_sorted:
        lines.append(f"   - rank {r['rank']} {r['team_name']}: {fmt(r.get('mean_factory_jumps'))}")
    lines.append(f"   {len(high_jump)} of {len(rows_sorted)} teams average ≥15 factory-jumps per replay. Our v37 only jumps reactively when scroll pressure is high; using JUMP_NORTH proactively (the moment a 2-cell empty corridor opens) is consistently used by the top of the board.")
    lines.append("")
    lines.append("4. **Factory steps onto its own mines and TRANSFERs energy.** Even teams that build only 2-3 miners total still log dozens of `TRANSFER_*` actions per game, because the workflow is `BUILD_MINER_X → TRANSFORM → factory walks onto the new mine → TRANSFER from miner remainder + 50/turn from mine`. v37 does not exercise this loop.")
    lines.append("")
    lines.append("5. **Late-game wall removal to reopen a path north.** Most top-15 replays show `REMOVE_NORTH`/`REMOVE_*` activity in the late game (steps 300-500). Mean wall-removals per replay are non-trivial for most teams. Our v37 essentially never removes walls.")
    lines.append("")
    lines.append("## 3. Divergent patterns (top-15 internal schools)")
    lines.append("")
    def names_str(group):
        return ", ".join(f"rank {r['rank']} {r['team_name']}" for r in group) or "none"
    pure_north_str = names_str(pure_north_miners)
    lines.append("- **Explicit-direction vs legacy-NORTH spelling.** Plain `BUILD_MINER` is a backward-compatible NORTH spawn, not a separate in-factory mechanic. The observed split is action spelling:")
    lines.append(f"   - Directional school ({len(directional_teams)} teams): {names_str(directional_teams)}")
    lines.append(f"   - Teams observed using the legacy plain action: {names_str(legacy_plain_teams)}")
    lines.append(f"   - No-miner / mostly-scout school ({len(no_miner_teams)} teams, ≤0.5 miners per game): {names_str(no_miner_teams)}")
    lines.append("")
    lines.append(f"- **Pure-north miners vs side miners (within the directional school).** Pure-north miners (≥80% miner builds NORTH): {pure_north_str}. Heavy side miners (largest EAST+WEST share):")
    for r in side_miners[:5]:
        side = (r["miner_dir_pct"].get("EAST", 0) + r["miner_dir_pct"].get("WEST", 0))
        nesw = (
            f"N{fmt(r['miner_dir_pct'].get('NORTH', 0), 0)}/"
            f"E{fmt(r['miner_dir_pct'].get('EAST', 0), 0)}/"
            f"W{fmt(r['miner_dir_pct'].get('WEST', 0), 0)}/"
            f"S{fmt(r['miner_dir_pct'].get('SOUTH', 0), 0)}"
        )
        lines.append(f"   - rank {r['rank']} {r['team_name']}: side share {fmt(side, 1)}% ({nesw})")
    lines.append("")
    def names_first_miner(group):
        return ", ".join(
            f"rank {r['rank']} {r['team_name']}({fmt(r['median_first_miner'])})"
            for r in group
        ) or "none"
    lines.append(
        "- **Early-miner specialists vs late-miner economy.** "
        f"Early (median first miner ≤40): {names_first_miner(early_miner)}. "
        f"Late (median first miner ≥80): {names_first_miner(late_miner)}. "
        "The early-miner school converts the opening 30 steps directly into energy, accepting some scroll risk; "
        "the late school plays a safer race first and only mines once the corridor is committed."
    )
    lines.append("")
    high_scout_str = ", ".join(
        f"rank {r['rank']} {r['team_name']}({fmt(r['mean_build_scouts'])})"
        for r in high_scout
    ) or "none"
    lines.append(
        "- **Scout-zero schools vs hybrid scout users.** "
        f"Zero-scout (mean<0.5): {names_str(no_scout)}. "
        f"Higher-scout hybrids (mean ≥2): {high_scout_str}."
    )
    lines.append("")
    lines.append("## 4. Rare but lethal techniques")
    lines.append("")
    lines.append(f"- **Step ≤10 BUILD_MINER**: the earliest miner builds observed (`min_first_miner`) include " + ", ".join(f"rank {r['rank']} {r['team_name']}(step {fmt(r['min_first_miner'])})" for r in rows_sorted if r.get('min_first_miner') is not None and r['min_first_miner'] <= 15)[:1000] + ". Building a miner at step ≤10 commits to the economy before the opponent has scouted and before scroll has started; in our v37 the equivalent slot is wasted on `BUILD_SCOUT_NORTH`.")
    if south_savers:
        s = south_savers[0]
        south_top = ", ".join(
            f"rank {r['rank']} {r['team_name']}({fmt(r['south_save_per_replay'])})"
            for r in south_savers[:3]
        )
        lines.append(
            "- **Defensive `SOUTH`/`JUMP_SOUTH` to dodge collision and reset cooldowns.** "
            f"The teams that use the most survival-south actions per replay are {south_top}. "
            "v37 actively avoids SOUTH because of scroll fear; the data shows the top-15 routinely accept one or two SOUTH steps in exchange for not dying in a head-on factory collision."
        )
    lines.append("- **Late-game `REMOVE_NORTH` to break maze walls late and pop one extra row in tiebreak.** Several profiles show non-trivial `REMOVE_*` counts even though their explorers are minimal; the factory removes walls itself once it has enough energy and can no longer step around them. In our v37, factory wall-removal is essentially never triggered.")
    lines.append("- **High-reward jackpot runs.** Several teams have at least one focus replay with reward ≥5000 (mine economy snowball). Highest observed max reward per team:")
    for r in rows_sorted:
        if r.get("max_reward") is not None and r["max_reward"] >= 3000:
            lines.append(f"   - rank {r['rank']} {r['team_name']}: max reward {fmt(r['max_reward'])}")
    lines.append("  These outlier games dominate the public score under the Kaggle ranking system, so missing them costs more than one would think from a 'most games go to step 500' prior.")
    lines.append("")
    lines.append("## 5. Highest-ROI changes for v38 (rank 24 → 15)")
    lines.append("")
    lines.append("1. **Earlier first miner.** Push the first `BUILD_MINER_*` to step 20-30 unconditionally when an adjacent mining node is visible north, east, or west. This is the change all of bunterrrrr, Андрей Савельев, Takahiro Matsumoto, Hazy Maze Crawler, harmo-miu, and ZERO HQR have already made; it is the dominant reason we are below them. (Re-uses the experiment v15 + v17 + v19 lineage but commits to it as the default rather than an A/B.)")
    lines.append("2. **Add side miners under a clear gating rule.** When the factory's southBound gap is ≥6 and `move_cd > 0`, allow `BUILD_MINER_EAST` / `BUILD_MINER_WEST` if the adjacent cell is a mining node. This is what splits Андрей Савельев / Takahiro Matsumoto / Hazy Maze Crawler from the pure-north school and is consistently associated with reward outliers ≥3000. Re-use the v21 gating logic but ship it.")
    lines.append("3. **Cap scouts at 1-2 then disable.** The strong correlation across the top-15 between low scout count and high score is overwhelming; v37's routine scout cycle is a tempo and energy leak. Either gate `BUILD_SCOUT` behind low explored coverage (similar to v19's `SCOUT_DELAY_STEP=24` but harder: cap total scouts at 2), or disable routine scouts after step ~30 and rely on the factory's local vision plus existing scouts/workers.")
    lines.append("")
    lines.append("## 6. Cross-team metrics table")
    lines.append("")
    header = ("| Rank | Team | Score | Focus W-L-D | Avg reward | Final factory energy | First miner step (median) | Scouts (mean) | Miner builds (mean) | Miner direction NESW/U% | Max mines | Primary failure |")
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for r in rows_sorted:
        wld = "{}-{}-{}".format(*r["focus_wld"])
        nesw = "/".join(fmt(r["miner_dir_pct"].get(d, 0), 0) for d in ("NORTH", "EAST", "WEST", "SOUTH"))
        lines.append(
            f"| {r['rank']} | {r['team_name']} | {fmt(r['score'])} | {wld} | "
            f"{fmt(r.get('mean_reward'))} | {fmt(r.get('mean_final_fac_energy'))} | "
            f"{fmt(r.get('median_first_miner'))} (min {fmt(r.get('min_first_miner'))}) | "
            f"{fmt(r.get('mean_build_scouts'))} | {fmt(r.get('mean_build_miners'))} | "
            f"{nesw} | {fmt(r.get('mean_max_mines'))} | {r.get('primary_failure') or '–'} |"
        )
    lines.append("")
    lines.append("## 7. Where to look next")
    lines.append("")
    lines.append("- Per-team `profile.md`s in `reports/top_competitors/<slug>/profile.md` carry richer breakdowns including action-mix, row-by-step, top-15 head-to-head counts, plus a **Tactical archive** narrative section that answers the per-team qualitative questions (core playbook, v37 differences, unique tricks, weakness, projected v37 matchup).")
    lines.append("- `reports/top_competitors/aggregate_metrics.csv` is the machine-readable join of every metric used in this compendium; rerun via `python scripts/top_competitors_summary.py --ranks 2-15` after re-downloading replays. `reports/top_competitors/aggregate_metrics.json` is the same data with full nested structures (vs-top15 counters, action totals).")
    lines.append("- `reports/top_competitors/<slug>/replays/` holds the raw JSON (~4 MB each) for spot-checking specific episodes. Useful starting points:")
    lines.append("  - To study undirected `BUILD_MINER`: `reports/top_competitors/03_takahiro_matsumoto/replays/` and `08_ai_took_my_job/replays/`.")
    lines.append("  - To study side miners: `reports/top_competitors/04_hazy_maze_crawler/replays/`, `10_josephmontana/replays/`.")
    lines.append("  - To study off-axis (no-NORTH) miners: `reports/top_competitors/14_henry_solberg/replays/`.")
    lines.append("  - To study pure scout (our own school): `reports/top_competitors/15_nicolas_bridelance/replays/` — the most direct apples-to-apples comparison to v37.")
    lines.append("- Pipeline scripts:")
    lines.append("  - `scripts/top_competitors_pipeline.py` orchestrates fetch / focus / download / metrics per rank set.")
    lines.append("  - `scripts/top_competitors_summary.py` produces per-team profile.md and the aggregate CSV/JSON.")
    lines.append("  - `scripts/append_tactical_archives.py` injects/refreshes the qualitative tactical archive into each profile.md.")
    lines.append("  - `scripts/write_top_competitors_compendium.py` produces this compendium.")
    lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> None:
    json_path = TOP_DIR / "aggregate_metrics.json"
    if not json_path.exists():
        print(f"missing {json_path}; run scripts/top_competitors_summary.py first")
        raise SystemExit(1)
    with json_path.open(encoding="utf-8") as fh:
        rows = json.load(fh)

    bunt = load_bunterrrrr_row()
    if bunt is not None:
        rows = [bunt] + rows

    out = write_compendium(rows)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
