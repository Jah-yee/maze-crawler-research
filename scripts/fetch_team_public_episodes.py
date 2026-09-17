#!/usr/bin/env python3
"""Fetch public submissions and simulation episodes for a Kaggle team."""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from kaggle import api
from kagglesdk.competitions.types.competition_api_service import (
    ApiListSubmissionEpisodesRequest,
    ApiListTeamPublicSubmissionsRequest,
)


def call_with_retry(fn, attempts: int = 3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # Kaggle intermittently fails with DNS/SSL errors.
            last_error = exc
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise last_error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-id", type=int, required=True)
    parser.add_argument("--team-name", required=True)
    parser.add_argument("--submissions-out", type=Path, required=True)
    parser.add_argument("--episodes-out", type=Path, required=True)
    args = parser.parse_args()

    submissions = []
    episodes = []
    with api.build_kaggle_client() as kg:
        client = kg.competitions.competition_api_client

        req = ApiListTeamPublicSubmissionsRequest()
        req.team_id = args.team_id
        resp = call_with_retry(lambda: client.list_team_public_submissions(req))
        for sub in resp.submissions:
            submissions.append(
                {
                    "submission_id": sub.id,
                    "date_submitted": sub.date_submitted,
                    "public_score": sub.public_score,
                }
            )

        for sub in submissions:
            ereq = ApiListSubmissionEpisodesRequest()
            ereq.submission_id = int(sub["submission_id"])
            eresp = call_with_retry(lambda req=ereq: client.list_submission_episodes(req))
            for episode in eresp.episodes:
                row = {
                    "submission_id": sub["submission_id"],
                    "submission_public_score": sub["public_score"],
                    "id": episode.id,
                    "createTime": episode.create_time,
                    "endTime": episode.end_time,
                    "state": episode.state,
                    "type": episode.type,
                }
                for agent in episode.agents:
                    prefix = f"agent_{agent.index}"
                    row[f"{prefix}_submission_id"] = agent.submission_id
                    row[f"{prefix}_reward"] = agent.reward
                    row[f"{prefix}_state"] = agent.state
                    row[f"{prefix}_team_name"] = agent.team_name
                    row[f"{prefix}_team_id"] = agent.team_id
                    if agent.team_id == args.team_id or agent.team_name == args.team_name:
                        row["team_index"] = agent.index
                        row["team_reward"] = agent.reward
                        row["opponent_index"] = 1 - agent.index
                opponent_index = row.get("opponent_index")
                if opponent_index is not None:
                    prefix = f"agent_{opponent_index}"
                    row["opponent_team_name"] = row.get(f"{prefix}_team_name", "")
                    row["opponent_team_id"] = row.get(f"{prefix}_team_id", "")
                    row["opponent_submission_id"] = row.get(f"{prefix}_submission_id", "")
                    row["opponent_reward"] = row.get(f"{prefix}_reward", "")
                episodes.append(row)

    args.submissions_out.parent.mkdir(parents=True, exist_ok=True)
    with args.submissions_out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["submission_id", "date_submitted", "public_score"])
        writer.writeheader()
        writer.writerows(submissions)

    episode_fields = [
        "submission_id",
        "submission_public_score",
        "id",
        "createTime",
        "endTime",
        "state",
        "type",
        "team_index",
        "team_reward",
        "opponent_index",
        "opponent_team_name",
        "opponent_team_id",
        "opponent_submission_id",
        "opponent_reward",
        "agent_0_submission_id",
        "agent_0_reward",
        "agent_0_state",
        "agent_0_team_name",
        "agent_0_team_id",
        "agent_1_submission_id",
        "agent_1_reward",
        "agent_1_state",
        "agent_1_team_name",
        "agent_1_team_id",
    ]
    with args.episodes_out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=episode_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(episodes)

    public_count = sum(str(row["type"]) == "EpisodeType.EPISODE_TYPE_PUBLIC" for row in episodes)
    print(
        f"wrote {args.submissions_out} ({len(submissions)} submissions) and "
        f"{args.episodes_out} ({len(episodes)} episodes, {public_count} public)"
    )


if __name__ == "__main__":
    main()
