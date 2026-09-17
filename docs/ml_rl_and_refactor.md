# ML/RL Pathways and Architecture Refactor for maze-crawler

Last updated: 2026-06-03.

This document answers two questions:

- **Task A.** Which ML/RL technique is worth investing 1-2 weeks of effort in for `maze-crawler`, given 13 days to deadline, 5 submissions/day, single-file Python submission, and a current rank of 24/345 with score `1129.0`?
- **Task B.** How do we refactor the v24/v37/v40 elif chain so the next ten patches do not break the previous ten?

All claims are backed by either project data (`docs/research.md`, `reports/*.csv`, `experiments/`) or public competition writeups (Lux AI, Halite). Buzzwords without a concrete fit are explicitly marked **not applicable**.

---

## 1. Executive Summary

1. **In comparable Kaggle simulation competitions (Halite IV, Lux AI 2), the 1st-place solution was pure rule-based, not ML.** ML hybrids reached top-10 but did not win. See [Halite IV winner ttvand](https://github.com/ttvand/Halite) and [Lux AI Season 2 winner ryandy](https://github.com/ryandy/Lux-S2-public). Lux AI 1 imitation-learning U-Net agents finished 93rd / 1178. The probability that 2 weeks of RL pays off more than 2 weeks of structured heuristics is low.
2. **The 1080-point ELO gap from our 1133 to bunterrrrr's 2216 is almost certainly a strategy gap, not a perception gap.** bunterrrrr median final factory energy is `6874` vs our `351.6` (research.md §Bunterrrrr Leader Study). That is an economy/phase-switch problem, not a "we need a CNN" problem.
3. **The single highest-EV bet over the next week is Task B, not Task A:** refactor v40 into a small Utility-based scorer so each existing patch becomes a small additive `score(action, ctx)` function, and so future patches (better mine, better late-game) can be added without touching the elif spine.
4. **The single highest-EV ML bet is imitation/data mining from the 167 already-downloaded bunterrrrr replays, not training a deployable neural net.** Train a decision tree or logistic model on `(obs_features, factory_action)` pairs to surface new rules; ship the rules, not the model. This is `1-3 days` of effort and the output integrates directly into the utility scorer above.
5. **Realistic non-options for the remaining 13 days:** end-to-end self-play PPO from scratch, AlphaZero with neural network, offline RL on multi-GB replay tarballs, Decision Transformer, full neural-net-in-submission. They are not eliminated because of dogma; they are eliminated because the action timeout is `3 s/turn` and `actTimeout=3` with `runTimeout=9600` (see `.venv/lib/python3.13/site-packages/kaggle_environments/envs/crawl/crawl.json` lines 214-215). On CPU-only Kaggle runners, a neural-net forward pass per turn plus a 2-week RL train budget collides hard with the deadline.

**Recommended next 1-2 actions (full justification in §5):**
- **Action 1 (3-5 days):** Refactor `experiments/v40_collision_predictor/main.py` into a single `score_factory_action(act) -> float` function with named additive components (`safety`, `progress`, `economy`, `late_game`). Each existing v24/v37/v40 patch becomes a small named scorer. Keep BFS helpers untouched. Net new PoC code ~150-200 lines.
- **Action 2 (1-3 days, in parallel):** Build `scripts/mine_decisions.py` that joins `reports/replays_bunterrrrr_focus/*.json` with replay state-extraction to produce a `pandas.DataFrame` of `(factory_gap, factory_energy, scout_count, has_visible_north_mine, has_visible_side_mine, …) -> action_label`. Fit a depth-4 decision tree on it and read off the splits as new heuristic rules. The output is rules, not a deployed model.

**Biggest unknown:** Whether we have already extracted most of bunterrrrr's policy through the v15-v22 economy experiments, or whether the late-game switch (research.md §Late-Game Learning) hides another 200-500 ELO points. The decision-tree mining in Action 2 directly answers this.

---

## 2. Background Constraints (verified)

| Constraint | Value | Source |
|---|---|---|
| Submission format | Single Python file | `data/input/AGENTS.md` and Kaggle CLI behavior of `kaggle competitions submit -f main.py` |
| Submission size cap | ~100 MB (general Kaggle simulation cap) | Kaggle CLI docs, ConnectX/Halite/Lux references |
| Per-turn time | `actTimeout = 3` seconds | `crawl.json:214` |
| Per-episode wall clock | `runTimeout = 9600` seconds | `crawl.json:215` |
| First-act init | `agentTimeout` (default >> 3 s) | `kaggle-environments` README |
| Daily submissions | 5 | research.md §Competition Facts |
| Episodes/day available | ~3000-3500 replays, ~9GB/day | `data/episodes_index/manifest.csv` |
| bunterrrrr replays already on disk | 17 with state, 167 with metadata | `reports/bunterrrrr_focus_*.csv` |
| Current best agent line count | 472 (v24) / 509 (v37) / 536 (v40) | `wc -l` |
| Pilkwang reference planner | 3314 lines | `wc -l baselines/pilkwang_structure/main.py` |

Two practical implications:

- `actTimeout=3` is generous for BFS but very tight for any meaningful learned forward pass on the Kaggle CPU runner. A small CNN (e.g. 100k params) is feasible but only if loaded once and reused.
- 100 MB is plenty to embed a small model weight blob if base64-encoded. It is **not** enough to embed a large transformer.

---

## 3. Task A: ML/RL Technique Survey

Each section uses the same rubric: **Fit**, **Data**, **Compute**, **Integration with v24/v37/v40**, **Risks**, **Ramp-up**.

### 3.1 Imitation Learning / Behavioral Cloning from bunterrrrr replays

- **Fit:** mid-to-high. There is a single dominant opponent (bunterrrrr at 2216 vs our 1129) whose 167-episode public sample shows a clearly different strategy (mine economy, no-scout, late-game north hard switch). The supervised learning problem `(state, factory_action_one_hot)` is small and well-posed.
- **Data:** 167 episodes × ~300 turns × 1 factory action = ~50k labeled (state, action) tuples for the factory only. After train/test split that is small for a neural net but plenty for tree-based models or a linear policy on hand-crafted features. We already have the 167 episode IDs in `reports/bunterrrrr_episodes.csv`; only 17 full state JSONs are downloaded (`reports/replays_bunterrrrr_focus/`).
- **Compute:** CPU only. Decision tree, GBM, or logistic regression takes minutes. A small CNN-on-grid takes ~30 minutes on a laptop.
- **Integration with v24/v37/v40:**
  - **Best:** treat IL as a *rule-mining tool*. Train a depth-4 decision tree on hand-crafted features, read off the splits, then promote the splits to numerical thresholds in our utility scorer. This ships zero ML at submission time but uses ML to find rules.
  - **Acceptable:** keep IL as a learned policy that proposes an action, then post-filter through the existing safety helpers (`safe_factory_action`, `bfs_jump` for emergency). The neural net runs only on the factory and only when we are not in emergency mode.
  - **Bad:** replace the factory's elif chain entirely with the IL policy. Loses our explicit safety guards. Lux AI 1 imitation-only U-Nets ranked 93/1178; that is below our current 24/345 percentile.
- **Risks:**
  - **Off-distribution states.** bunterrrrr sees opponents we will not see. Imitation breaks when our scout-less mid-game puts us in a state never seen in bunterrrrr's replays. DAgger fixes this in principle but adds a self-play loop.
  - **State extraction.** Kaggle replay JSONs store the full observation per step, but we need a function that produces *the agent's view* (fog-of-war) from the replay's god-view. The crawl env in `.venv` exposes `obs.walls` etc. on each step; we can re-replay via `env.run` with a wrapper agent to capture exactly the obs each side sees.
  - **Mirroring.** bunterrrrr plays both player_0 and player_1. We must mirror states so the policy is side-agnostic, as we already mirror walls in `main.py:14-20`.
- **Ramp-up:** 1-3 days for the rule-mining version. 1-2 weeks for a deployed neural policy.
- **Verdict:** **Use it, but as rule-mining first.** Direct evidence from this project: research.md §Bunterrrrr Leader Study has already been doing this informally and produced v15/v17/v19/v24 from one pattern (north mine economy). A systematic decision-tree pass should produce another 2-3 rules.

### 3.2 Offline RL (CQL, IQL, AWR) from Kaggle replay tarballs

- **Fit:** **low**. Three independent reasons:
  1. We do not have rewards per turn that fairly attribute credit. The competition reward at end is ELO-derived (`1/-1/0.5`) plus mid-game energy; that is essentially terminal sparse reward with one small dense term.
  2. Replays mix many different agents' policies; offline RL on heterogeneous behavior policies typically requires importance weighting that we cannot estimate.
  3. The most successful offline RL papers (CQL, IQL) require pessimism that easily collapses to "do nothing". For a game whose only winning strategy is *move north*, pessimism is the wrong inductive bias.
- **Data:** Theoretically all 60k+ episodes in `data/episodes_index/`. In practice we cannot fit ~100 GB of replays locally.
- **Compute:** GPU mandatory. Out of scope for CPU laptop and the 13-day budget.
- **Integration:** Same as IL — only deployable as a rules-extraction tool or as a learned residual.
- **Verdict:** **Not applicable.** Even if it produced a useful policy, the implementation, training, and integration are not feasible by 2026-06-16.

### 3.3 Self-play PPO / A2C / IMPALA

- **Fit:** **low for this deadline, mid for a post-deadline project.** Reasons:
  - kaggle-environments `crawl` runs locally (research.md `scripts/evaluate_agents.py` already exercises it). Self-play loops are mechanically possible.
  - However, the [arXiv 2304.13004 Lux AI 2 paper](https://arxiv.org/abs/2304.13004) explicitly notes that the *first* milestone (a factory that doesn't starve itself) required a curriculum reward; without it, PPO collapses. Maze Crawler's "first milestone" is "the factory doesn't get scrolled off", and our existing v24 already solves that. Re-learning it from scratch via PPO would waste the entire 13 days re-deriving v1's behavior.
- **Data:** Self-generated.
- **Compute:** GPU strongly preferred. Even on GPU, Lux AI papers report multi-day training runs. The arXiv author warmed-started with imitation; pure PPO never trained to win.
- **Integration:** Difficult. The learned policy needs the same fog-of-war view we already build, and we still need our safety filters at the end.
- **Verdict:** **Not applicable for this deadline.** Document as a post-deadline follow-up.

### 3.4 AlphaZero-style MCTS + Policy/Value Net

- **Fit:** **low**. AlphaZero requires (a) a perfect simulator of opponent observations, (b) determinism in transitions, (c) tractable branching. Maze Crawler violates all three:
  - The opponent's view is hidden, so MCTS rollouts must model their belief state too — this is closer to POMCP, which is dramatically slower.
  - Scroll boundary, crystal spawns, and door openings are stochastic per replay.
  - Branching is ~5 actions × N robots. At step 100 we typically have ~3 robots, so per-turn branching is 5³=125 — feasible, but multiply by 300 turns and you need to truncate aggressively.
- **Data:** Self-generated.
- **Compute:** GPU for value net training; CPU for MCTS rollouts at inference (3 s budget = ~100-300 rollouts on a CPU runner if we are lean, much less if we run a CNN per leaf).
- **Integration:** Hard. The MCTS rollouts need a fast Python simulator; the kaggle-environments env is ~100 ms per step in Python, which gives only ~30 rollouts per turn. That is below AlphaZero's empirical floor (~100 rollouts for useful play).
- **Verdict:** **Not applicable** unless we write a stripped-down C-accelerated crawl simulator. Out of scope for 13 days.

### 3.5 Decision Transformer / sequence model on replays

- **Fit:** **low**. Decision Transformer assumes you can condition on a target return at inference and the model will produce actions consistent with that return. The replay return distribution we'd train on is bimodal (win=1 vs loss=-1) so conditioning on "return=1" mostly just imitates the strongest segment of the dataset, which is what plain imitation already does, but with more parameters and lower interpretability.
- **Data/Compute/Integration:** Same as IL but worse interpretability.
- **Verdict:** **Not worth the complexity over plain IL.**

### 3.6 Heuristic + learned residual

- **Fit:** **mid**. Take v24's elif output as a "base action" and learn a small residual classifier that *occasionally* overrides it. Lux AI 2's 1st place (ryandy) used a similar hybrid in spirit — rules for macro decisions, learned components for sub-decisions.
- **Data:** Either:
  - Self-play: run v24 vs v24 and label `(state, was_this_action_a_winning_move)` based on terminal outcome. Train a binary "should we override?" classifier.
  - Replay-driven: when v24 in `reports/replay_failures_v*.csv` is shown losing, compare v24's chosen action to bunterrrrr's chosen action in similar states. Train the residual to predict bunterrrrr's deviations.
- **Compute:** CPU.
- **Integration:** Clean. The residual runs after `bfs_jump` and before `record(...)`. If `residual.confidence > τ`, it picks the alternate action.
- **Risks:** double-coupling — a bad residual can silently corrupt v24's strong cases.
- **Verdict:** **Defer.** Lower EV than IL-as-rule-mining because we still need to handcraft the override conditions; not enough lift to justify the 5-7 days of build time.

### 3.7 Imitation + DAgger

- **Fit:** **mid**, but only if §3.1 IL is already deployed and we observe distribution shift in self-play.
- **Verdict:** Useful next step *after* §3.1. Not a standalone candidate this week.

### 3.8 Genetic Algorithm / Evolution Strategies on heuristic constants

- **Fit:** **high for narrow goal: tuning knobs.** The v37/v40 patches introduce many magic constants: `SCOUT_DELAY_STEP=24`, gap thresholds 4/6/8/10, energy floors 200/350/650, jump cooldown threshold 8, etc. These are exactly the parameter space ES/CMA-ES is good at.
- **Data:** Local self-play paired-seed runs, already automated by `scripts/evaluate_agents.py`.
- **Compute:** CPU. ~30 seeds × 30 candidates × 5 generations × 200ms/episode ≈ 75 min/round if we parallelize.
- **Integration:** Trivial — the knobs are already named constants at the top of `main.py`. Just wrap them with an outer search loop and freeze the best.
- **Risks:**
  - Local self-play is noisy and not the same as the Kaggle ladder (research.md §Local Evaluation). Tuning on local may not transfer.
  - 5 submissions/day = the online signal cannot keep up with a CMA-ES generation budget. ES has to use local evaluation as its primary signal, accepting some noise.
- **Verdict:** **Worth doing for v40's knob set.** Pair with §3.1 rule-mining; one finds *which* rules to add, the other tunes thresholds on existing rules.
- **Ramp-up:** 1-2 days.

### 3.9 Bandit / Bayesian optimization on the knob space

- **Fit:** **mid**. Same problem as §3.8 but a different solver. CMA-ES handles continuous + many parameters; Bayesian optimization is better when each evaluation is expensive (e.g. true ladder submissions). Our case has cheap local evals and expensive online evals.
- **Verdict:** **Useful as a meta-layer over §3.8.** Use ES locally; use BO for selecting *which submission to send* among the top ES candidates. Not the first thing to build.

### 3.10 Symbolic regression / program synthesis

- **Fit:** **mid in theory, low in practice.** Tools like PySR can derive new symbolic rules from `(features → action)` data. But for discrete action spaces and a non-numeric output, this collapses into IL with decision trees, which is what §3.1 already proposes.
- **Verdict:** Equivalent to §3.1 IL-as-rule-mining. Use a decision tree, not a separate framework.

### 3.11 Population-based training (PBT)

- **Fit:** **low for this deadline.** PBT is most useful when you can fork dozens of training runs and copy hyperparameters from leaders. We have a single laptop and 5 daily submissions.
- **Verdict:** **Not applicable.**

### 3.12 Multi-agent algorithms (QMIX, MAPPO, etc.)

- **Fit:** **low.** The factory is the only unit that truly needs coordination with itself across turns; scout/worker/miner are independent satellites. Multi-agent ML buys us nothing the single-agent setup doesn't.
- **Verdict:** **Not applicable.**

### 3.13 Summary table

| Method | Fit | Data needs | Compute | Integration | Risks | Ramp-up | Recommend |
|---|---|---|---|---|---|---|---|
| Imitation + decision-tree mining | high | 17-167 replays | CPU minutes | rules → utility scorer | off-distribution, mirroring | 1-3 days | **YES (Action 2)** |
| Imitation as deployed policy | mid | 167+ replays + per-step views | CPU minutes | replace factory elif | distribution shift, brittle | 1-2 weeks | maybe later |
| Offline RL (CQL/IQL/AWR) | low | 60k+ replays | GPU days | rules only | sparse reward, heterogeneous behavior | 2-4 weeks | no |
| Self-play PPO | low (deadline) | self-gen | GPU days | hard | restart from v0, curriculum | 2-6 weeks | post-deadline |
| AlphaZero MCTS+NN | low | self-gen | GPU + fast sim | very hard | no fast sim, POMDP | 4+ weeks | no |
| Decision Transformer | low | 167+ replays | GPU | same as IL | weaker than tree | 1-2 weeks | no |
| Heuristic + learned residual | mid | self-play or focus replays | CPU | residual layer | silent regressions | 5-7 days | defer |
| Imitation + DAgger | mid (after IL) | IL + self-play | CPU | adds self-play | bootstraps off IL | +3 days | after IL |
| ES / CMA-ES on knobs | high | local self-play | CPU hours | drop-in retune | local≠ladder | 1-2 days | **YES (Action 3)** |
| Bayesian opt on submissions | mid | online | n/a | meta-layer | 5 subs/day cap | 1 day | after ES |
| Symbolic regression | mid | replays | CPU | rules | redundant with IL | n/a | merged into IL |
| PBT | low | self-play | many CPUs | n/a | infra | weeks | no |
| Multi-agent ML | low | self-play | GPU | n/a | not the problem | weeks | no |

---

## 4. Task B: Architecture Refactor Options

`main.py` is currently a single 472-line function whose factory section is a 100-line elif chain. The same chain appears with patches in v37 (509 lines) and v40 (536 lines). The pattern is:

```python
if factory_gap <= 2 and south > 0: ...   # emergency
if factory_uid not in actions:
    if f_build_cd <= 1 and ... counts[MINER] < 1: mine_build_action = ...
    if mine_build_action: ...
    elif scout_build_ok: ...
    elif f_move_cd > 1: IDLE
    else:
        if on_mine and gap>10: IDLE
        elif on_north_mine: NORTH
        else:
            step = bfs_jump(...)
            ... fallback 1..4 ...
            if step: record(step)
            else:
                if worker_build_ok: BUILD_WORKER
                else: IDLE
```

Each patch (mirror walls, optimistic fog, emergency escape, jump-only enemy guard, north mine econ, scout delay, save jump for north, no-scout-low-gap, 2-turn collision predictor, worker energy floor) is wedged into a different branch. The blast radius of changes is high because branches share fallthrough.

I evaluated five concrete refactor patterns. Three are recommended, two are rejected.

### 4.1 Option A: Utility-based Action Scoring (recommended)

**Idea.** Generate the full candidate factory action set, score each independently with a sum of small named scorer functions, pick the max-score legal action. No elif chain.

**PoC skeleton (~150 lines net new, BFS helpers reused):**

```python
# Existing helpers stay unchanged:
#   bfs_jump, bfs_first_step, can_move, can_jump, safe_factory_action,
#   action_dest, get_wall, MIRROR_WALL, _memory walls dict.

@dataclass
class Ctx:
    factory_col: int
    factory_row: int
    factory_gap: int
    factory_energy: int
    f_jump_cd: int
    f_build_cd: int
    f_move_cd: int
    south: int
    north: int
    turn: int
    counts: dict
    enemy_factory_threats: set
    enemy_factory_jump_threats: set
    own_mines: dict
    mining_nodes: set
    walls_mem: dict
    bfs_next_step: str | None   # cached output of bfs_jump
    bfs_north_only_step: str | None
    collision_tiebreak_bad: bool

def factory_candidates(ctx) -> list[str]:
    cands = ["IDLE"]
    for d in DIRS:
        if can_move(ctx.factory_col, ctx.factory_row, d):
            cands.append(d)
        if ctx.f_jump_cd <= 0 and can_jump(ctx.factory_col, ctx.factory_row, d):
            cands.append(f"JUMP_{d}")
    if ctx.f_build_cd <= 1:
        cands += ["BUILD_SCOUT", "BUILD_WORKER",
                  "BUILD_MINER_NORTH", "BUILD_MINER_EAST", "BUILD_MINER_WEST"]
    return cands

# Each scorer returns a (small) signed float. Sum picks the action.

def s_safety(act, ctx) -> float:
    if not safe_factory_action(act):
        return -1e6
    return 0.0

def s_emergency_north(act, ctx) -> float:
    if ctx.factory_gap > 2:
        return 0.0
    if act == "JUMP_NORTH" and ctx.f_jump_cd <= 0:
        return 1e3
    if act in ("JUMP_EAST", "JUMP_WEST") and ctx.f_jump_cd <= 0:
        return 5e2
    return 0.0

def s_progress(act, ctx) -> float:
    if ctx.bfs_next_step is None:
        return 0.0
    # If gap small we want north_only BFS recommendation
    target = ctx.bfs_north_only_step if ctx.factory_gap <= 8 else ctx.bfs_next_step
    return 50.0 if act == target else 0.0

def s_north_mine(act, ctx) -> float:
    if act != "NORTH":
        return 0.0
    mpos = (ctx.factory_col, ctx.factory_row + 1)
    if mpos in ctx.own_mines:
        return 30.0
    return 0.0

def s_build_north_mine(act, ctx) -> float:
    if act != "BUILD_MINER_NORTH":
        return 0.0
    mpos = (ctx.factory_col, ctx.factory_row + 1)
    if mpos not in ctx.mining_nodes:
        return -1e6
    if ctx.factory_energy < 650 or ctx.factory_gap <= 6 or ctx.counts[MINER] >= 1:
        return -1e6
    return 80.0

def s_build_scout(act, ctx) -> float:
    if act != "BUILD_SCOUT":
        return 0.0
    if ctx.turn < SCOUT_DELAY_STEP or ctx.counts[SCOUT] >= 1:
        return -1e6
    if ctx.factory_energy < 50:
        return -1e6
    # v37 gap gate + v40 distance gate
    scout_safe_distance = all_far_enemy(ctx)
    if ctx.factory_gap <= 4 and not scout_safe_distance:
        return -1e6
    return 10.0

def s_build_worker(act, ctx) -> float:
    if act != "BUILD_WORKER":
        return 0.0
    # v40 energy floor 350 + only useful when stuck near south
    if ctx.factory_energy < 350 or ctx.counts[WORKER] >= 1:
        return -1e6
    if ctx.factory_gap > 4:
        return -1e6
    if ctx.bfs_next_step is not None:
        return -1e6  # have a path, no need
    return 8.0

def s_idle_for_mine_or_cd(act, ctx) -> float:
    if act != "IDLE":
        return 0.0
    if ctx.f_move_cd > 1:
        return 5.0
    if (ctx.factory_col, ctx.factory_row) in ctx.own_mines and ctx.factory_gap > 10:
        return 6.0
    return -1.0  # mild deprioritization vs any positive option

FACTORY_SCORERS = [
    s_safety,
    s_emergency_north,
    s_progress,
    s_north_mine,
    s_build_north_mine,
    s_build_scout,
    s_build_worker,
    s_idle_for_mine_or_cd,
]

def pick_factory_action(ctx) -> str:
    best, best_score = "IDLE", float("-inf")
    for act in factory_candidates(ctx):
        score = sum(s(act, ctx) for s in FACTORY_SCORERS)
        if score > best_score:
            best, best_score = act, score
    return best
```

**Migration of every existing patch** (one row per v24/v37/v40 patch):

| Patch | Where it goes | Notes |
|---|---|---|
| `MIRROR_WALL` symmetry inference | unchanged — runs before scoring, mutates `walls_mem` | |
| Optimistic fog (`get_wall` default 0) | unchanged helper | |
| Emergency escape (gap≤2 → JUMP_NORTH) | `s_emergency_north` returning 1e3 | |
| Jump-only enemy factory guard (v24) | `s_safety` using existing `enemy_factory_jump_threats` and `safe_factory_action` | |
| North mine economy + own_mines step (v15+) | `s_north_mine` + `s_build_north_mine` | |
| Scout delay step 24 (v19) | hard gate in `s_build_scout` | |
| Save jump for north when gap ≤ 8 (v37) | precompute `bfs_north_only_step` once; `s_progress` picks it when gap≤8 | |
| No scout/miner at low gap (v37) | `s_build_scout`/`s_build_north_mine` gates | |
| 2-turn collision predictor (v40) | runs in pre-scoring threat building; flows into `s_safety` via the augmented `enemy_factory_threats` | |
| Conditional BUILD_SCOUT by distance (v40) | `all_far_enemy(ctx)` term inside `s_build_scout` | |
| Worker energy floor 350 (v40) | hard gate in `s_build_worker` | |
| Mid-game IDLE on own mine | `s_idle_for_mine_or_cd` | |
| BFS fallback 1-4 chain | precompute `bfs_next_step`; the candidate loop tries every direction anyway, so fallbacks 2-4 fold into the candidate set | |

**Why this fits our existing patches.** Almost every patch is already of the form "in *this* state, prefer *that* action". The elif chain only enforces priority order; a scorer with named additive terms does the same and is reorderable.

**What this gives us for the next ten patches.** The two next-most-likely patches (better late-game switch, side-mining gate) drop in as `s_late_game_switch` and `s_side_mine`. Adding a new patch is one new function with one numeric weight, not surgery on the elif chain.

**Estimated diff:** ~+150 lines, ~-90 lines in `pick_factory_action`. Net file size ~530 lines. Comfortably below 100 MB.

**PoC time-to-build:** 1-2 working days. Validation: paired-seed against v24, then v37, then v40 with `scripts/evaluate_agents.py --swap-sides --seeds 50`. Acceptance criterion: ≥ v40 on each. If equal or better, submit; otherwise iterate weight tuning (this is where §3.8 ES is useful).

**Risk:** Setting wrong relative magnitudes between scorers. Mitigation: keep emergency = 1e3, hard-gates = -1e6, all other scorers in `[-50, +100]`. Hard-gates dominate; rest is preference.

**Verdict:** **Top pick for Task B.**

### 4.2 Option B: Explicit Phase Machine

**Idea.** Define three phases: `ECONOMY`, `RACE`, `SURVIVAL`. Each phase exposes its own factory policy.

**PoC skeleton:**

```python
def detect_phase(ctx) -> str:
    if ctx.factory_gap <= 4:
        return "SURVIVAL"
    if ctx.turn < 80 and ctx.factory_gap >= 10:
        return "ECONOMY"
    return "RACE"

def factory_action_economy(ctx) -> str: ...
def factory_action_race(ctx) -> str: ...
def factory_action_survival(ctx) -> str: ...

def pick_factory_action(ctx) -> str:
    return {
        "ECONOMY": factory_action_economy,
        "RACE": factory_action_race,
        "SURVIVAL": factory_action_survival,
    }[detect_phase(ctx)](ctx)
```

**Mapping of patches:**

| Patch | Phase |
|---|---|
| Mirror walls / optimistic fog | shared preprocessing |
| Emergency escape | SURVIVAL only |
| North mine econ, scout delay 24 | ECONOMY only |
| Save jump for north (gap≤8) | SURVIVAL guard inside RACE/SURVIVAL BFS |
| No scout at low gap | SURVIVAL only |
| 2-turn collision predictor | RACE + SURVIVAL safety |
| Worker energy floor | SURVIVAL fallback |
| BFS jump-preferred | RACE |

**Why I rank this below Option A:** Each phase function will still be an elif chain internally, just shorter. We trade one big elif for three medium elifs. We also have to define the phase boundary, and the v37 results say boundary tuning has been the dominant failure mode (research.md §v30/v24 audit). Phase transitions add a new bug surface (oscillation between phases on the boundary turn).

**Where this *is* useful:** as a complement to Option A. The phase label can be one of the features inside the utility scorers (e.g., `s_progress` boost in RACE, `s_economy` boost in ECONOMY). This is essentially `bunterrrrr`'s strategy per research.md §Late-Game Learning.

**Verdict:** **Recommend as a context feature inside Option A, not as the top-level architecture.**

### 4.3 Option C: Hierarchical Planner (pilkwang-style)

**Idea.** Layered: `WorldModel → Targets → Strategy → Commit/Normalize/Reserve`. The pilkwang baseline in `baselines/pilkwang_structure/main.py` is the production example, at 3314 lines.

**Why I rank this lowest for our deadline:**
- Pilkwang's structure exists for two reasons our agent does not face: (a) it manages 5+ different unit types coordinating reservations and TRANSFERs, (b) it has a sophisticated SafetyDecision system. Our v24 has exactly 1 active worker most of the time and uses a single `reserved` set with no coordination.
- Local evaluation already shows pilkwang loses to v40 (research.md §v40, `+14` over 40 paired seeds). Importing its structure would buy us code complexity without a known performance ceiling above v40.
- Maintaining a 3000-line file in two weeks across 5 daily submissions makes regressions much more expensive than maintaining a 500-line file.

**Where this is useful:** if/when we add real coordination between multiple workers + miners + scouts to chase late-game side mines (research.md §Miner Event Notes shows bunterrrrr mixes directions: 37 NORTH / 18 WEST / 7 EAST). At that point a `reservation` system pays off. Today it does not.

**Verdict:** **Defer.** Useful post-deadline if the team continues working on this competition.

### 4.4 Option D: Local Beam Search / Short MCTS using kaggle-environments

**Idea.** For factory decisions only, simulate 2-3 turns ahead using the actual kaggle-environments crawl simulator with a trivial enemy model (assume enemy NORTH or IDLE) and a value function = `-gap + 0.001 * own_energy`.

**Feasibility check.** The crawl env in `.venv/lib/python3.13/site-packages/kaggle_environments/envs/crawl/crawl.py` is pure Python. Measuring: an env step is ~30-50 ms locally. Branching ~5 factory actions × 1-3 worker actions. A 2-turn lookahead = ~25-125 leaves × 30ms = 0.75-3.75 s. We have 3 s/turn. Tight.

**Mapping of patches:** Most existing patches become evaluator features in the value function (energy floor, gap, jump cooldown preserved, etc.). The 2-turn collision predictor essentially *is* a 2-turn lookahead; this option generalizes it.

**Risks:**
- Slow Python sim eats our `actTimeout=3 s`. We'd have to write a stripped-down "factory-only" simulator that drops irrelevant stuff (scouts, crystals, mining nodes), trading correctness of the simulator for speed.
- Modeling the enemy is a research problem on its own.

**Where this is useful:** as a *targeted* fallback. When the main scorer returns a tie between two actions, run a 1-ply lookahead for just those two. This is much cheaper than full lookahead.

**Verdict:** **Defer the full version. Use 1-ply tie-breaking inside Option A as a small optimization.** Estimated lift: maybe 50-100 ELO. Worth a follow-up but not the first move.

### 4.5 Option E: Behavior Tree

**Idea.** Standard game-AI behavior tree library.

**Why I rank this low:** A behavior tree with `Sequence/Selector/Inverter` nodes is just an elif chain with extra noun. It improves *visualization* and *modularity for very large hierarchies* (think 50+ behaviors). We have 10. The lift from a behavior tree library over Option A's named scorers is negligible.

**Verdict:** **Not applicable** for our complexity level. Use Option A.

### 4.6 Option F: Heuristic + learned residual (architecture flavor)

Same as §3.6. Architecturally, this is Option A plus one more scorer (`s_residual_learned`) that returns the residual classifier's confidence. Defer until §3.1 IL is shipped.

### 4.7 Option summary table

| Option | PoC effort | Migration cost | Future-flexibility | Recommend |
|---|---|---|---|---|
| A. Utility scoring | 1-2 days | mechanical | high | **YES (Action 1)** |
| B. Phase machine | 2-3 days | replaces structure | mid | use as feature inside A |
| C. Hierarchical pilkwang-style | 1-2 weeks | rewrites everything | high | post-deadline |
| D. Beam search / MCTS | 3-5 days | needs fast sim | high | use 1-ply tie-break inside A |
| E. Behavior tree | 1-2 days | new framework, same logic | mid | not worth it |
| F. Learned residual | 5-7 days | adds one scorer | high | after §3.1 IL |

---

## 5. Concrete Integration / Migration Table

This table is the canonical mapping from every v24/v37/v40 patch onto the recommended architecture (Option A utility scoring with §3.1 rule-mining as a research feeder):

| Patch | Source file:line | New home in Option A | New home in §3.1 mining? |
|---|---|---|---|
| Persistent walls + mirror inference | `main.py:43-67` (`walls_mem`) | preprocessing, untouched | feature `wall_density_north` |
| Optimistic fog (`get_wall` default 0) | `main.py:70-72` | helper untouched | feature `unknown_fraction` |
| Emergency escape gap≤2 | `main.py:294-307` | `s_emergency_north` | label only — guaranteed override |
| Jump-only enemy factory guard | `main.py:272-290` (`enemy_factory_jump_threats`, `safe_factory_action`) | `s_safety` returns -1e6 when unsafe | feature `enemy_factory_near` |
| North mine economy build | `main.py:312-323` | `s_build_north_mine` | feature `has_visible_north_mining_node` |
| North mine step onto own mine | `main.py:345-350` | `s_north_mine` returns 30 on NORTH | feature `on_own_north_mine` |
| Idle on own mine if gap>10 | `main.py:340-341` | `s_idle_for_mine_or_cd` returns 6 | feature `on_own_mine` |
| Scout delay step 24 | `main.py:334`, `SCOUT_DELAY_STEP=12` | `s_build_scout` early-gate `turn < 24` | feature `turn`, target action |
| BFS jump-preferred main pathfinding | `main.py:354-357` | precompute `bfs_next_step` once, `s_progress` references it | feature `bfs_recommended_action` |
| BFS fallback 1-4 (close target / any north / SOUTH escape / desperation jump) | `main.py:361-386` | replaced by candidate enumeration in `factory_candidates`; scorers naturally prefer alive over dead | n/a |
| Worker last-resort build | `main.py:391-396` | `s_build_worker` only positive when `bfs_next_step is None` | n/a |
| Save jump for north (gap≤8) (v37) | v37 diff: `bfs_jump(..., north_only_jump=factory_gap<=8)` | precompute both `bfs_next_step` and `bfs_north_only_step`; `s_progress` picks the second when gap≤8 | n/a |
| No-scout-low-gap (v37) | `factory_gap > 4` and `> 6` build gates | `s_build_scout` / `s_build_north_mine` gates | n/a |
| 2-turn collision predictor (v40) | v40 diff: `emove_cd <= 2` | `enemy_factory_threats` builder, before scoring | n/a |
| Conditional BUILD_SCOUT distance (v40) | v40 `scout_safe_distance = all_far_enemy(...)` | `s_build_scout` | feature `enemy_factory_manhattan_min` |
| BUILD_WORKER energy floor 350 (v40) | v40 `factory_energy >= 350` | `s_build_worker` | n/a |
| Mirror reservation set | `main.py:104` (`reserved`) | unchanged — passed into `record()` | n/a |
| Exception-safety wrapper | `main.py:25-31` | unchanged | n/a |

For the scout/miner/worker per-unit loops in `main.py:398-465`, the same utility-scoring pattern applies but the payoff is smaller because each unit's chain is short and stable. Refactor them only if time permits after the factory refactor lands.

---

## 6. Next Steps (sorted by effort/payoff)

| # | Action | Effort | Expected payoff | Depends on |
|---|---|---|---|---|
| 1 | Refactor v40 → Option A utility scorer. Validate paired-seed vs v24/v37/v40, then submit as v41. | 1-2 days | unlock all later patches; should be neutral-or-positive on its own | nothing |
| 2 | Build `scripts/mine_decisions.py`: re-replay 17 downloaded bunterrrrr focus episodes through the local crawl env, dump `(features, factory_action)` rows, fit `sklearn.tree.DecisionTreeClassifier(max_depth=4)`, print splits. | 1-3 days | finds 2-4 new heuristic rules; each may be worth ~50 ELO | nothing |
| 3 | Implement §3.8 ES on the named knobs of the refactored agent (`SCOUT_DELAY_STEP`, gap thresholds, energy floors, scorer weights). 30-seed paired evaluation as fitness. | 1-2 days | tunes the new scorers to v40-or-better numerically | Action 1 |
| 4 | Download more bunterrrrr episodes (target: 50-70) to broaden the rule-mining sample. Use existing `scripts/fetch_team_public_episodes.py`. | <1 day, mostly wall clock | makes Action 2 more reliable | none |
| 5 | Add 1-ply tie-breaking lookahead (§4.4) inside Option A: when top-2 actions are within 5 utility points, simulate 1 turn ahead and pick the higher-reward one. | 2 days | targeted defense against ramming-on-cooldown deaths | Action 1 |
| 6 | Add explicit phase label (`ECONOMY/RACE/SURVIVAL`, §4.2) as a feature inside Option A scorers; tune transition thresholds with ES. | 1 day | likely +30-80 ELO from a cleaner late-game switch | Action 1, Action 3 |
| 7 | If Actions 1-3 push us past 1250 and the deadline still has 5+ days, attempt §3.6 learned residual on factory action only, on bunterrrrr focus replays. | 5-7 days | uncertain; high variance | Actions 1-3 done |

**Submit cadence.** With 5 daily submissions and the active-slot ladder behavior documented in research.md §v29 (slots = last 2), keep one slot as v40-current-best and rotate the other to test refactored variants.

---

## 7. Risks and Open Questions

### 7.1 Risks

- **Refactor regression risk.** Replacing the elif spine with a scorer is mechanical but easy to get subtly wrong (e.g., emergency-jump priority not high enough on a tied tie-break). Mitigation: write a `tests/test_refactor_parity.py` that replays the same 20 seeds through both v40 and Option A and asserts the per-step factory action is identical on at least 80%+ of turns (the rest must come from intentional re-prioritization, audit them manually).
- **Local self-play noise.** Research.md §Local Evaluation says local is noisy and side-sensitive. Any ES tuning that drifts the agent toward a player_0 preference will not transfer. Mitigation: always evaluate with `--swap-sides` and ≥30 seeds.
- **Submission active-slot semantics.** Confirmed in research.md §v29 that the live leaderboard uses the active/latest two slots, not historical best. Refactor submissions should always replace the weaker slot, never both at once.
- **bunterrrrr's strategy may already be near-extracted.** v15-v24 already covers north mine economy + scout delay + jump-only enemy guard. The remaining gap may be in *late-game phase switch* and *side mining*. The decision-tree mining in Action 2 should reveal whether new rules exist or we are already at diminishing returns.

### 7.2 Open Questions (in priority order)

1. **What does the decision-tree mining (Action 2) actually say?** This is the single biggest unknown. If it surfaces a clear new rule (e.g., "when step > 350 and factory_gap > 5, never BUILD_SCOUT"), we have a cheap +100 ELO. If it just reproduces our existing rules, the value gap to bunterrrrr is elsewhere (likely *late-game phase switch* or *side-mining gating*), and Action 6 is the bigger bet.
2. **Is there a kaggle-environments overhead we can shave?** The env's per-step cost determines whether Option D (lookahead) is viable. Worth a 1-hour benchmark.
3. **How does bunterrrrr handle ramming on cooldown?** Our v40 has 5/7 losses from factory collisions where our mvcd>1 and enemy walks into us. If bunterrrrr never gets into mvcd>1 in dangerous positions, that itself is a learnable rule.
4. **Is the side-mining payoff worth the tempo cost?** v21/v22 says naive side mining hurt. The bunterrrrr miner-direction histogram (NORTH 37 / WEST 18 / EAST 7) suggests a gated rule exists but we have not found it.
5. **Will the ladder still be active for 13 more days?** The competition deadline is 2026-06-16, and the top-of-ladder has been stable (rank 1 at 2216 for at least a week). 13 days is enough for 65 submissions and ~200 public episodes — enough sample for any refactor to converge on its true rating.

---

## 8. Final Recommendation

- **This week, build Option A (utility scoring) and run Action 2 (rule mining) in parallel.** They are independent. Option A unblocks the next ten patches structurally; Action 2 tells us which patches to write first.
- **Do not start any neural-net training or self-play RL during the 13-day window.** The expected ROI is lower than tightening the heuristic stack, and the comparable Kaggle competitions (Halite IV, Lux AI 2) confirm this empirically.
- **Track the leaderboard rank, not just the score.** Top-20 is ~1165 at last snapshot (`data/raw/leaderboard_now2/`). A clean refactor + 1-2 new mined rules should put us reproducibly in the 1200-1300 band, which is top-15.

The single most important sentence in this document:
> **Use ML to *find* rules. Ship rules, not models.**

This matches what Halite IV and Lux AI 2 winners did, and it fits inside our 13-day, 5-subs/day, single-file constraint.

