#!/usr/bin/env python3
"""Run N paired games and count three target failure modes for the defense line.

Modes:
  boundary_scroll: factory ended with gap == 0 (scrolled off / pushed onto south
                   edge) — the dominant v30 failure.
  energy_zero    : factory_energy == 0 at any step while still alive.
  lateral_jcd_lock: at some step factory_gap <= 4 AND f_jump_cd just became 20
                   (i.e. we burned the jump cd via lateral while small gap).

We run agent A as p0 and B as p1, then swap. For each game we record which side
hit each mode. Prints a small table: counts per side over 2*seeds games.

Usage:
  .venv/bin/python scripts/defense_failure_audit.py \
      --a experiments/v46c_jump_cd_save/main.py \
      --b experiments/v37_late_save_jump_no_scout/main.py \
      --seeds 20
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

logging.disable(logging.INFO)

from kaggle_environments import make  # noqa: E402

FACTORY = 0


def audit_game(env_steps, owner: int) -> dict[str, bool]:
    """Walk env.steps, return per-game flags for owner side."""
    out = {"boundary_scroll": False, "energy_zero": False, "lateral_jcd_lock": False}
    prev_jcd = None
    final_step = env_steps[-1]
    obs0 = final_step[0].get("observation") or {}
    south = obs0.get("southBound", 0)
    # walk every step
    for step in env_steps:
        obs = step[0].get("observation") or {}
        robots = obs.get("globalRobots") or obs.get("robots") or {}
        sb = obs.get("southBound", 0)
        # find this owner's factory
        my_fact = None
        for uid, data in robots.items():
            if data[0] == FACTORY and data[4] == owner:
                my_fact = data
                break
        if my_fact is None:
            continue
        row = int(my_fact[2])
        energy = int(my_fact[3])
        gap = row - sb
        jcd = int(my_fact[6]) if len(my_fact) > 6 else 0
        if gap <= 0:
            out["boundary_scroll"] = True
        if energy == 0:
            out["energy_zero"] = True
        if prev_jcd is not None and prev_jcd <= 0 and jcd >= 18 and gap <= 4:
            out["lateral_jcd_lock"] = True
        prev_jcd = jcd
    return out


def play_and_audit(a: str, b: str, seed: int):
    env = make("crawl", configuration={"seed": seed}, debug=False)
    env.run([a, b])
    a_audit = audit_game(env.steps, owner=0)
    b_audit = audit_game(env.steps, owner=1)
    a_reward = env.steps[-1][0].reward
    b_reward = env.steps[-1][1].reward
    return a_audit, b_audit, a_reward, b_reward


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--start-seed", type=int, default=1)
    args = ap.parse_args()

    a_counts = {k: 0 for k in ("boundary_scroll", "energy_zero", "lateral_jcd_lock")}
    b_counts = {k: 0 for k in a_counts}
    a_losses = b_losses = a_wins = b_wins = draws = 0
    games = 0

    for seed in range(args.start_seed, args.start_seed + args.seeds):
        for a_is_p0 in (True, False):
            if a_is_p0:
                a_aud, b_aud, ra, rb = play_and_audit(args.a, args.b, seed)
            else:
                b_aud, a_aud, rb, ra = play_and_audit(args.b, args.a, seed)
            games += 1
            for k in a_counts:
                if a_aud[k]:
                    a_counts[k] += 1
                if b_aud[k]:
                    b_counts[k] += 1
            if ra > rb:
                a_wins += 1
            elif rb > ra:
                b_wins += 1
            else:
                draws += 1

    a_label = Path(args.a).parent.name or args.a
    b_label = Path(args.b).parent.name or args.b
    print(f"{a_label} vs {b_label} over {games} games: A {a_wins}-{b_wins}-{draws}")
    print(f"{'mode':<22}{a_label:>26}{b_label:>26}")
    for k in a_counts:
        ac = a_counts[k]
        bc = b_counts[k]
        delta = ac - bc
        print(f"{k:<22}{ac:>20} ({ac/games:5.1%}){bc:>20} ({bc/games:5.1%})  delta={delta:+d}")


if __name__ == "__main__":
    main()
