#!/usr/bin/env python3
"""Build a tidy per-team summary table for the top10 dossier.

For each of Top 1-10 + us, computes:
  - rank, score, sample win/loss/draw
  - core economy metrics
  - failure_mode top-3
  - bunterrrrr loss highlights (only for bunterrrrr)
  - 'gap vs bunterrrrr' on a few canonical features
  - 'gap vs us'

Reads:
  reports/top10_analysis/team_aggregate.csv
  reports/top_competitors/<rank>_<slug>/failure_analysis.csv  (per team)
  reports/bunterrrrr_focus_failure_analysis.csv               (bunterrrrr)

Writes:
  reports/top10_analysis/per_team_dossier.json
  reports/top10_analysis/per_team_dossier.md  (human readable)
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "top10_analysis"
TC = ROOT / "reports" / "top_competitors"

TEAM_ORDER = [
    ("bunterrrrr", "n/a", ROOT / "reports" / "bunterrrrr_focus_failure_analysis.csv"),
    ("Андрей Савельев", "02_andrey_saveliev", TC / "02_andrey_saveliev" / "failure_analysis.csv"),
    ("Takahiro Matsumoto", "03_takahiro_matsumoto", TC / "03_takahiro_matsumoto" / "failure_analysis.csv"),
    ("Hazy Maze Crawler", "04_hazy_maze_crawler", TC / "04_hazy_maze_crawler" / "failure_analysis.csv"),
    ("PavelLiashkov", "05_pavelliashkov", TC / "05_pavelliashkov" / "failure_analysis.csv"),
    ("Nicolas Klodt", "06_nicolas_klodt", TC / "06_nicolas_klodt" / "failure_analysis.csv"),
    ("Daniel Bekker", "07_daniel_bekker", TC / "07_daniel_bekker" / "failure_analysis.csv"),
    ("AI TOOK MY JOB AND YOUR JOB!", "08_ai_took_my_job", TC / "08_ai_took_my_job" / "failure_analysis.csv"),
    ("ZERO HQR", "09_zero_hqr", TC / "09_zero_hqr" / "failure_analysis.csv"),
    ("JosephMontana", "10_josephmontana", TC / "10_josephmontana" / "failure_analysis.csv"),
    ("Jiayi Du", "n/a", None),
]

def read_failures(path: Path | None) -> dict:
    """Aggregate failure cause / opponent on losses+draws."""
    if path is None or not path.exists():
        return {"n_losses": 0, "n_draws": 0, "cause_counts": {},
                "loss_opponents": [], "draw_opponents": [], "key_losses": []}
    n_losses, n_draws = 0, 0
    causes = Counter()
    loss_opps, draw_opps, key_losses = [], [], []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            res = row.get("result")
            cause = row.get("cause") or "n/a"
            if res == "loss":
                n_losses += 1
                causes[cause] += 1
                loss_opps.append(row.get("opponent", ""))
                if cause != "active_or_win":
                    key_losses.append({
                        "episode_id": row.get("episode_id"),
                        "opponent": row.get("opponent"),
                        "cause": cause,
                        "death_step": row.get("death_step"),
                        "south_at_death": row.get("south_at_death"),
                        "our_factory_action": row.get("our_factory_action"),
                        "opp_factory_action": row.get("opp_factory_action"),
                    })
            elif res == "draw":
                n_draws += 1
                draw_opps.append(row.get("opponent", ""))
    return {
        "n_losses": n_losses,
        "n_draws": n_draws,
        "cause_counts": dict(causes.most_common()),
        "loss_opponents": Counter(loss_opps).most_common(8),
        "draw_opponents": Counter(draw_opps).most_common(8),
        "key_losses": key_losses,
    }


def main() -> None:
    # Load aggregates
    agg = {}
    with (OUT / "team_aggregate.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            agg[row["team_name"]] = row

    bunt = agg["bunterrrrr"]
    us = agg.get("Jiayi Du", {})

    GAP_KEYS = [
        ("build_scout_mean", "scouts/ep"),
        ("build_miner_mean", "miners/ep"),
        ("build_worker_mean", "workers/ep"),
        ("first_miner_mean", "step of first miner"),
        ("max_factory_energy_mean", "peak factory energy"),
        ("final_factory_energy_mean", "final factory energy"),
        ("energy_300_mean", "energy at step 300"),
        ("row_200_mean", "row at step 200"),
        ("north_pct_mean", "NORTH action pct"),
        ("south_pct_mean", "SOUTH action pct"),
        ("jump_north_pct_mean", "JUMP_NORTH pct"),
        ("idle_pct_mean", "IDLE pct"),
        ("pct_episodes_no_scout", "pct ep with 0 scouts"),
    ]

    dossier = []
    md_chunks: list[str] = []
    for team_name, slug, failure_path in TEAM_ORDER:
        if team_name not in agg:
            continue
        a = agg[team_name]
        f = read_failures(failure_path)
        # Gap calculations
        gaps = {}
        for key, label in GAP_KEYS:
            try:
                v = float(a[key]) if a[key] not in ("", None) else None
            except ValueError:
                v = None
            try:
                bv = float(bunt[key]) if bunt[key] not in ("", None) else None
            except ValueError:
                bv = None
            try:
                uv = float(us.get(key, "")) if us.get(key, "") not in ("", None) else None
            except ValueError:
                uv = None
            gaps[key] = {
                "label": label,
                "value": v,
                "vs_bunterrrrr_delta": (v - bv) if v is not None and bv is not None else None,
                "vs_us_delta": (v - uv) if v is not None and uv is not None else None,
            }

        dossier.append({
            "team_name": team_name,
            "rank": int(a["rank"]),
            "team_score": float(a["team_score"]),
            "n_episodes": int(a["n_episodes"]),
            "wins": int(a["wins"]),
            "losses": int(a["losses"]),
            "draws": int(a["draws"]),
            "win_pct": float(a["win_pct"]),
            "gaps": gaps,
            "failure": f,
        })

        # Build markdown chunk
        md = [f"### #{a['rank']} {team_name}  (LB score {a['team_score']}, sample W-L-D {a['wins']}-{a['losses']}-{a['draws']})"]
        md.append("")
        md.append("**Core stats vs bunterrrrr (Δ) and vs us (Δ):**")
        md.append("")
        md.append("| metric | value | Δ vs bunterrrrr | Δ vs us |")
        md.append("|---|---|---|---|")
        for key, label in GAP_KEYS:
            g = gaps[key]
            v = g["value"]
            db = g["vs_bunterrrrr_delta"]
            du = g["vs_us_delta"]
            def fmt(x):
                if x is None: return "–"
                return f"{x:+.1f}" if abs(x) < 1000 else f"{x:+.0f}"
            md.append(f"| {label} | {v if v is None else round(v,2)} | {fmt(db)} | {fmt(du)} |")
        md.append("")
        if f["cause_counts"]:
            md.append("**Failure mode mix (losses+draws):** "
                      + ", ".join(f"{k}:{v}" for k, v in f["cause_counts"].items()))
        if f["loss_opponents"]:
            md.append("**Top loss opponents:** "
                      + ", ".join(f"{n}({c})" for n, c in f["loss_opponents"]))
        if f["draw_opponents"]:
            md.append("**Top draw opponents:** "
                      + ", ".join(f"{n}({c})" for n, c in f["draw_opponents"]))
        md.append("")
        md_chunks.append("\n".join(md))

    (OUT / "per_team_dossier.json").write_text(json.dumps(dossier, indent=2, ensure_ascii=False))
    (OUT / "per_team_dossier.md").write_text("\n\n".join(md_chunks))
    print(f"wrote {OUT/'per_team_dossier.json'}")
    print(f"wrote {OUT/'per_team_dossier.md'}")


if __name__ == "__main__":
    main()
