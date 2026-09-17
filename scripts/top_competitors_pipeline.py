#!/usr/bin/env python3
"""Pipeline: fetch submissions+episodes, pick focus replays, download, analyze for top competitors.

Steps:
  - fetch: call fetch_team_public_episodes.py for one team into the team folder.
  - focus: pick 20-30 high-signal episodes and write focus_episodes.csv.
  - download: download replays via kaggle competitions replay.
  - metrics: run analyze_strategy_metrics.py + analyze_replay_failures.py + analyze_miner_events.py.

All operations are idempotent enough to re-run without redoing finished work.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "bin" / "python"
KAGGLE = ROOT / ".venv" / "bin" / "kaggle"
TOP_DIR = ROOT / "reports" / "top_competitors"

# Top-15 leaderboard (rank 2-15, since bunterrrrr is already studied).
TEAMS: list[dict[str, object]] = [
    {"rank": 2,  "team_id": 15912080, "team_name": "Андрей Савельев",             "slug": "02_andrey_saveliev"},
    {"rank": 3,  "team_id": 16096591, "team_name": "Takahiro Matsumoto",          "slug": "03_takahiro_matsumoto"},
    {"rank": 4,  "team_id": 16091355, "team_name": "Hazy Maze Crawler",           "slug": "04_hazy_maze_crawler"},
    {"rank": 5,  "team_id": 16129175, "team_name": "PavelLiashkov",               "slug": "05_pavelliashkov"},
    {"rank": 6,  "team_id": 16114141, "team_name": "Nicolas Klodt",               "slug": "06_nicolas_klodt"},
    {"rank": 7,  "team_id": 16148325, "team_name": "Daniel Bekker",               "slug": "07_daniel_bekker"},
    {"rank": 8,  "team_id": 15988966, "team_name": "AI TOOK MY JOB AND YOUR JOB!", "slug": "08_ai_took_my_job"},
    {"rank": 9,  "team_id": 15844167, "team_name": "ZERO HQR",                    "slug": "09_zero_hqr"},
    {"rank": 10, "team_id": 16103102, "team_name": "JosephMontana",               "slug": "10_josephmontana"},
    {"rank": 11, "team_id": 16087640, "team_name": "harmo-miu",                   "slug": "11_harmo_miu"},
    {"rank": 12, "team_id": 16050506, "team_name": "CurveCowboy",                 "slug": "12_curvecowboy"},
    {"rank": 13, "team_id": 15854253, "team_name": "Pavlo Ivanin",                "slug": "13_pavlo_ivanin"},
    {"rank": 14, "team_id": 16065837, "team_name": "Henry Solberg",               "slug": "14_henry_solberg"},
    {"rank": 15, "team_id": 15926206, "team_name": "Nicolas Bridelance",          "slug": "15_nicolas_bridelance"},
]

# Top-15 team names (lower-cased exact match for opponent filter).
TOP15_NAMES = {t["team_name"] for t in TEAMS} | {"bunterrrrr"}


def team_dir(team: dict) -> Path:
    return TOP_DIR / str(team["slug"])


def run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)


def fetch_team(team: dict) -> bool:
    """Run scripts/fetch_team_public_episodes.py. Return True on success."""
    out_dir = team_dir(team)
    out_dir.mkdir(parents=True, exist_ok=True)
    subs = out_dir / "submissions.csv"
    eps = out_dir / "episodes.csv"
    if subs.exists() and eps.exists() and subs.stat().st_size > 0 and eps.stat().st_size > 0:
        print(f"[fetch] skip {team['slug']} (already fetched)")
        return True

    cmd = [
        str(PY), str(ROOT / "scripts" / "fetch_team_public_episodes.py"),
        "--team-id", str(team["team_id"]),
        "--team-name", str(team["team_name"]),
        "--submissions-out", str(subs),
        "--episodes-out", str(eps),
    ]
    for attempt in range(1, 4):
        try:
            proc = run(cmd, timeout=240)
        except subprocess.TimeoutExpired as exc:
            print(f"[fetch] {team['slug']} timeout attempt {attempt}: {exc}")
            time.sleep(3 * attempt)
            continue
        if proc.returncode == 0:
            print(f"[fetch] {team['slug']}: {proc.stdout.strip().splitlines()[-1] if proc.stdout else 'ok'}")
            return True
        print(f"[fetch] {team['slug']} attempt {attempt} failed:\n{proc.stdout}")
        time.sleep(3 * attempt)
    return False


def pick_focus(team: dict, limit: int = 25) -> int:
    """Select high-signal episodes from episodes.csv. Returns count."""
    out_dir = team_dir(team)
    src = out_dir / "episodes.csv"
    dst = out_dir / "focus_episodes.csv"
    if not src.exists():
        print(f"[focus] {team['slug']} no episodes.csv")
        return 0

    with src.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    # Keep only public episodes that have rewards.
    rows = [r for r in rows if r.get("type") == "EpisodeType.EPISODE_TYPE_PUBLIC"
            and r.get("team_index") not in (None, "")
            and r.get("team_reward") not in (None, "")]
    if not rows:
        print(f"[focus] {team['slug']}: no public episodes")
        return 0

    # Annotate each row with selection signals.
    def to_float(x):
        try:
            return float(x)
        except Exception:
            return None

    for r in rows:
        r["_team_reward"] = to_float(r.get("team_reward"))
        r["_opp_reward"] = to_float(r.get("opponent_reward"))
        r["_create"] = r.get("createTime", "")

    # Result categorization.
    def res(r):
        a, b = r["_team_reward"], r["_opp_reward"]
        if a is None or b is None:
            return "unk"
        if a > b:
            return "win"
        if a < b:
            return "loss"
        return "draw"

    losses = [r for r in rows if res(r) == "loss"]
    draws = [r for r in rows if res(r) == "draw"]
    wins = [r for r in rows if res(r) == "win"]
    top_opp = [r for r in rows if r.get("opponent_team_name") in TOP15_NAMES]
    recent = sorted(rows, key=lambda r: r["_create"], reverse=True)
    top_reward_wins = sorted(wins, key=lambda r: r["_team_reward"] or 0.0, reverse=True)

    picked: list[dict] = []
    seen: set[str] = set()

    def add_from(seq, n):
        for r in seq:
            if len(picked) >= limit:
                return
            eid = str(r["id"])
            if eid in seen:
                continue
            picked.append(r)
            seen.add(eid)
            if len([x for x in picked if x is r]) >= 1:
                pass
            if n is not None and sum(1 for p in picked if id(p) >= 0) >= len(picked):
                pass
        return

    # Quotas: half-ish on losses/draws + strong opponents, the rest on recent + top-reward wins.
    quotas = [
        ("losses", losses, 8),
        ("draws", draws, 3),
        ("top_opp", top_opp, 8),
        ("recent", recent, 6),
        ("top_reward_wins", top_reward_wins, 5),
    ]
    for name, seq, n in quotas:
        count = 0
        for r in seq:
            if len(picked) >= limit:
                break
            if count >= n:
                break
            eid = str(r["id"])
            if eid in seen:
                continue
            picked.append({**r, "reason": name})
            seen.add(eid)
            count += 1

    # Backfill with most recent.
    for r in recent:
        if len(picked) >= limit:
            break
        eid = str(r["id"])
        if eid in seen:
            continue
        picked.append({**r, "reason": "backfill_recent"})
        seen.add(eid)

    if not picked:
        print(f"[focus] {team['slug']}: nothing to pick")
        return 0

    fieldnames = ["id", "type", "submission_id", "createTime", "team_index", "team_reward",
                  "opponent_team_name", "opponent_team_id", "opponent_reward", "reason"]
    with dst.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in picked:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
    print(f"[focus] {team['slug']}: wrote {len(picked)} episodes")
    return len(picked)


def download_one(replay_dir: Path, episode_id: str) -> bool:
    target = replay_dir / f"episode-{episode_id}-replay.json"
    if target.exists():
        return True
    for attempt in range(1, 4):
        try:
            proc = run([str(KAGGLE), "competitions", "replay", episode_id, "-p", str(replay_dir)], timeout=120)
        except subprocess.TimeoutExpired:
            time.sleep(2 * attempt)
            continue
        if proc.returncode == 0 and target.exists():
            return True
        time.sleep(2 * attempt)
    return False


def download_replays(team: dict) -> tuple[int, int]:
    out_dir = team_dir(team)
    src = out_dir / "focus_episodes.csv"
    if not src.exists():
        print(f"[download] {team['slug']} no focus_episodes.csv")
        return 0, 0
    replay_dir = out_dir / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    fail = 0
    with src.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        eid = str(r["id"])
        if download_one(replay_dir, eid):
            ok += 1
        else:
            fail += 1
            print(f"[download] {team['slug']} failed {eid}")
    print(f"[download] {team['slug']}: ok={ok} fail={fail}")
    return ok, fail


def run_metrics(team: dict) -> None:
    out_dir = team_dir(team)
    replay_dir = out_dir / "replays"
    if not any(replay_dir.glob("episode-*-replay.json")):
        print(f"[metrics] {team['slug']}: no replays")
        return
    strategy_out = out_dir / "strategy_metrics.csv"
    failure_out = out_dir / "failure_analysis.csv"
    miner_out = out_dir / "miner_events.csv"
    cmds = [
        [str(PY), str(ROOT / "scripts" / "analyze_strategy_metrics.py"),
         "--replay-dir", str(replay_dir), "--team-name", str(team["team_name"]),
         "--out", str(strategy_out)],
        [str(PY), str(ROOT / "scripts" / "analyze_replay_failures.py"),
         "--replay-dir", str(replay_dir), "--team-name", str(team["team_name"]),
         "--out", str(failure_out)],
        [str(PY), str(ROOT / "scripts" / "analyze_miner_events.py"),
         "--replay-dir", str(replay_dir), "--team-name", str(team["team_name"]),
         "--out", str(miner_out)],
    ]
    for cmd in cmds:
        proc = run(cmd, timeout=600)
        if proc.returncode != 0:
            print(f"[metrics] {team['slug']} FAILED {cmd[1]}:\n{proc.stdout}")
        else:
            tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
            print(f"[metrics] {team['slug']} {Path(cmd[1]).name}: {tail}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["fetch", "focus", "download", "metrics", "all"], default="all")
    parser.add_argument("--ranks", default="2-15", help="e.g. 2-15 or 2,3,5")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    if "-" in args.ranks:
        a, b = args.ranks.split("-", 1)
        keep = set(range(int(a), int(b) + 1))
    else:
        keep = {int(x) for x in args.ranks.split(",") if x.strip()}

    selected = [t for t in TEAMS if t["rank"] in keep]
    failed_to_fetch: list[dict] = []

    for team in selected:
        print(f"\n=== rank {team['rank']} {team['team_name']} ({team['slug']}) ===")
        if args.stage in ("fetch", "all"):
            ok = fetch_team(team)
            if not ok:
                print(f"[main] {team['slug']}: fetch failed; skipping team")
                failed_to_fetch.append({**team, "reason": "fetch_failed"})
                continue
        if args.stage in ("focus", "all"):
            pick_focus(team, args.limit)
        if args.stage in ("download", "all"):
            download_replays(team)
        if args.stage in ("metrics", "all"):
            run_metrics(team)

    if failed_to_fetch:
        out = TOP_DIR / "_failed_to_fetch.md"
        with out.open("w", encoding="utf-8") as fh:
            fh.write("# Top competitors fetch failures\n\n")
            for t in failed_to_fetch:
                fh.write(f"- rank {t['rank']} `{t['team_name']}` (id `{t['team_id']}`) – {t['reason']}\n")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
