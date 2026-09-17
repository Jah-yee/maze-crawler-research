# Maze Crawler Research Notes

Last updated: 2026-06-03.

## Current Status

- Kaggle CLI is installed in the local project virtualenv: `.venv/bin/kaggle`.
- Kaggle auth is configured via `~/.kaggle/access_token`; CLI was verified with `competitions list`.
- Competition files were downloaded to `data/input/`.
- Public notebooks and leaderboard snapshots were pulled into `external/`, `docs/`, and `data/raw/leaderboard/`.
- Root `main.py` is the current v1 baseline, copied from the strongest public package found: `nbridelancetb/top-2-maze-crawler-jump-preferred-bfs-lb-1223`.
- Local syntax and self-play validation pass.
- Online submission succeeded after updating `~/.kaggle/access_token` to the newly generated token.

## Competition Facts

- Competition: `maze-crawler`
- Deadline shown by CLI: 2026-06-16 23:59:00
- Category: Playground
- Reward: Knowledge
- Team count at snapshot: 331
- User has already joined the competition.
- Evaluation page says up to 5 agent submissions per day.
- The leaderboard score is a skill rating; episode win/loss/draw updates rating, and win margin does not affect rating.
- There is no private leaderboard in this simulation competition.
- Rules say prizes are not awarded for this competition. Treat "medal zone" as a leaderboard rank target, not guaranteed Kaggle medals/points.

## Game Summary

The core objective is factory survival in a north-scrolling symmetric maze. The most important practical lesson from public high-scoring work is that factory pathfinding speed dominates economy:

- Build at most one scout for vision.
- Avoid proactive workers/miners unless the factory is truly blocked.
- Prefer factory jumps when available because they cover two cells and avoid walls.
- Treat unknown fog optimistically so the factory keeps moving north.
- Mirror observed walls across the east/west symmetry axis to improve map knowledge.
- Use emergency escape logic when the factory is near the southern boundary.

One important local detail: the installed `kaggle-environments==1.30.1` reports these defaults:

- `scrollStartInterval=10`
- `scrollEndInterval=2`
- `scrollRampSteps=450`

The downloaded competition README still says `4/1/400`, so prefer the installed environment and Kaggle discussion updates over the static README when they conflict.

Discussion confirmations:

- Topic `701583` says the maze initial crawl speed was changed to `10`, maxes at `2`, at turn `450`.
- Topic `701737` says local environment mismatches should be fixed in `kaggle-environments` `1.29.3+`.
- Topic `702108` is the public LB1223 jump-preferred BFS writeup used for v1.
- Topic `701822` points to the daily episodes dataset: `kaggle/maze-crawler-episodes-index`.
- The episodes index manifest is saved at `data/episodes_index/manifest.csv`; full daily replay datasets are multi-GB, so only targeted samples should be downloaded.

## Leaderboard Snapshot

Downloaded public leaderboard snapshot: `data/raw/leaderboard/maze-crawler-publicleaderboard-2026-06-02T07:56:10.csv`

- Teams: 331
- Rank 1: 2213.4
- Rank 3: 1594.8
- Rank 10: 1208.7
- Rank 20: 1165.0
- Rank 30: 1078.9
- Rank 50: 1009.5
- Rank 100: 843.1

Practical target bands:

- First milestone: clear 1000.
- Strong public baseline target: 1200+.
- Serious medal-zone proxy: top 20, currently about 1165+.
- Leader contention requires much more than the public baseline: 1600+ to challenge top 3, 2200+ for first at this snapshot.

## Public Baselines Pulled

- `nbridelancetb/top-2-maze-crawler-jump-preferred-bfs-lb-1223`
  - Strategy: jump-preferred factory BFS, mirror wall memory, optimistic fog, one scout, emergency escape.
  - Extracted to `baselines/top2_jump_bfs/main.py`.
  - Selected as root `main.py` v1.

- `pilkwang/1000-maze-crawler-structure-baseline`
  - Strategy: large structured planner with world model, reservations, miner/mine logic, safety controller.
  - Extracted to `baselines/pilkwang_structure/main.py`.

- `lightningv08/worker-bfs-baseline-lb-1100-maze-crawler`
  - Strategy: conservative worker and BFS wall opener.
  - Extracted to `baselines/worker_bfs/main.py`.

- `lakhindarpal/1100-lb-maze-crawler`
  - Strategy: convoy-style jump/BFS baseline.
  - Extracted to `baselines/lakhindar_1100/main.py`.

## Local Evaluation

Local evaluation is noisy and not equivalent to Kaggle's ladder. Use it mainly for crash checks and paired comparisons.

20 seeds vs `random`:

- `pilkwang_structure`: 20-0-0, avg reward 754.8 / -252.8
- `lakhindar_1100`: 18-0-2, avg reward 762.7 / -244.5
- `top2_jump_bfs`: 19-0-1, avg reward 529.6 / -217.6
- `worker_bfs`: 20-0-0, avg reward 412.4 / -238.1
- starter `data/input/main.py`: 0-0-20, avg reward 0.5 / 0.5

10 paired seeds with side swaps vs `top2_jump_bfs`:

- top2 vs `worker_bfs`: 13-7-0, avg top2 reward 193.4
- top2 vs `lakhindar_1100`: 17-1-2, avg top2 reward 106.4
- top2 vs `pilkwang_structure`: 11-8-1, avg top2 reward 155.4

Conclusion: `top2_jump_bfs` is the best v1 candidate despite some side sensitivity. `pilkwang_structure` is worth mining for safety/reservation ideas but is not a clear drop-in replacement.

## Online Submission

- Submission ID: `53283498`
- File: `main.py`
- Message: `v1 public top2 jump bfs baseline`
- Status: `COMPLETE`
- Initial public score after first checks: `736.5`
- Latest refreshed leaderboard rank after two public episodes: rank `87` of `333`, score `861.3`
- Later submission score after 30 public episodes: `997.3`
- Replay summary over 30 public episodes: `20-9-1`, saved at `reports/replay_summary.csv`
- Failure classification over those 30 public episodes, saved at `reports/replay_failure_analysis.csv`:
  - Losses: 6 factory-collision tiebreak losses, 2 timeout tiebreak losses, 1 boundary-scroll loss.
  - Draws: 1 factory-collision draw.
  - Wins: many are also factory-collision tiebreak wins, so avoiding every collision is too blunt.
- First public episode: `78489628`
  - Opponent: `MhalTeddy`
  - Our side: agent index 1
  - Result: win, final rewards `-104 / 634`
  - Replay: `reports/replays/episode-78489628-replay.json`
- Second public episode: `78489980`
  - Opponent: `Santiago Maniches`
  - Our side: agent index 1
  - Result: win, final rewards `-36 / 580`
  - Replay: `reports/replays/episode-78489980-replay.json`
- Experimental v2 submission:
  - Submission ID: `53290722`
  - File: `experiments/v6_enemy_factory_avoid/main.py`
  - Message: `v2 visible enemy factory collision avoidance`
  - Status: `COMPLETE`
  - Public score has been volatile, last checked at `895.1` after 6 public episodes.
  - Public replay summary: `5-1-0`, saved at `reports/replay_summary_v2.csv`.
  - Failure classification: no factory-collision losses; the single public loss was boundary scroll at episode `78510303`.
  - Interpretation: broad visible enemy-factory avoidance appears to solve the collision class, but can still lose tempo or simply fail in trapped boundary situations.

- Experimental v3 submission:
  - Submission ID: `53291864`
  - File: `experiments/v9_collision_avoid_gap_guard/main.py`
  - Message: `v3 conditional collision avoid gap guard`
  - Status: `COMPLETE`
  - Best checked public score: `1016.1`.
  - Public replay summary at 3 episodes: `3-0-0`, saved at `reports/replay_summary_v3.csv`.
  - Idea: conditional collision avoidance like v7, but disabled when the factory is within 3 rows of the south bound so escape keeps priority.

- Experimental v4 submission:
  - Submission ID: `53292191`
  - File: `experiments/v10_enemy_factory_avoid_gap_guard/main.py`
  - Message: `v4 visible enemy factory avoid gap guard`
  - Status: `COMPLETE`
  - Public score after first public draw: `897.3`.
  - Public replay summary at 1 episode: `0-0-1`, saved at `reports/replay_summary_v4.csv`.
  - Idea: v6 broad visible enemy-factory threat avoidance, but disabled when the factory is within 3 rows of the south bound.

- Restored v1 submission:
  - Submission ID: `53292419`
  - File: `main.py`
  - Message: `v5 restore v1 top2 baseline active`
  - Status: `COMPLETE`
  - Public score last checked: `907.5`.
  - Public replay summary at 5 episodes: `4-1-0`, saved at `reports/replay_summary_v5.csv`.
  - The single public loss is a factory-collision tiebreak loss, exactly the main v1 failure class.

- Revived v3 submission:
  - Submission ID: `53293112`
  - File: `experiments/v9_collision_avoid_gap_guard/main.py`
  - Message: `v6 revive v3 collision guard active`
  - Status: `COMPLETE`
  - Public score last checked: `716.4`.
  - Public replay summary at 6 episodes: `4-2-0`, saved at `reports/replay_summary_v6.csv`.
  - Both public losses were boundary-scroll losses, not factory-collision losses. One was a 0-energy forced-idle failure at turn 451.
  - Purpose: make the latest active candidate the best observed online variant (`v9` / submission `53291864`) instead of leaving the weak v4 as one of the latest submissions.

- Late scout reserve submission:
  - Submission ID: `53294055`
  - File: `experiments/v11_late_scout_reserve/main.py`
  - Message: `v7 late scout energy reserve`
  - Status: `COMPLETE`
  - Public score after validation plus one public win: `681.1`.
  - Public replay summary at 1 episode: `1-0-0`, saved at `reports/replay_summary_v7.csv`.
  - Full leaderboard snapshot after this submission: rank `59` of `336`, score `959.1`, saved at `data/raw/leaderboard_check_v11/`.
  - Current top-50 line is about `1004.3`; top-20 line is about `1161.7`.

## Commands

Verify CLI:

```bash
.venv/bin/kaggle competitions list --search maze-crawler
```

Run local validation:

```bash
.venv/bin/python -m py_compile main.py
.venv/bin/python scripts/evaluate_agents.py \
  --agents main.py \
  --opponent random \
  --seeds 5 \
  --out reports/smoke.csv
```

Submit current `main.py`:

```bash
.venv/bin/kaggle competitions submit maze-crawler \
  -f main.py \
  -m "v1 public top2 jump bfs baseline"
```

Check submissions:

```bash
.venv/bin/kaggle competitions submissions maze-crawler
```

## Experiment Log

- `experiments/v2_reciprocal/main.py`
  - Added positive reciprocal wall propagation and a late-game adaptive danger gap.
  - 20 paired seeds looked neutral: v2 18 wins, v1 17 wins, 5 draws.
  - 50 paired seeds rejected it: v1 45 wins, v2 33 wins, 22 draws.
  - Decision: keep as an experiment, do not promote to root `main.py`.

- `experiments/v3_weighted_factory/main.py`
  - Replaced factory jump BFS with a weighted best-first search that rewards net north movement and penalizes SOUTH detours.
  - 30 paired seeds were slightly negative: v1 26 wins, v3 23 wins, 11 draws.
  - Decision: keep as an experiment, do not promote to root `main.py`.

- `experiments/v4_one_scout/main.py`
  - Changed scout policy to build at most one scout per episode, based on online replay evidence that v1 rebuilds scouts many times and loses some long games on energy tiebreaks.
  - 60 paired seeds rejected it: v1 75 wins, v4 19 wins, 26 draws.
  - Decision: too little vision; keep as an experiment, do not promote.

- `experiments/v5_max5_scouts/main.py`
  - Capped scout rebuilds at five per episode as a softer version of v4.
  - 60 paired seeds rejected it: v1 56 wins, v5 44 wins, 20 draws.
  - Decision: still worse than uncapped scout rebuilding; do not promote.

- `experiments/v6_enemy_factory_avoid/main.py`
  - Added visible enemy-factory threat avoidance to reduce factory collision losses found in online replays.
  - 60 paired seeds were neutral: v1 44 wins, v6 44 wins, 32 draws.
  - Decision: not enough to replace v1 locally, but worth a Kaggle exploratory submission while v1 remains one of the latest two submissions.

- `experiments/v7_conditional_collision_avoid/main.py`
  - Avoided visible enemy-factory collision only when visible support-unit tiebreak looked unfavorable.
  - 60 paired seeds were slightly negative: v1 48 wins, v7 45 wins, 27 draws.
  - Decision: use as the base for a guarded variant rather than submit directly.

- `experiments/v8_own_unit_safe_factory/main.py`
  - Tried to stop the factory from moving into stuck friendly support units outside emergency.
  - 60 paired seeds rejected it: v1 52 wins, v8 41 wins, 27 draws.
  - Decision: do not submit; friendly-unit preservation cost too much tempo.

- `experiments/v9_collision_avoid_gap_guard/main.py`
  - Added a south-boundary gap guard to v7 conditional enemy-factory collision avoidance.
  - 60 paired seeds vs v1 were positive: v9 48 wins, v1 43 wins, 29 draws.
  - 30 paired seeds vs `pilkwang_structure` were still positive but weaker than v6: v9 33 wins, Pilkwang 27 wins.
  - Decision: submitted as v3 for online validation because it is the first variant with positive v1 paired-seed signal while targeting the dominant online loss class.

- `experiments/v10_enemy_factory_avoid_gap_guard/main.py`
  - Added the same south-boundary gap guard to v6 broad visible enemy-factory avoidance.
  - 60 paired seeds vs v1 were slightly positive: v10 45 wins, v1 43 wins, 32 draws.
  - 30 paired seeds vs `pilkwang_structure` were strongly positive: v10 42 wins, Pilkwang 18 wins.
  - Decision: submitted as v4 because it keeps most of v6's anti-Pilkwang strength while improving v6's v1 self-play signal.

- `experiments/v11_late_scout_reserve/main.py`
  - Built on v9 and raised the minimum factory energy required to rebuild scouts late:
    50 before step 300, 150 after step 300, 250 after step 400.
  - Motivation: online v6 losses show boundary-scroll failures caused by low or zero factory energy, while v1/v5 still spends 50 energy rebuilding scouts late.
  - 50 paired seeds vs v1 were strongly positive: v11 43 wins, v1 27 wins, 30 draws.
  - 50 paired seeds vs v9 were positive: v11 38 wins, v9 32 wins, 30 draws.
  - 30 paired seeds vs `pilkwang_structure` were positive: v11 35 wins, Pilkwang 23 wins, 2 draws.
  - Decision: top candidate for the next submission window; online v6 `4-2-0` has only boundary-scroll losses, matching v11's target.

## Bunterrrrr Leader Study

- Current rank 1 snapshot:
  - Team: `bunterrrrr`
  - TeamId: `16001129`
  - Current public submission: `53084625`
  - Previous public submission: `52950479`
  - Snapshot score: about `2216.1`
- `scripts/fetch_team_public_episodes.py` uses Kaggle's internal public-team-submissions endpoint to fetch exposed submission IDs and episode lists. It wrote:
  - `reports/bunterrrrr_public_submissions.csv`
  - `reports/bunterrrrr_episodes.csv`
- Current submission `53084625` public sample in the fetched episode list:
  - 167 public episodes
  - 161 wins, 4 losses, 2 draws
  - Strong-team outcomes include wins/draws/losses against Takahiro Matsumoto, ZERO HQR, harmo-miu, CurveCowboy, AI TOOK MY JOB AND YOUR JOB!, Nicolas Bridelance, Kalyan, and Mathieu W.
- Focus replays:
  - `reports/bunterrrrr_focus_episodes.csv` selected 60 high-signal episodes: losses/draws, strong opponents, recent episodes, and top reward games.
  - `reports/replays_bunterrrrr_focus/` currently contains a downloaded subset.
  - `reports/bunterrrrr_focus_strategy_metrics.csv` extracts economy/action metrics.
- Main strategic finding:
  - Bunterrrrr is not a pure scout + factory BFS agent.
  - It often builds no scouts at all.
  - It opportunistically builds miners directly onto visible adjacent mining nodes with directional actions such as `BUILD_MINER_NORTH`.
  - The miner then `TRANSFORM`s, and the factory steps onto the new mine to collect the miner's remaining energy and then 50 energy per turn.
  - In high-reward wins, factory energy reaches `6000-10000`, while v1/v3 usually decline from `1000` to a few hundred.
  - It also uses workers late for wall removal/energy support, but the first large gap is the mine economy.
- Metrics over the first 17 downloaded focus replays:
  - Bunterrrrr: `16-1-0`, mean reward `3726.8`, median reward `2738`, max reward `9684`.
  - Mean final factory energy `5645.6`; median final factory energy `6874`.
  - Mean build miners `3.8`; first miner build median step `31`.
  - Mean build scouts `0.0`.
  - v1 comparison over 30 public replays: mean reward `85.6`, median reward `1`, mean final factory energy `351.6`, mean build scouts `6.1`, no miners/mines.
- `experiments/v14_adjacent_mine_econ/main.py`
  - Built on v9 and added adjacent mining-node economy in any direction, miner transform logic, directional build reservation, and simple mine collection.
  - Local signal:
    - vs v1 over 60 paired seeds: v14 34 wins, v1 57 wins, 29 draws, but v14 average reward much higher.
    - vs v9 over 50 paired seeds: v14 40 wins, v9 47 wins, 13 draws.
    - vs Pilkwang over 30 paired seeds: v14 37 wins, Pilkwang 26 wins, 2 draws.
  - Interpretation: side/south mining is too greedy and can cost tempo even though it proves the economy mechanism works.
- `experiments/v15_north_mine_econ/main.py`
  - Restricts v14's proactive miner builds and mine collection to northward mining nodes only.
  - Keeps the factory's northward tempo closer to the public baseline while preserving the bunterrrrr-style energy engine.
  - Local signal:
    - vs v1 over 60 paired seeds: v15 54 wins, v1 42 wins, 24 draws.
    - vs v9 over 50 paired seeds: v15 44 wins, v9 42 wins, 14 draws.
    - vs Pilkwang over 30 paired seeds: v15 38 wins, Pilkwang 20 wins, 2 draws.
  - Submitted as `v9 north mine economy from bunterrrrr study`; submission status still needs a successful Kaggle query because the API began returning SSL EOF during follow-up status checks.
- `experiments/v16_no_scout_north_mine/main.py`
  - Disabled routine scout builds entirely to test the "bunterrrrr often builds no scouts" hypothesis.
  - Local signal was rejected despite high average rewards from occasional mine jackpots:
    - vs v1 over 60 paired seeds: v16 23 wins, v1 79 wins, 18 draws.
    - vs v9 over 50 paired seeds: v16 16 wins, v9 64 wins, 20 draws.
    - vs Pilkwang over 30 paired seeds: v16 32 wins, Pilkwang 24 wins, 4 draws.
  - Interpretation: no-scout navigation loses too many races; keep only as evidence that some early scout delay may help.
- `experiments/v17_delay_scout_north_mine/main.py`
  - Delays the first routine scout until step 32, preserving an early no-scout mine window while restoring later vision.
  - Local signal:
    - vs v1 over 60 paired seeds: v17 61 wins, v1 41 wins, 18 draws.
    - vs v9 over 50 paired seeds: v17 39 wins, v9 44 wins, 17 draws.
    - vs Pilkwang over 30 paired seeds: v17 40 wins, Pilkwang 18 wins, 2 draws.
  - Interpretation: strong vs public-style baselines, but too weak vs the internal v9 guard.
- `experiments/v18_delay20_scout_north_mine/main.py`
  - Shorter first-scout delay at step 20.
  - Smoke signal:
    - vs v1 over 30 paired seeds: v18 29 wins, v1 25 wins, 6 draws.
    - vs v9 over 25 paired seeds: v18 26 wins, v9 20 wins, 4 draws.
    - vs Pilkwang over 20 paired seeds: v18 21 wins, Pilkwang 19 wins.
  - Interpretation: improves v9 stability relative to v17, but loses too much Pilkwang/economy strength.
- `experiments/v19_delay24_scout_north_mine/main.py`
  - Middle point: first routine scout delayed until step 24.
  - Diff from v15 is intentionally small: add `SCOUT_DELAY_STEP = 24`, reset memory on `obs.step == 0`, and gate `BUILD_SCOUT` until the delay has passed.
  - Full local signal:
    - vs v1 over 60 paired seeds: v19 62 wins, v1 39 wins, 19 draws.
    - vs v9 over 50 paired seeds: v19 55 wins, v9 33 wins, 12 draws.
    - vs Pilkwang over 30 paired seeds: v19 42 wins, Pilkwang 18 wins.
  - Submitted as `v19 delay24 scout north mine economy`; submission ref `53298536`.
  - Initial online evidence:
    - Submissions table after two public games: publicScore `809.1`.
    - Validation `78528209`: win, self-play, reward `1/-1`, final factory energy `6673`, first scout step `25`, first miner step `95`, max mines `2`.
    - Public `78528807`: win vs Lakhindar Pal, reward `781/-205`, no miner triggered.
    - Public `78529042`: win vs Michael Gough, reward `3314/-101`, first miner step `159`, max factory energy `3448`.
    - Failure analysis over downloaded replays: `3-0-0`, all `active_or_win`.
  - Interpretation: the package is not broken online, but the current public score is based on too few games and still trails v15/v7. Miner timing remains much later than bunterrrrr's median first miner step around `31`.
- `experiments/v20_delay28_scout_north_mine/main.py`
  - Longer first-scout delay at step 28.
  - Smoke signal:
    - vs v1 over 30 paired seeds: v20 23 wins, v1 24 wins, 13 draws.
    - vs v9 over 25 paired seeds: v20 22 wins, v9 20 wins, 8 draws.
    - vs Pilkwang over 20 paired seeds: v20 28 wins, Pilkwang 12 wins.
  - Interpretation: good economy vs Pilkwang, but too weak vs v1/top2; v19 is the better submission candidate.
- `experiments/v21_idle_side_mine_econ/main.py`
  - Built on v19. Allows side (`EAST`/`WEST`) miner builds only when the factory already has movement cooldown, high energy, and a large south-bound gap. Side mine collection is also gated by a larger gap.
  - Smoke signal:
    - vs v19 over 25 paired seeds: v21 28 wins, v19 17 wins, 5 draws.
    - vs v9 over 25 paired seeds: v21 21 wins, v9 22 wins, 7 draws.
    - vs Pilkwang over 20 paired seeds: v21 22 wins, Pilkwang 17 wins, 1 draw.
  - Interpretation: idle-turn side mining can beat v19 directly, but the current side-collection gate damages the older stable baselines. Do not submit; tighten side collection before retrying.
- `experiments/v22_conservative_side_collect/main.py`
  - Built on v21. Keeps idle-turn side miner construction, but only side-collects when the factory has a larger gap and energy below `900`.
  - Smoke signal:
    - vs v19 over 25 paired seeds: v22 21 wins, v19 22 wins, 7 draws.
    - vs v9 over 25 paired seeds: v22 23 wins, v9 18 wins, 9 draws.
    - vs Pilkwang over 20 paired seeds: v22 28 wins, Pilkwang 11 wins, 1 draw.
  - Interpretation: side mining remains useful against Pilkwang and can produce high rewards, but v22 no longer beats v19 directly and still does not match v19's v9 stability. Do not submit.
- `experiments/v23_near_enemy_factory_avoid/main.py`
  - Built on v19 after online v19 loss `78529554` vs Mathieu W: our visible factory jumped east into a cell the enemy factory could move west into.
  - Added broad near visible enemy-factory threat avoidance.
  - Exact replay regression: changes the losing step-159 factory action from `JUMP_EAST` to `IDLE`.
  - Smoke signal:
    - vs v19 over 25 paired seeds: v23 17 wins, v19 21 wins, 12 draws.
    - vs v9 over 25 paired seeds: v23 11 wins, v9 31 wins, 8 draws.
    - vs v1 over 30 paired seeds: v23 28 wins, v1 17 wins, 15 draws.
    - vs Pilkwang over 20 paired seeds: v23 30 wins, Pilkwang 10 wins.
  - Interpretation: fixes the replay but is too conservative against the stable v9 guard. Do not submit.
- `experiments/v24_jump_enemy_factory_avoid/main.py`
  - Narrower v23: only adds an extra guard for factory `JUMP_*` landing cells that a nearby visible enemy factory occupies or can move into; normal movement keeps v19's original conditional tiebreak guard.
  - Exact replay regression: also changes the losing v19 step-159 factory action from `JUMP_EAST` to `IDLE`.
  - Smoke signal:
    - vs v19 over 25 paired seeds: v24 19 wins, v19 21 wins, 10 draws.
    - vs v9 over 25 paired seeds: v24 30 wins, v9 17 wins, 3 draws.
    - vs v1 over 30 paired seeds: v24 30 wins, v1 18 wins, 12 draws.
    - vs Pilkwang over 20 paired seeds: v24 25 wins, Pilkwang 15 wins.
  - Interpretation: slight local regression vs v19 head-to-head, but it fixes a concrete online factory-collision loss while staying positive against v9/v1/Pilkwang. Candidate for an online repair submission.
  - Submitted as `v24 jump-only enemy factory guard`; submission ref `53299372`.
  - Initial online evidence after three public games:
    - Submissions table publicScore `1039.7`.
    - Validation `78530398`: win by factory-collision tiebreak, reward `1/-1`.
    - Public `78530966`: win vs Alexander Smetannikov, reward `3405/-92`, first miner step `6`.
    - Public `78531329`: win vs Kirito_arkerman, reward `3869/-38`, first miner step `41`.
    - Public `78531555`: win vs Or4k2!, reward `1/-1`, first miner step `47`.
    - Downloaded replay sample is `4-0-0`; no public loss yet.
  - Later online evidence:
    - Submissions table settled at publicScore `1188.9`; leaderboard rank `12/338` at the `2026-06-02T18:10:43` public leaderboard download.
    - Downloaded sample: `8-1-1` over validation + public replays: 4 active wins, 4 factory-collision wins, 1 factory-collision draw, 1 factory-collision loss.
    - The visible loss `78532503` was not a jump-landing bug: our factory was in move cooldown and the opponent moved into us. A simple safe-action filter cannot repair that turn.
    - Current best online submission as of the latest check.
- `experiments/v26_lateral_jump_guard/main.py`
  - Built on v15, not v24. Adds only a lateral factory jump guard for `JUMP_EAST`, `JUMP_WEST`, and `JUMP_SOUTH`.
  - Exact replay checks:
    - v15 draw `78529045`: step 91 changes from `JUMP_EAST` to `IDLE`.
    - v19 loss `78529554`: step 159 changes from `JUMP_EAST` to `IDLE`.
    - v15 normal movement collision `78530159`: step 128 remains `NORTH`.
  - Local signal:
    - vs v15 over 25 paired seeds: v26 24 wins, v15 21 wins, 5 draws.
    - vs v9 over 25 paired seeds: 20 wins each, 10 draws.
    - vs top2 over 30 paired seeds: v26 26 wins, top2 25 wins, 9 draws.
    - vs Pilkwang over 20 paired seeds: v26 33 wins, Pilkwang 7 wins.
  - Submitted as `v26 lateral factory jump guard on v15`; submission ref `53300160`.
  - Online signal was poor (`723.9` after latest check), so this is not a candidate despite the clean replay fix.
- `experiments/v27_contact_guard/main.py`
  - Built on v24. Adds a cautious ordinary-move guard that avoids stepping adjacent to a much stronger visible enemy factory when support is not better.
  - Replay action scan over v24 player-0 samples changed only three factory actions in one replay, but that replay was a v24 collision win.
  - Local signal:
    - vs v24 over 25 paired seeds: v27 20 wins, v24 22 wins, 8 draws.
    - vs v9 over 25 paired seeds: v27 23 wins, v9 22 wins, 5 draws.
    - vs top2 over 30 paired seeds: 26 wins each, 8 draws.
    - vs Pilkwang over 20 paired seeds: v27 29 wins, Pilkwang 11 wins.
  - Interpretation: not enough; do not submit.
- `main.py` / v28
  - Root `main.py` was restored to match `experiments/v24_jump_enemy_factory_avoid/main.py`.
  - Submitted as `v28 rerun v24 current best sampling`; submission ref `53300377`.
  - Purpose is online sampling with the current best code, not a new logic change.
  - Online sample after monitoring: 3 public wins, all active wins, but only small rewards (`411/-174`, `404/-142`, `1/-1`), so publicScore stayed around `967.3-985.2` rather than reproducing v24's high-score sample.
- `main.py` / v29
  - Same v24 code, submitted as `v29 rerun v24 active slot restore`; submission ref `53300743`.
  - The competition leaderboard appears to use the active/latest two submissions rather than historical best. After v26/v28, the visible leaderboard no longer used v24's `1236.5`.
  - Current observed state after final check:
    - v29: `600.0`, validation only.
    - v28: `967.3`, three public wins but low rewards.
    - Historical v24 submission `53299372`: still shows `1236.5` in the submissions table.
    - Downloaded leaderboard `2026-06-02T18:36:51`: Jiayi rank `61/338`, score `967.3`.
  - Do not submit experimental code until the active-slot behavior is understood or both active slots are restored to strong v24-like samples.
- `scripts/kaggle_batch_ops.py`
  - Hardened the workflow helpers so empty episode/replay results no longer leave stale CSV state or crash the script.
  - `episodes` now removes stale output before writing and returns cleanly when Kaggle has not generated episodes yet.
  - `download-replays` now returns cleanly when the episodes CSV does not exist.
  - `summarize` now returns cleanly when the replay directory is empty.
- `main.py` / v30
  - Same v24 code, submitted as `v30 stable v24 mainline deployment`; submission ref `53300964`.
  - Chosen as the stable mainline online candidate.
- `main.py` / v31
  - Same v19 code, submitted as `v31 alternative v19 delay24 scout deployment`; submission ref `53300978`.
  - Chosen as the second promising candidate: weaker than v24 historically, but still one of the strongest alternate lines and different enough to serve as the exploratory slot without dropping to a clearly bad experiment.
  - Immediate status after submission check:
    - `v30` had one validation episode only.
    - `v31` had one validation episode only.
    - Public leaderboard snapshot `2026-06-02T18:44:07` showed rank `197/338`, score `600.0`, which reflects the latest active submissions still waiting for public episodes.
  - Later online evidence:
    - `v30` climbed to `1123.0`.
    - `v31` climbed to `985.4`.
    - Public leaderboard snapshot `2026-06-03T05:25:35` showed Jiayi rank `26/341`, score `1123.0`.
    - This confirms the active slots were successfully restored to strong agents, with `v30` clearly the better live slot.

- `experiments/v32_late_scroll_collision_fix/main.py`
  - Built on v24. Two narrow ideas only:
    - enter late-game northward survival mode earlier to reduce `boundary_scroll`;
    - avoid some late adjacent-factory deaths by escaping only when `IDLE` is already unsafe.
  - Replay-level improvements:
    - `78542117` no longer spends a late-game turn on `BUILD_SCOUT`.
    - `78564151` no longer idles on the final adjacent-factory death turn.
  - Local signal:
    - first pass vs v24 over 25 paired seeds: worse than v24.
    - narrowed pass vs v24 over 20 paired seeds: still worse than v24.
    - vs v9 over 25 paired seeds: positive.
    - vs top2 over 25 paired seeds: slightly positive.
  - Interpretation: the failure diagnosis is probably right, but the current fix is not yet production-safe. Do not submit.

## Late-Game Learning From bunterrrrr

- The remaining gap to `bunterrrrr` is not just "more side miners"; it is also a stronger late-game mode switch.
- Focus replays show many late miner builds at factory gap `<= 10`, often with very high stored factory energy, but when the south bound gets close the factory action stream becomes much more north-forcing.
- Several late `bunterrrrr` samples show repeated `NORTH` progress while preserving the economy shell, rather than mixing in extra scout-like tempo loss.
- The comprehensive pattern is:
  - early and mid game are still economy-positive, often with no scout at all;
  - miner directions are mixed, not north-only (`NORTH 37`, `WEST 18`, `EAST 7`, `SOUTH 2` in the focus sample);
  - once scroll pressure becomes real, the policy flips into a much harder north conveyor and gives up lower-value support actions.
- Practical takeaway:
  - the next strong improvement is likely a dedicated late-game north conveyor / survival mode, not another broad contact guard.

## Current Best Versions

- Last checked via Kaggle submissions on 2026-06-03 06:16 UTC+8:
  - `v30 stable v24 mainline deployment`: `1133.4`
  - `v31 alternative v19 delay24 scout deployment`: `985.4`
- Latest downloaded public leaderboard snapshot is `data/raw/leaderboard_now2/maze-crawler-publicleaderboard-2026-06-03T06:16:05.csv`.
  - Snapshot result: `Jiayi Du` rank `25 / 342`, score `1133.4`.
  - Top-20 boundary score: `1155.6`. Top-15: `1181.4`. Top-10: `1339.0`.
- `main.py` is intentionally kept equal to `experiments/v24_jump_enemy_factory_avoid/main.py` because that line remains the strongest production-safe agent in this workspace.
- 2026-06-03 ~16:53 UTC+8 active slots (after v40 refloor):
  - `v37 save jump for north plus no scout at low gap`: `53317242`, `publicScore 1142.4`.
  - `v38 v24 mainline safety slot to keep strong baseline active`: `53318414`, `publicScore 1007.5`.
  - `v40 2-turn collision predictor plus conditional scout`: `53320605`, `publicScore 968.2` (kept as data; below the 1100 refloor threshold).
  - `v41 v24 mainline refloor`: `53321085`, pending — submitted because v40 stayed under 1100 after ~5 episodes across the two v40 slots.

## v33 Targeted Late Patch

- `experiments/v33_targeted_late_patch/main.py`
  - Built from `v24` with only two narrow changes:
    - enter late scroll mode later and block late `BUILD_SCOUT` / late miner greed near the boundary;
    - reuse the `v32` adjacent-enemy-factory escape only when `IDLE` is already unsafe.
  - Local result:
    - vs `v24` over 20 paired seeds: `v33` 11 wins, `v24` 22 wins, 7 draws.
    - vs `v19` over 20 paired seeds: slightly negative.
    - vs `top2` over 20 paired seeds: slightly positive.
  - Interpretation:
    - the diagnosis around `boundary_scroll` and `late-game factory_collision` is probably correct;
    - even this narrower patch still gives back too much core strength against `v24`;
    - keep `v33` as a research branch, do not promote or submit.

## Miner Event Notes

- `scripts/analyze_miner_events.py` extracts detailed `BUILD_MINER_*` contexts from replays.
- Bunterrrrr focus sample:
  - 64 `BUILD_MINER_*` actions across 17 downloaded focus replays.
  - Direction distribution: `NORTH 37`, `WEST 18`, `EAST 7`, `SOUTH 2`.
  - This confirms bunterrrrr is not north-only; side mining is important, but prior v21/v22 show naive side collection can hurt stable racing.
- Jiayi v19/v24 online samples:
  - v19 miner events are all `BUILD_MINER_NORTH`; first miner examples include steps `68`, `95`, `159`.
  - v24 online sample is also north-only, but got much earlier visible north mining opportunities: steps `6`, `41`, `47`.
  - Next useful economy work is not just more scout delay; it should selectively exploit side mining without dragging the factory off tempo.

## v30 / v24 Replay Failure Audit (2026-06-03)

- Refreshed `reports/replay_summary_v30.csv` and `reports/replay_failures_v30.csv` over 34 v30 episodes.
- Result split: `20-14-0` (record); cause split for losses:
  - `boundary_scroll`: 6
  - `factory_collision`: 4
  - `timeout_tiebreak`: 3
  - `single_factory_death`: 1
- v31 (v19 code) shows a similar shape (`18-14-1`) but more `factory_collision` losses (6).
- Two concrete bugs surfaced from inspecting `78569976` step-by-step:
  - Step 481, gap=4, jump ready: BFS expanded `JUMP_WEST` because it reaches the row-20 goal in fewer steps. The jump cooldown locked at 20 turns and ran the factory out of escape options when scroll caught up at step 499.
  - Step 492, gap=2, move on cooldown: the elif chain still preferred `BUILD_SCOUT` over `IDLE`, so a near-death turn was spent on a 50-energy scout instead of staging an escape.
- Energy=0 deaths (`78544366`, `78560758`) are a downstream consequence of those builds plus per-turn passive drain: `factoryEnergy=1000`, `energyPerTurn=1`, scout 50 + miner 300 + worker 200 spawn drains another 200 each. By turn ~470 the factory hits zero and the next JUMP becomes a forced IDLE.

## v36 Save Jumps for North (rejected)

- `experiments/v36_save_jump_for_north/main.py`
  - Restricts `bfs_jump` to `JUMP_NORTH` whenever `south >= 60 and factory_gap > 2`.
  - Local signal vs `v24` over 50 paired seeds: `v36` 16, `v24` 22, draws 12.
  - Interpretation: blocking lateral jumps too broadly slows down mid-game travel and gives back self-play. Do not promote.

## v37 Late Save-Jump + No-Scout-Low-Gap (active)

- `experiments/v37_late_save_jump_no_scout/main.py`
  - Two narrow changes vs `v24`:
    - `bfs_jump(north_only_jump=True)` only when `factory_gap <= 8`.
    - `BUILD_SCOUT` and `BUILD_MINER` gated by `factory_gap > 4` (and `> 6` for miner).
  - Local signal:
    - vs `v24` over 100 paired seeds: `v37` 44, `v24` 36, draws 20.
    - vs `v19` over 50 paired seeds: `v37` 17, `v19` 19, draws 14.
    - vs `top2` over 50 paired seeds: `v37` 30, `top2` 14, draws 6.
    - vs `pilkwang_structure` over 40 paired seeds: `v37` 29, `pilkwang` 10, draws 1.
  - Interpretation: roughly even vs the strongest current line, clearly stronger vs the v1/pilkwang style of opponent that is common on the live ladder.
  - Submitted as `v37 save jump for north plus no scout at low gap`; submission ref `53317242`.
  - Online sample after first 8 public episodes: `5-3-0`, `publicScore 1007.7`. Two of the losses are early `factory_collision` where our factory was on `mvcd > 1` and the opponent rammed into us; that pattern is not addressable by output-only filtering and remains an open issue.
  - Online sample after 18 public episodes: `publicScore 1129.0`, leaderboard rank `24 / 342`. The trajectory is consistent with v24's 1133-1236 historical band and is climbing past v37's mid-sample dip.

## v39 isolated build-gate (rejected)

- `experiments/v39_no_scout_low_gap_only/main.py` keeps only the `BUILD_SCOUT/MINER` gap gate, drops v37's `north_only_jump` restriction.
- Local signal vs `v24` over 100 paired seeds: `v39` 38, `v24` 40, draws 22.
- This isolates that v37's local edge over v24 comes from the jump restriction, not the build gate alone. The combined patch in v37 is the production-safe pick.

## v38 v24 Safety Slot (active)

- `main.py` is still v24 code; submitted as `v38 v24 mainline safety slot to keep strong baseline active`; submission ref `53318414`.
- Purpose: keep a known `~1133-1236` agent in the active slot so the leaderboard score does not collapse if `v37` ends up settling lower than `v24` once both have ~30 public episodes.
- After this submission, the active slots are `v38` (v24 code) and `v37`. The leaderboard will track the better of the two, which keeps us close to v24's historical band as a floor while v37 either pulls ahead or stays flat.

## v40 Collision Predictor (active)

- `experiments/v40_collision_predictor/main.py` built on v37 with three narrow knobs targeting the dominant v37 failure mode (5/7 losses = factory_collision):
  - Knob 1 - 2-turn collision predictor: when `collision_tiebreak_bad` is true, also include cells reachable by an enemy factory with `emove_cd <= 2` (was `<= 1`), because our `factoryMovePeriod=2` cooldown leaves us stuck for exactly the same window the opponent uses to ram us.
  - Knob 2 - Conditional BUILD_SCOUT: keep v37's `factory_gap > 4` rule, but also allow BUILD_SCOUT when no visible enemy factory is within Manhattan 6 (so 2 of v37's losses with `zero support units` would have had a scout for tiebreak).
  - Knob 3 - BUILD_WORKER energy floor: require `factory_energy >= 350` instead of `>= 200`, since worker drains 200 + 200 spawn = 400, which is the source of v24/v38's repeated `energy=0` JUMP forced-IDLE boundary_scroll deaths.
- Local paired evaluations (swap-sides):
  - vs `v37` over 100 seeds: `v40 47, v37 33, draws 20` (+14).
  - vs `v24` (main.py) over 50 seeds: `v40 23, v24 19, draws 8` (+4).
  - vs `top2` over 50 seeds: `v40 24, top2 20, draws 6` (+4).
  - vs `pilkwang_structure` over 40 seeds: `v40 28, pilkwang 12, draws 0` (+16).
- All four opponents non-negative; the v37 head-to-head is the strongest signal because v40's diff vs v37 is exactly three knobs. Submitted as `v40 two turn collision predictor plus conditional scout plus worker energy floor`; submission ref `53320125`.
- Replay-action regression at the killing step (`scripts/replay_action_regression.py`) is uninformative for the "rammed on cooldown" pattern because the divergent move is several steps before the death; the script is kept but not used as a gating signal. Paired evaluations are the decision rule.
- 53320125 settled at `publicScore 858.1` after only 4 episodes (1 validation + 3 public, all 3 public are wins per `reports/replay_failures_v40.csv`); the low score is likely a small-sample artifact rather than a real signal that the agent is weaker than v37. To gather more online data, the same binary was resubmitted as `v40 2-turn collision predictor plus conditional scout`; resubmission ref `53320605`.
- Resubmission paired re-eval (smaller 25-seed swap-side runs, 50 games each except pilkwang at 40) for `53320605`:
  - vs `v37` 50 games: `v40 23, v37 22, draws 5` (+1).
  - vs `v24` 50 games: `v40 24, v24 21, draws 5` (+3).
  - vs `top2` 50 games: `v40 20, top2 19, draws 11` (+1).
  - vs `pilkwang_structure` 40 games: `v40 26, pilkwang 12, draws 2` (+14).
  - All four opponents still non-negative; the v37 and top2 deltas are noisier on this smaller sample but the signed direction matches the earlier 100/50/50/40 results.
- Online behavior after ~15 minutes of play:
  - 53320125 trajectory: `944.4` -> `843.9` (slid down as more episodes resolved).
  - 53320605 trajectory: `600.0` -> `839.5` -> `968.2` (climbing, but still under v38's 1007 and v37's 1142).
  - `reports/replay_failures_v40_605.csv` shows `78598494` is a `factory_collision` loss where v40 walks `NORTH` into the dest cell `(18, 67)` of an `IDLE` enemy factory. Knob 1 only adds the enemy's reachable cells to `enemy_factory_threats` when `collision_tiebreak_bad` is true; the enemy's current cell is also only added inside that gate, so when the tiebreak heuristic says we are not at risk, we still walk into a stationary enemy. This is the same failure mode v40 was meant to fix.
- Per the plan's refloor rule (`publicScore < 1100` on the new slot), `main.py` (v24 code) was resubmitted as `v41 v24 mainline refloor`; ref `53321085`. The active slots after refloor are:
  - `v37 save jump for north plus no scout at low gap`: `53317242`, `publicScore 1142.4`.
  - `v38 v24 mainline safety slot to keep strong baseline active`: `53318414`, `publicScore 1007.5`.
  - `v41 v24 mainline refloor`: `53321085`, pending.
  - `v40 2-turn collision predictor plus conditional scout`: `53320605`, `publicScore 968.2` (kept as a research data point, expected to be aged out as newer slots accumulate score).
- Open follow-up for any v42:
  - Move the unconditional `enemy_factory_threats.add((ec, er))` line OUT of the `if collision_tiebreak_bad:` block so the enemy's *current* cell is always treated as occupied; the tiebreak gate should only widen the reach prediction, not be the only way the enemy's own square is blocked. This is a one-line move and is the smallest correct fix for `78598494`-style collisions.

## Next Improvement Ideas

1. Fix side sensitivity.
   - Compare failures where `top2` loses as player 0 vs player 1.
   - Audit mirror inference and reserved-cell collision logic.

2. Wall reciprocal propagation.
   - If `(c, r)` has north wall, set south wall for `(c, r+1)` when known or inferred.
   - Same for E/W reciprocal walls, respecting fixed middle/perimeter walls.

3. Net-north path scoring.
   - Replace plain BFS with a small weighted search that penalizes SOUTH and rewards row gain.
   - Keep jump preference but avoid lateral loops.

4. Adaptive danger threshold.
   - Current emergency gap is mostly `<=2`.
   - Scale danger with scroll speed / step, especially late game.

5. Late energy protection.
   - Online v6 loss `78515845` reached turn 451 with factory energy `0`; the attempted `JUMP_NORTH` could not execute.
   - Prefer v11-style late scout energy reserves over hard scout-count caps, because one-scout and max-five-scout experiments were locally negative.

6. Replay-driven debugging.
   - Once an online submission succeeds, download episodes and logs.
   - Classify losses by death mode: scrolled, factory collision, wall trap, self-block, bad jump.

7. Blend `pilkwang_structure` safety into `top2`.
   - Reservation and action validation ideas may reduce friendly fire and bad spawn moves.
   - Avoid importing the entire heavy planner until it proves a paired-seed gain.

## 2026-06-04 Local Experiment Session — Full Results

**Context**: v51 (R1 TRANSFER_NORTH rule on v37) confirmed online at 1125, z+2.20 vs top2.
Baseline for new experiments is v51. All evals use `scripts/paired_eval.py --swap-sides`.

### Engine mechanics discovered (critical)

- `get_robot_max_energy(FACTORY) = float("inf")` — factory has no energy cap.
- TRANSFER to factory sends ALL of the transferring unit's energy. Miner with 300 energy → TRANSFER_SOUTH to factory → miner has 0, can't TRANSFORM (needs 100). Mine never forms. **Any TRANSFER-before-TRANSFORM implementation is broken.**
- Mine mechanics: Phase 6 (fill from mine to unit on mine) happens BEFORE Phase 7 (mine +50/turn regeneration). Factory on mine: gets all stored energy in one burst (200 on first turn), then +50/turn each subsequent turn.
- Tiebreak: `_resolve_tiebreak` compares total energy of ALL units (factory + scouts + workers + miners). Each dead scout = −50 from final pool. v37 builds ~4-6 scouts/game, 3-5 die → ~150-250 tiebreak disadvantage vs 0-scout agents.

### Experiments tested (vs v37 unless noted)

| Version | Change | vs v37 z | vs v24 z | vs v51 z | Verdict |
|---|---|---|---|---|---|
| v42a P01 only | unconditional enemy cell = unsafe | −1.02 | — | — | ❌ sacrifices winnable rams |
| v42b boundary | step≥400+gap≤15 Final Kick | −0.24 | — | — | ⚪ neutral, self-play can't detect |
| v43 worker | late worker buffer (no mine) | −1.15 | — | — | ❌ no mine income to offset |
| v44 economy | early E/W miner + TRANSFER + idle gap>6 | +2.56 | −3.35 | — | ⚠️ TRANSFER broken; gap>6 idle → row loss vs v24 |
| v44c | + no idle gap change | −0.23 | +0.11 | — | ⚪ neutral (TRANSFER still broken) |
| v44e | clean early NORTH miner (turn≤25, ≥400 energy) | −0.10 | +0.54 | — | ⚪ neutral/slight+ vs v24 |
| v44f | mine idle gap>8 | −0.73 | −0.60 | — | ❌ |
| v48 scout cap=1 | never rebuild first scout | −5.20 | −5.14 | — | ❌ vision loss catastrophic |
| v49 worker+mine | worker when own_mine active | — | — | −3.88 | ❌ |
| v50 anti-mirror | player-asymmetric BFSDIRS | draw_rate 20%→65% | — | — | ❌ routes agents away, more draws |
| v57 P01 (other session) | same as v42a | −0.77 | — | — | ❌ confirmed |
| v59 phase-switch | 3-phase architecture | −4.50 | −4.47 | — | ❌ catastrophic |
| v72 R1 rule | factory TRANSFER_NORTH to miner | +0.98 | −0.44 | — | ⚪ positive vs v37, negative vs v24 |
| v76 mine gap>5 | v37 mine trigger gap>6→>5 | −0.11 | **+2.09** | — | ✅ vs v24; ⚪ vs v37 |
| v80 v51+gap>5 | same on v51 base | — | — | −0.56 | ⚪ slightly negative |
| **v81 v51+gap5+early** | v51 + mine gap>5 + early miner | — | — | **+0.56** | 🔵 best positive vs v51 |
| v82 v51+gap5+boundary | + Final Kick | — | — | −1.61 | ❌ boundary hurts v51 |

### Key findings

1. **TRANSFER-before-TRANSFORM is unimplementable** — factory has inf energy cap so TRANSFER drains miner completely; mine never forms.
2. **Mine gap trigger gap>5 (v24 level) is slightly better than gap>6 (v37 level)** — improves mine_rate from ~30% to ~40%.
3. **Early miner (turn≤25, NORTH only, energy≥400) is neutral self-play but adds +1.1 z-score on top of gap>5**.
4. **Boundary defense consistently hurts against v51** — v51's R1 already handles late timing; final_kick gate adds overhead.
5. **Scout cap / anti-mirror both catastrophic** — vision loss and routing divergence dominate any tiebreak savings.
6. **Best new candidate: v81** (v51 + mine gap>5 + early NORTH miner), z=+0.56 vs v51 in 100 games (not z≥1.5 but positive direction).

### Recommendation for exploration slot

- **v81**: z=+0.56 vs v51, positive trend, mine_rate 27%→27% (miner_rate 47%→80%), first miner 110→47 steps. Safe exploration candidate.
- **v37**: proven 1142 online (still historically strongest confirmed slot), worth keeping as alternative if v81 underperforms.
