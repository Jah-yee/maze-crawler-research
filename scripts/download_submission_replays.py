#!/usr/bin/env python3
"""Download replay JSONs for selected submission IDs from an episodes CSV."""

from __future__ import annotations

import argparse
import csv
import subprocess
import time
from pathlib import Path


def run(cmd: list[str], attempts: int = 4) -> bool:
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode == 0:
            return True
        if attempt == attempts:
            print(proc.stdout.rstrip())
            return False
        time.sleep(2 * attempt)
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--submission-id", action="append", required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--kaggle", default=".venv/bin/kaggle")
    args = parser.parse_args()

    wanted = set(args.submission_id)
    with args.episodes.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    selected = [
        row for row in rows
        if row.get("submission_id") in wanted and row.get("type") == "EpisodeType.EPISODE_TYPE_PUBLIC"
    ]
    print(f"selected {len(selected)} public episodes for {sorted(wanted)}")

    ok = fail = 0
    for row in selected:
        sub_id = row["submission_id"]
        episode_id = row["id"]
        out_dir = args.out_root / sub_id / "replays"
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"episode-{episode_id}-replay.json"
        if target.exists() and target.stat().st_size > 0:
            ok += 1
            continue
        cmd = [args.kaggle, "competitions", "replay", episode_id, "-p", str(out_dir)]
        if run(cmd):
            ok += 1
        else:
            fail += 1
            print(f"failed episode {episode_id} submission {sub_id}")
    print(f"downloaded ok={ok} fail={fail}")


if __name__ == "__main__":
    main()
