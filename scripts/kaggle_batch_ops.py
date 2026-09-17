#!/usr/bin/env python3
"""Small Kaggle helpers for the Maze Crawler workflow."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / ".venv" / "bin" / "kaggle"


def run_kaggle(*args: str) -> str:
    last_output = ""
    for attempt in range(1, 4):
        try:
            proc = subprocess.run(
                [str(KAGGLE), *args],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=90,
            )
        except subprocess.TimeoutExpired as exc:
            last_output = exc.stdout or ""
            if attempt < 3:
                time.sleep(2 * attempt)
                continue
            raise subprocess.CalledProcessError(124, [str(KAGGLE), *args], output=last_output) from exc
        last_output = proc.stdout
        if proc.returncode == 0:
            return proc.stdout
        if attempt < 3:
            time.sleep(2 * attempt)
    raise subprocess.CalledProcessError(proc.returncode, proc.args, output=last_output)


def parse_csv_prefix(text: str) -> list[dict[str, str]]:
    lines = []
    for line in text.splitlines():
        if not line.strip():
            break
        if line.startswith("Use "):
            break
        lines.append(line)
    return list(csv.DictReader(lines))


def factory_state(agent_step: dict) -> tuple[int, int, int] | None:
    obs = agent_step.get("observation") or {}
    player = obs.get("player")
    for robot in (obs.get("robots") or {}).values():
        if robot[0] == 0 and robot[4] == player:
            return robot[1], robot[2], robot[3]
    return None


def summarize_replay(path: Path, team_name: str) -> dict[str, object]:
    data = json.loads(path.read_text())
    info = data.get("info", {})
    names = info.get("TeamNames") or [a.get("Name") for a in info.get("Agents", [])]
    steps = data.get("steps") or []
    rewards = data.get("rewards") or []
    statuses = data.get("statuses") or []
    our_index = None
    for i, name in enumerate(names):
        if name == team_name:
            our_index = i
            break
    if our_index is None:
        our_index = 0
    opp_index = 1 - our_index if len(names) == 2 else None
    winner = "draw"
    if len(rewards) == 2 and rewards[0] != rewards[1]:
        winner = names[0] if rewards[0] > rewards[1] else names[1]
    our_reward = rewards[our_index] if len(rewards) > our_index else ""
    opp_reward = rewards[opp_index] if opp_index is not None and len(rewards) > opp_index else ""
    if isinstance(our_reward, (int, float)) and isinstance(opp_reward, (int, float)):
        our_result = "win" if our_reward > opp_reward else ("loss" if our_reward < opp_reward else "draw")
    else:
        our_result = "win" if winner == team_name else ("draw" if winner == "draw" else "loss")

    death_steps = []
    last_factories = []
    for idx in range(len(names)):
        missing = None
        for step_idx, step in enumerate(steps):
            if factory_state(step[idx]) is None:
                missing = step_idx
                break
        death_steps.append(missing)
        last_factories.append(factory_state(steps[-1][idx]) if steps else None)

    return {
        "episode_id": info.get("EpisodeId") or path.stem.split("-")[1],
        "seed": (data.get("configuration") or {}).get("seed"),
        "teams": "|".join(str(x) for x in names),
        "our_index": our_index,
        "opponent": names[opp_index] if opp_index is not None else "",
        "reward_0": rewards[0] if len(rewards) > 0 else "",
        "reward_1": rewards[1] if len(rewards) > 1 else "",
        "our_reward": our_reward,
        "opp_reward": opp_reward,
        "winner": winner,
        "our_result": our_result,
        "status_0": statuses[0] if len(statuses) > 0 else "",
        "status_1": statuses[1] if len(statuses) > 1 else "",
        "steps": len(steps),
        "death_step_0": death_steps[0] if len(death_steps) > 0 else "",
        "death_step_1": death_steps[1] if len(death_steps) > 1 else "",
        "our_death_step": death_steps[our_index] if len(death_steps) > our_index else "",
        "opp_death_step": death_steps[opp_index] if opp_index is not None and len(death_steps) > opp_index else "",
        "last_factory_0": last_factories[0] if len(last_factories) > 0 else "",
        "last_factory_1": last_factories[1] if len(last_factories) > 1 else "",
        "replay_path": str(path.resolve().relative_to(ROOT)),
    }


def episodes(args: argparse.Namespace) -> None:
    text = run_kaggle("competitions", "episodes", args.submission_id, "-v")
    rows = parse_csv_prefix(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        args.out.unlink()
    if not rows:
        print(f"no episodes for {args.submission_id}")
        return
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.out} ({len(rows)} rows)")


def download_replays(args: argparse.Namespace) -> None:
    if not args.episodes.exists():
        print(f"episodes file not found: {args.episodes}")
        return
    rows = list(csv.DictReader(args.episodes.open(encoding="utf-8")))
    args.replay_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    failed = []
    for row in rows:
        if row.get("type") != "EpisodeType.EPISODE_TYPE_PUBLIC":
            continue
        episode_id = row["id"]
        target = args.replay_dir / f"episode-{episode_id}-replay.json"
        if target.exists() and not args.force:
            continue
        try:
            run_kaggle("competitions", "replay", episode_id, "-p", str(args.replay_dir))
        except subprocess.CalledProcessError:
            if not args.keep_going:
                raise
            failed.append(episode_id)
            print(f"failed {episode_id}")
            continue
        downloaded += 1
        print(f"downloaded {episode_id}")
        if args.limit and downloaded >= args.limit:
            break
    print(f"downloaded {downloaded} replay(s)")
    if failed:
        print(f"failed {len(failed)} replay(s): {','.join(failed)}")


def summarize(args: argparse.Namespace) -> None:
    paths = sorted(args.replay_dir.glob("episode-*-replay.json"))
    if not paths:
        print(f"no replays in {args.replay_dir}")
        return
    rows = [summarize_replay(path, args.team_name) for path in paths]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    wins = sum(r["our_result"] == "win" for r in rows)
    losses = sum(r["our_result"] == "loss" for r in rows)
    draws = sum(r["our_result"] == "draw" for r in rows)
    print(f"wrote {args.out} ({wins}-{losses}-{draws})")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("episodes")
    p.add_argument("submission_id")
    p.add_argument("--out", type=Path, default=ROOT / "reports" / "episodes_53283498.csv")
    p.set_defaults(func=episodes)

    p = sub.add_parser("download-replays")
    p.add_argument("--episodes", type=Path, default=ROOT / "reports" / "episodes_53283498.csv")
    p.add_argument("--replay-dir", type=Path, default=ROOT / "reports" / "replays")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--force", action="store_true")
    p.add_argument("--keep-going", action="store_true")
    p.set_defaults(func=download_replays)

    p = sub.add_parser("summarize")
    p.add_argument("--replay-dir", type=Path, default=ROOT / "reports" / "replays")
    p.add_argument("--out", type=Path, default=ROOT / "reports" / "replay_summary.csv")
    p.add_argument("--team-name", default="Jiayi Du")
    p.set_defaults(func=summarize)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
