# Top-15 Competitor Compendium (maze-crawler)

Snapshot: 2026-06-03; data drawn from per-team focus sets (25 high-signal replays per team for ranks 2-15) plus the existing 60-replay bunterrrrr focus set for rank 1. Public score numbers are from `data/raw/leaderboard_v37_check3/maze-crawler-publicleaderboard-2026-06-03T07:55:58.csv`. Our baseline for the executive summary is `experiments/v37` (Jiayi Du, rank 24, score 1129.0).

## 1. Executive summary

- The whole top-15 stratum is built around the **factory-as-greedy-collector + early miner economy** that we identified in the bunterrrrr study. Across 14 newly-studied teams plus bunterrrrr, **every** team's median first miner step is well before our v37's typical first miner (≈95-159 in our online replays), and many already build their first miner before step 30.
- Our v37 leans heavily on routine `BUILD_SCOUT` while the top-15 either skip scouts entirely or build at most one or two. The most direct economy gap to rank-15 is **'less scout, faster first miner, more directional miner spam onto adjacent mines'**, not 'better path planning'.
- The single most under-used class of action by our agent is **directional miner builds toward EAST/WEST mining nodes when the factory has a comfortable south gap**. About half of the top-15 derives a significant share of their miner builds from side directions; v37 only mines north.
- The dominant failure mode at the top of the leaderboard is **`timeout_tiebreak`** (game reaches step 500 then loses on tiebreak), not boundary scroll or factory collision. Several teams have 70-100% of their losses falling into `timeout_tiebreak`. The implication is that getting to step 500 alive is necessary but not sufficient: the tiebreak is decided by support energy and final row, both of which the mine economy directly boosts.
- Conclusion: a +200-300 score jump from rank 24 to rank 15 is almost entirely an economy upgrade (earlier+cheaper miners, less scout overhead, opportunistic side mines, late wall removal). It is **not** an algorithmic search overhaul.

## 1.5 Counter-intuitive findings

These are the findings that don't follow from extrapolating the bunterrrrr study:

- **Two spellings, one NORTH miner mechanic.** Four teams (ranks 3, 8, 9, 13) use the legacy plain `BUILD_MINER` action for most miner builds. Current environment code defaults a build without a direction suffix to NORTH, so this is not an in-factory spawn and should be grouped with `BUILD_MINER_NORTH` when inferring geometry. Rank 3 Takahiro Matsumoto uses the legacy spelling for 100% of 134 observed miner builds.
- **A pure-scout strategy still reaches rank 15.** Rank 15 Nicolas Bridelance builds **zero miners** across 777 public episodes (and zero in our 25-replay focus set), averaging 7.8 scouts per game and 0 workers. They reach rank 15 with the same strategy class as our v37 (and our older v1/v6/v7/v11). The gap from our rank 24 to their rank 15 is therefore **execution detail, not strategy class**: collision avoidance, careful row management, and the occasional opportunistic miner. We do not need to adopt the mine economy to reach rank 15.
- **Heavy SOUTH usage is routine at the top.** Rank 3 Takahiro Matsumoto averages 89 SOUTH/JUMP_SOUTH actions per replay. Rank 6 Nicolas Klodt averages 71. Rank 13 Pavlo Ivanin averages 61. v37 treats SOUTH as a near-error and almost never plays it. The data shows SOUTH is a routine survival tool — racing south refreshes movement/jump cooldowns and avoids head-on factory collisions, then JUMP_NORTH bursts back. v37's scroll-fear is over-tuned.

## 2. Shared patterns (top-15 does, we don't)

1. **First miner well before step 50.** Median first-miner step across the studied focus replays:
   - rank 1 bunterrrrr: 40.0 (min observed 2)
   - rank 2 Андрей Савельев: 27.0 (min observed 7)
   - rank 3 Takahiro Matsumoto: 29 (min observed 6)
   - rank 4 Hazy Maze Crawler: 33 (min observed 6)
   - rank 5 PavelLiashkov: 40 (min observed 27)
   - rank 6 Nicolas Klodt: 65 (min observed 28)
   - rank 7 Daniel Bekker: 52 (min observed 28)
   - rank 8 AI TOOK MY JOB AND YOUR JOB!: 23 (min observed 3)
   - rank 9 ZERO HQR: 46.0 (min observed 14)
   - rank 10 JosephMontana: 32 (min observed 12)
   - rank 11 harmo-miu: 62.0 (min observed 32)
   - rank 12 CurveCowboy: 52 (min observed 18)
   - rank 13 Pavlo Ivanin: 30.0 (min observed 20)
   - rank 14 Henry Solberg: 49 (min observed 8)
   Our v37 typically first-builds a miner only after step 90, frequently never; closing this gap is the single highest-EV change.

2. **Drastically fewer scouts than v37.** Mean scouts per game by team:
   - rank 1 bunterrrrr: 0 (median 0.0)
   - rank 2 Андрей Савельев: 0 (median 0)
   - rank 3 Takahiro Matsumoto: 7.3 (median 6)
   - rank 4 Hazy Maze Crawler: 1.5 (median 0)
   - rank 5 PavelLiashkov: 2.7 (median 3)
   - rank 6 Nicolas Klodt: 5.3 (median 5)
   - rank 7 Daniel Bekker: 2.3 (median 0)
   - rank 8 AI TOOK MY JOB AND YOUR JOB!: 4.1 (median 4)
   - rank 9 ZERO HQR: 1.0 (median 0)
   - rank 10 JosephMontana: 1 (median 1)
   - rank 11 harmo-miu: 3 (median 3)
   - rank 12 CurveCowboy: 5.3 (median 6)
   - rank 13 Pavlo Ivanin: 5.8 (median 6)
   - rank 14 Henry Solberg: 2.7 (median 0)
   - rank 15 Nicolas Bridelance: 7.8 (median 8)
   6/15 teams essentially **never** build routine scouts (mean<0.5). Our v37 still spends energy on BUILD_SCOUT every 5-10 steps even when vision is no longer the bottleneck.

3. **Factory uses JUMP_* heavily as a fast NORTH and survival tool.** Average factory jumps per replay:
   - rank 1 bunterrrrr: 21.3
   - rank 2 Андрей Савельев: 35.7
   - rank 3 Takahiro Matsumoto: 40.8
   - rank 4 Hazy Maze Crawler: 27.7
   - rank 5 PavelLiashkov: 25.4
   - rank 6 Nicolas Klodt: 23.0
   - rank 7 Daniel Bekker: 28.9
   - rank 8 AI TOOK MY JOB AND YOUR JOB!: 33.6
   - rank 9 ZERO HQR: 26.4
   - rank 10 JosephMontana: 32.3
   - rank 11 harmo-miu: 28.8
   - rank 12 CurveCowboy: 29.5
   - rank 13 Pavlo Ivanin: 31.6
   - rank 14 Henry Solberg: 29.4
   - rank 15 Nicolas Bridelance: 32.4
   15 of 15 teams average ≥15 factory-jumps per replay. Our v37 only jumps reactively when scroll pressure is high; using JUMP_NORTH proactively (the moment a 2-cell empty corridor opens) is consistently used by the top of the board.

4. **Factory steps onto its own mines and TRANSFERs energy.** Even teams that build only 2-3 miners total still log dozens of `TRANSFER_*` actions per game, because the workflow is `BUILD_MINER_X → TRANSFORM → factory walks onto the new mine → TRANSFER from miner remainder + 50/turn from mine`. v37 does not exercise this loop.

5. **Late-game wall removal to reopen a path north.** Most top-15 replays show `REMOVE_NORTH`/`REMOVE_*` activity in the late game (steps 300-500). Mean wall-removals per replay are non-trivial for most teams. Our v37 essentially never removes walls.

## 3. Divergent patterns (top-15 internal schools)

- **Explicit-direction vs legacy-NORTH spelling.** Plain `BUILD_MINER` is a backward-compatible NORTH spawn, not a separate in-factory mechanic. The observed split is action spelling:
   - Directional school (14 teams): rank 1 bunterrrrr, rank 2 Андрей Савельев, rank 3 Takahiro Matsumoto, rank 4 Hazy Maze Crawler, rank 5 PavelLiashkov, rank 6 Nicolas Klodt, rank 7 Daniel Bekker, rank 8 AI TOOK MY JOB AND YOUR JOB!, rank 9 ZERO HQR, rank 10 JosephMontana, rank 11 harmo-miu, rank 12 CurveCowboy, rank 13 Pavlo Ivanin, rank 14 Henry Solberg
   - Teams observed using the legacy plain action: rank 3 Takahiro Matsumoto, rank 8 AI TOOK MY JOB AND YOUR JOB!, rank 9 ZERO HQR, rank 12 CurveCowboy, rank 13 Pavlo Ivanin
   - No-miner / mostly-scout school (1 teams, ≤0.5 miners per game): rank 15 Nicolas Bridelance

- **Pure-north miners vs side miners (within the directional school).** Pure-north miners (≥80% miner builds NORTH): rank 3 Takahiro Matsumoto, rank 8 AI TOOK MY JOB AND YOUR JOB!, rank 9 ZERO HQR, rank 13 Pavlo Ivanin. Heavy side miners (largest EAST+WEST share):
   - rank 14 Henry Solberg: side share 72.7% (N0/E55/W18/S27)
   - rank 11 harmo-miu: side share 52.4% (N48/E29/W24/S0)
   - rank 4 Hazy Maze Crawler: side share 48.9% (N34/E23/W26/S17)
   - rank 6 Nicolas Klodt: side share 48.3% (N43/E26/W22/S9)
   - rank 2 Андрей Савельев: side share 42.7% (N56/E21/W22/S1)

- **Early-miner specialists vs late-miner economy.** Early (median first miner ≤40): rank 1 bunterrrrr(40.0), rank 2 Андрей Савельев(27.0), rank 3 Takahiro Matsumoto(29), rank 4 Hazy Maze Crawler(33), rank 5 PavelLiashkov(40), rank 8 AI TOOK MY JOB AND YOUR JOB!(23), rank 10 JosephMontana(32), rank 13 Pavlo Ivanin(30.0). Late (median first miner ≥80): none. The early-miner school converts the opening 30 steps directly into energy, accepting some scroll risk; the late school plays a safer race first and only mines once the corridor is committed.

- **Scout-zero schools vs hybrid scout users.** Zero-scout (mean<0.5): rank 1 bunterrrrr, rank 2 Андрей Савельев, rank 4 Hazy Maze Crawler, rank 7 Daniel Bekker, rank 9 ZERO HQR, rank 14 Henry Solberg. Higher-scout hybrids (mean ≥2): rank 3 Takahiro Matsumoto(7.3), rank 5 PavelLiashkov(2.7), rank 6 Nicolas Klodt(5.3), rank 7 Daniel Bekker(2.3), rank 8 AI TOOK MY JOB AND YOUR JOB!(4.1), rank 11 harmo-miu(3), rank 12 CurveCowboy(5.3), rank 13 Pavlo Ivanin(5.8), rank 14 Henry Solberg(2.7), rank 15 Nicolas Bridelance(7.8).

## 4. Rare but lethal techniques

- **Step ≤10 BUILD_MINER**: the earliest miner builds observed (`min_first_miner`) include rank 1 bunterrrrr(step 2), rank 2 Андрей Савельев(step 7), rank 3 Takahiro Matsumoto(step 6), rank 4 Hazy Maze Crawler(step 6), rank 8 AI TOOK MY JOB AND YOUR JOB!(step 3), rank 9 ZERO HQR(step 14), rank 10 JosephMontana(step 12), rank 14 Henry Solberg(step 8). Building a miner at step ≤10 commits to the economy before the opponent has scouted and before scroll has started; in our v37 the equivalent slot is wasted on `BUILD_SCOUT_NORTH`.
- **Defensive `SOUTH`/`JUMP_SOUTH` to dodge collision and reset cooldowns.** The teams that use the most survival-south actions per replay are rank 3 Takahiro Matsumoto(89.2), rank 6 Nicolas Klodt(71.4), rank 13 Pavlo Ivanin(60.9). v37 actively avoids SOUTH because of scroll fear; the data shows the top-15 routinely accept one or two SOUTH steps in exchange for not dying in a head-on factory collision.
- **Late-game `REMOVE_NORTH` to break maze walls late and pop one extra row in tiebreak.** Several profiles show non-trivial `REMOVE_*` counts even though their explorers are minimal; the factory removes walls itself once it has enough energy and can no longer step around them. In our v37, factory wall-removal is essentially never triggered.
- **High-reward jackpot runs.** Several teams have at least one focus replay with reward ≥5000 (mine economy snowball). Highest observed max reward per team:
   - rank 1 bunterrrrr: max reward 10118.0
   - rank 2 Андрей Савельев: max reward 8728.0
   - rank 3 Takahiro Matsumoto: max reward 8609.0
   - rank 4 Hazy Maze Crawler: max reward 7299.0
   - rank 5 PavelLiashkov: max reward 6701.0
   - rank 6 Nicolas Klodt: max reward 8426.0
   - rank 7 Daniel Bekker: max reward 7373.0
   - rank 8 AI TOOK MY JOB AND YOUR JOB!: max reward 4048.0
   - rank 9 ZERO HQR: max reward 5757.0
   - rank 10 JosephMontana: max reward 8603.0
   - rank 11 harmo-miu: max reward 7592.0
   - rank 12 CurveCowboy: max reward 7711.0
  These outlier games dominate the public score under the Kaggle ranking system, so missing them costs more than one would think from a 'most games go to step 500' prior.

## 5. Highest-ROI changes for v38 (rank 24 → 15)

1. **Earlier first miner.** Push the first `BUILD_MINER_*` to step 20-30 unconditionally when an adjacent mining node is visible north, east, or west. This is the change all of bunterrrrr, Андрей Савельев, Takahiro Matsumoto, Hazy Maze Crawler, harmo-miu, and ZERO HQR have already made; it is the dominant reason we are below them. (Re-uses the experiment v15 + v17 + v19 lineage but commits to it as the default rather than an A/B.)
2. **Add side miners under a clear gating rule.** When the factory's southBound gap is ≥6 and `move_cd > 0`, allow `BUILD_MINER_EAST` / `BUILD_MINER_WEST` if the adjacent cell is a mining node. This is what splits Андрей Савельев / Takahiro Matsumoto / Hazy Maze Crawler from the pure-north school and is consistently associated with reward outliers ≥3000. Re-use the v21 gating logic but ship it.
3. **Cap scouts at 1-2 then disable.** The strong correlation across the top-15 between low scout count and high score is overwhelming; v37's routine scout cycle is a tempo and energy leak. Either gate `BUILD_SCOUT` behind low explored coverage (similar to v19's `SCOUT_DELAY_STEP=24` but harder: cap total scouts at 2), or disable routine scouts after step ~30 and rely on the factory's local vision plus existing scouts/workers.

## 6. Cross-team metrics table

| Rank | Team | Score | Focus W-L-D | Avg reward | Final factory energy | First miner step (median) | Scouts (mean) | Miner builds (mean) | Miner direction NESW/U% | Max mines | Primary failure |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bunterrrrr | 2221.4 | 54-4-2 | 4269.7 | 6728.6 | 40.0 (min 2) | 0 | 4.1 | 55/16/27/2 | 1.6 | factory_collision |
| 2 | Андрей Савельев | 1677.5 | 11-11-3 | 384.0 | 5052.4 | 27.0 (min 7) | 0 | 3.3 | 56/21/22/1 | 1.2 | timeout_tiebreak |
| 3 | Takahiro Matsumoto | 1659.8 | 9-13-3 | 551.1 | 6137.2 | 29 (min 6) | 7.3 | 5.4 | 100/0/0/0 | 1.8 | factory_collision |
| 4 | Hazy Maze Crawler | 1588.2 | 10-12-3 | 640.5 | 5245.4 | 33 (min 6) | 1.5 | 3.5 | 34/23/26/17 | 1.8 | timeout_tiebreak |
| 5 | PavelLiashkov | 1526.5 | 11-11-3 | 530.7 | 5383.7 | 40 (min 27) | 2.7 | 5.8 | 38/23/19/21 | 2.6 | timeout_tiebreak |
| 6 | Nicolas Klodt | 1500.3 | 12-13-0 | 851.1 | 5764.0 | 65 (min 28) | 5.3 | 2.3 | 43/26/22/9 | 1.2 | timeout_tiebreak |
| 7 | Daniel Bekker | 1399.8 | 11-14-0 | 1304.4 | 3585.1 | 52 (min 28) | 2.3 | 2.2 | 59/17/24/0 | 1.5 | timeout_tiebreak |
| 8 | AI TOOK MY JOB AND YOUR JOB! | 1398.6 | 6-16-3 | 160.1 | 2218.4 | 23 (min 3) | 4.1 | 4.3 | 100/0/0/0 | 2.1 | timeout_tiebreak |
| 9 | ZERO HQR | 1369.4 | 11-11-3 | 287.6 | 2983.5 | 46.0 (min 14) | 1.0 | 4.1 | 100/0/0/0 | 2.3 | timeout_tiebreak |
| 10 | JosephMontana | 1338.4 | 10-13-2 | 335.9 | 6060.4 | 32 (min 12) | 1 | 5.4 | 40/21/21/18 | 2.2 | boundary_scroll |
| 11 | harmo-miu | 1274.7 | 10-12-3 | 1257.9 | 5008.7 | 62.0 (min 32) | 3 | 1.7 | 48/29/24/0 | 1.2 | factory_collision |
| 12 | CurveCowboy | 1202.1 | 10-11-4 | 687.4 | 2996.9 | 52 (min 18) | 5.3 | 2.4 | 44/25/10/21 | 1.6 | factory_collision |
| 13 | Pavlo Ivanin | 1193.8 | 8-14-3 | 15.3 | 132.8 | 30.0 (min 20) | 5.8 | 0.9 | 100/0/0/0 | 0.6 | factory_collision |
| 14 | Henry Solberg | 1188.6 | 7-15-3 | 394.1 | 1719.2 | 49 (min 8) | 2.7 | 1.3 | 0/55/18/27 | 0.9 | timeout_tiebreak |
| 15 | Nicolas Bridelance | 1176.8 | 9-12-4 | 85.0 | 318.3 | – (min –) | 7.8 | 0 | 0/0/0/0 | 0 | factory_collision |

## 7. Where to look next

- Per-team `profile.md`s in `reports/top_competitors/<slug>/profile.md` carry richer breakdowns including action-mix, row-by-step, top-15 head-to-head counts, plus a **Tactical archive** narrative section that answers the per-team qualitative questions (core playbook, v37 differences, unique tricks, weakness, projected v37 matchup).
- `reports/top_competitors/aggregate_metrics.csv` is the machine-readable join of every metric used in this compendium; rerun via `python scripts/top_competitors_summary.py --ranks 2-15` after re-downloading replays. `reports/top_competitors/aggregate_metrics.json` is the same data with full nested structures (vs-top15 counters, action totals).
- `reports/top_competitors/<slug>/replays/` holds the raw JSON (~4 MB each) for spot-checking specific episodes. Useful starting points:
  - To study undirected `BUILD_MINER`: `reports/top_competitors/03_takahiro_matsumoto/replays/` and `08_ai_took_my_job/replays/`.
  - To study side miners: `reports/top_competitors/04_hazy_maze_crawler/replays/`, `10_josephmontana/replays/`.
  - To study off-axis (no-NORTH) miners: `reports/top_competitors/14_henry_solberg/replays/`.
  - To study pure scout (our own school): `reports/top_competitors/15_nicolas_bridelance/replays/` — the most direct apples-to-apples comparison to v37.
- Pipeline scripts:
  - `scripts/top_competitors_pipeline.py` orchestrates fetch / focus / download / metrics per rank set.
  - `scripts/top_competitors_summary.py` produces per-team profile.md and the aggregate CSV/JSON.
  - `scripts/append_tactical_archives.py` injects/refreshes the qualitative tactical archive into each profile.md.
  - `scripts/write_top_competitors_compendium.py` produces this compendium.

