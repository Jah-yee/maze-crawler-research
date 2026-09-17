#!/usr/bin/env python3
"""Replay the agent on the exact factory planning step that died online.

Loads a Kaggle replay JSON, picks the agent step right before the loss, and
asks the candidate agent module what action it would take given the same
observation/configuration. We then print the original (recorded) factory
action vs the candidate's factory action so we can verify that a fix
actually flips the decision at the failing turn.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import types
from pathlib import Path


FACTORY = 0


def load_agent(module_path: Path):
    spec = importlib.util.spec_from_file_location("candidate_agent", str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {module_path}")
    mod = importlib.util.module_from_spec(spec)
    # Make sure module state (global memory dict) is fresh per replay.
    spec.loader.exec_module(mod)
    return mod.agent


def make_namespace(obj):
    """Top-level dict becomes SimpleNamespace, nested dicts stay as dicts.

    Agents in this repo access obs.robots, obs.walls etc. via attribute
    access, but iterate the values like obs.robots.items() expecting a
    real dict. We mirror that contract here.
    """
    if isinstance(obj, dict):
        return types.SimpleNamespace(**obj)
    return obj


def find_factory_uid(robots: dict, owner: int) -> str | None:
    for uid, r in robots.items():
        if r[0] == FACTORY and r[4] == owner:
            return uid
    return None


def step_obs(step_state, owner_index, full_config):
    """Return obs and config namespaces for the candidate agent."""
    raw_obs = step_state[owner_index].get("observation") or {}
    if not raw_obs:
        return None, None
    # Merge globalRobots into robots so the agent sees the same data the
    # replay had at this turn.
    obs_dict = dict(raw_obs)
    if "globalRobots" in obs_dict and "robots" not in obs_dict:
        obs_dict["robots"] = obs_dict["globalRobots"]
    obs_dict.setdefault("player", owner_index)
    obs_dict.setdefault("step", obs_dict.get("step", 0))
    obs_dict.setdefault("crystals", obs_dict.get("crystals", {}))
    obs_dict.setdefault("walls", obs_dict.get("walls", []))
    obs_dict.setdefault("mines", obs_dict.get("mines", {}))
    obs_dict.setdefault("miningNodes", obs_dict.get("miningNodes", {}))
    obs_ns = make_namespace(obs_dict)
    cfg_ns = make_namespace(full_config)
    return obs_ns, cfg_ns


def run(replay_path: Path, candidate_path: Path, team_name: str) -> dict:
    data = json.loads(replay_path.read_text())
    steps = data.get("steps") or []
    info = data.get("info", {})
    config = data.get("configuration") or {}
    names = info.get("TeamNames") or [a.get("Name") for a in info.get("Agents", [])]

    our_index = 0
    for idx, name in enumerate(names):
        if name == team_name:
            our_index = idx
            break

    death_step = None
    for idx, step in enumerate(steps):
        raw_obs = step[0].get("observation") or {}
        robots = raw_obs.get("globalRobots") or raw_obs.get("robots") or {}
        if find_factory_uid(robots, our_index) is None:
            death_step = idx
            break

    if death_step is None:
        return {"replay": replay_path.name, "death_step": None, "note": "no factory death"}

    # In the Kaggle Crawl replay format, steps[i].observation is the obs
    # the agent saw when deciding steps[i].action. The action that LED to
    # the death is therefore at steps[death_step - 1] (it resolves into
    # the state at steps[death_step] where the factory is already gone).
    plan_step = max(0, death_step - 1)

    agent = load_agent(candidate_path)

    candidate_factory_action = None
    candidate_actions = None
    for idx in range(plan_step + 1):
        obs_ns, cfg_ns = step_obs(steps[idx], our_index, config)
        if obs_ns is None:
            continue
        try:
            actions = agent(obs_ns, cfg_ns)
        except Exception as e:
            return {
                "replay": replay_path.name,
                "death_step": death_step,
                "plan_step": plan_step,
                "error": f"agent crashed at step {idx}: {e}",
            }
        if idx == plan_step:
            candidate_actions = actions
            our_obs = steps[idx][our_index].get("observation") or {}
            robots = our_obs.get("robots") or {}
            fac_uid = find_factory_uid(robots, our_index)
            candidate_factory_action = actions.get(fac_uid) if fac_uid else None

    recorded_actions = (steps[plan_step][our_index].get("action") or {})
    our_obs = steps[plan_step][our_index].get("observation") or {}
    robots = our_obs.get("robots") or {}
    fac_uid = find_factory_uid(robots, our_index)
    recorded_factory_action = recorded_actions.get(fac_uid) if fac_uid else None

    return {
        "replay": replay_path.name,
        "death_step": death_step,
        "plan_step": plan_step,
        "factory_uid": fac_uid,
        "recorded_factory_action": recorded_factory_action,
        "candidate_factory_action": candidate_factory_action,
        "diverged": recorded_factory_action != candidate_factory_action,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--episodes", nargs="+", required=True, help="episode ids")
    parser.add_argument("--team-name", default="Jiayi Du")
    args = parser.parse_args()

    for ep in args.episodes:
        path = args.replay_dir / f"episode-{ep}-replay.json"
        if not path.exists():
            print(f"{ep}: replay not found at {path}")
            continue
        result = run(path, args.candidate, args.team_name)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
