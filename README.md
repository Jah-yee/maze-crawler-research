# Maze Crawler

Local workspace for the Kaggle `maze-crawler` competition.

This repository is the sanitized public research archive. It keeps first-party
experiment variants, evaluation helpers, and written findings while excluding
raw competition inputs, replay corpora, submissions, virtual environments, and
cached third-party baselines. The root baseline was originally derived from the
public Kaggle notebook credited in `docs/research.md`; subsequent variants and
analysis are preserved here with that provenance visible.

## Setup

The Kaggle CLI and local dependencies are installed in `.venv`.

```bash
source .venv/bin/activate
kaggle competitions list --search maze-crawler
```

## Current Baseline

`main.py` is the current submission entry point. It now matches the stable `v24` / `v30` line, which is still the best online performer in this workspace.

- Stable mainline: `main.py` == `experiments/v24_jump_enemy_factory_avoid/main.py`
- Best recent online slot: `v30 stable v24 mainline deployment` with public score `1123.0`
- Best alternate online slot: `v31 alternative v19 delay24 scout deployment` with public score `985.4`
- Current experimental late-game patch: `experiments/v33_targeted_late_patch/main.py` (kept as a research branch, not promoted)

See `docs/research.md` for rule notes, leaderboard snapshot, local evaluation, and improvement plan.

## Evaluate Locally

```bash
.venv/bin/python -m py_compile main.py
.venv/bin/python scripts/evaluate_agents.py --agents main.py --opponent random --seeds 5
```

## Submit

```bash
.venv/bin/kaggle competitions submit maze-crawler \
  -f main.py \
  -m "v1 public top2 jump bfs baseline"
```

If Kaggle API has transient SSL failures, use:

```bash
scripts/submit_with_retry.sh
```
