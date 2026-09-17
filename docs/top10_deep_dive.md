# Top 1-10 深度挖掘 (W8)

最后更新: 2026-06-03。研究者: 内部 W8。

数据快照: 各队 Kaggle 公开 episode 抓样 + W3 已下载的 14 队 × 25 局 focus replay (350) + bunterrrrr 60 局 focus (W8 补全) + 我们 v24/v30 共 44 局 = 454 局 episode。

---

## 0. 方法学决策 (200-400 字)

**视角**: 主 player-centric, 副 archetype-clustering. 理由: 第 1 名 (2221) 和第 10 名 (1338) 之间 883 ELO, 单一 "emergent meta" 假设过强; 但 K-means 在 13 个策略特征上能自然分出 3 簇, 所以也加一个 archetype overlay。

**方法组合**: B (手工 feature 抽取 + RandomForest/GBDT 看 importance) + H (浅决策树挖可读规则) + 轻量 K-means 在 team-level aggregate 上 + 失败模式定性 step-by-step (bunterrrrr 4 损 + Joseph 7 boundary_scroll 等)。

**没有选**:
- C (Levenshtein/DTW): action 序列对齐到 step 级会被噪声淹没, 拿不到战略意图;
- D/E/F (深度嵌入 / LSTM / 对比学习): 454 episode 太少, 喂不饱, 且不可解释——而我们要的是可执行规则;
- G (因果反事实): 没有 interventional 数据, 只有 observational;
- I (HMM phase detection): 用更轻量的 "first_miner / first_scout / energy@step" 已经足以挖出 phase, 不需要正式 HMM.

**理由**: W3 已经把数据准备成 tabular CSV, 几乎一个 sklearn 跑通; 而我们最终要的不是 embedding 而是 "我们要不要建 worker"、"我们要不要把首 scout 推迟到 step 60+" 这类决策。可解释性 >> 模型复杂度。CPU 单机 < 5 分钟跑完所有分析。

**视角的具体落地**: 第二部分 10 份个人档案 (player); 第三部分 archetype + emergent meta (total); 第四部分反制矩阵按 player 行 + archetype 列。

---

## 1. 执行摘要 (TL;DR, 10 行)

**一张图概括差距**: `reports/top10_analysis/plot_energy_trajectory.png` — bunterrrrr 在 step 400 时平均能量 7500, 我们 v24 平均 2700——是 top10 最弱队 (AI TOOK) 3200 的 84%, 是 top1 的 36%。


1. **Top 1-10 不是单一流派**——K-means 自然分出 3 簇: Silent Miner (#1,#2,#4,#9), Hybrid (#3,#5,#6,#7,#10), Scout Swarm (#8)。Top 4 Hazy Maze Crawler 实际上是 "Silent Miner + 多 worker" 变种, 68% 的 episode 不建 scout。
2. **决策树最锋利的一条规则**: `build_worker ≤ 0.5 AND scout_per_minute > 0.29 → us`; 反过来 `build_worker ≤ 0.5 AND scout_per_minute ≤ 0.29 AND idle_pct ≤ 63.9 → top1-3`。
3. **我们 v24 最孤立的 3 个 deficit**: (a) 0 workers (所有 top10 都 ≥0.64), (b) 1.25 miners (top10 范围 2.16-5.80), (c) peak factory energy 仅 2616——比 top10 最弱的 AI TOOK MY JOB (4240) 都低 38%。
4. **bunterrrrr 不是"完美 agent"**: 当前 submission 4 损 + 3 平。3 损是 factory_collision/single_factory_death (战术 edge case, 跟我们 v24 的 collision loss 同源), 1 损是 timeout_tiebreak 被 harmo-miu 的更强经济磨死。它的真正天花板天敌不是某个流派而是"高经济长游戏" + "凑近碰撞"。
5. **Top 1 vs Top 10 内部差距主要是 EXECUTION 而非 STRATEGY**: bunterrrrr 与 ZERO HQR 同属 Silent Miner, 但 bunterrrrr first_miner 中位数 47 vs ZERO HQR 58, peak energy +1895, final energy +3745——同战略, 时序更紧。
6. **JosephMontana (#10) 是 Top10 里最像 v24 病的队伍**: 25 局里 7 个 boundary_scroll 死亡——"末期高能量但被卷死"。我们 v30 的 6 个 boundary_scroll 死亡是同一个病。
7. **Andrey (#2) 是 bunterrrrr 的"60 分克隆"**, Takahiro (#3) 是 "scout 7 个 + 4 方向 miner" 的明显异类, Nicolas Klodt (#6) 用"极限耐心 (first_miner 78, peak energy 7381)" 站稳 top 6。
8. **AI TOOK MY JOB (#8) 是 bunterrrrr 唯一持续画平的对手 (3 平 in our sample)**——它的高 worker (4.44)+高 scout (4.12) 的"广撒网"反而在长 game 里把 bunterrrrr 的能量耗到平。这反映 Silent Miner 对 "spam 流" 没有压制力。
9. **明天就能做的最高 ROI 一条**: 让 v24 在 "step ≥ 300 且 factory_gap ≥ 8 且 factory_energy ≥ 500 且没有可用 miner" 时建 1 个 worker (target NORTH 优先)。理由: 所有 top10 都建 worker, 决策树规则也指向; 而 v24 现行代码里压根没有 worker 分支。
10. **不要复制 Joseph/AI-TOOK 的 worker 暴堆**: 5+ workers 反而导致末期 boundary_scroll 大量死亡; 0.6-1.5 之间是 sweet spot。

---

## 2. 第一部分: 数据准备

| 数据源 | 样本数 | 说明 |
|---|---|---|
| W3 已下载: `reports/top_competitors/02..15/replays/` | 14 队 × 25 = 350 局 | 含 strategy_metrics, miner_events, failure_analysis 三表 |
| bunterrrrr: `reports/replays_bunterrrrr_focus/` | 60 局 (W8 补完, 原 17 局) | 当前 submission `53084625` 的 60 个 high-signal episode (focus 选股: 损/平/强对手/最新) |
| 我们 v24: `reports/replays_v24/` + `replays_v30/` (同源代码) | 44 局 (W8 重合并) | 输出到 `reports/top10_analysis/jiayi_v24_combined_strategy_metrics.csv` |
| **总数据**: `reports/top10_analysis/master_episode_matrix.csv` | **454 episode × 50 列特征** | 4 类 team_aggregate.csv (16 队 aggregate) |

**统一特征 schema** (节选): `first_miner, first_scout, build_miner, build_scout, build_worker, factory_jump, max_factory_energy, final_factory_energy, max_mines, steps, row_50..400, energy_50..400, idle_pct, north_pct, jump_north_pct, transfer_north_pct, remove_north_pct, miner_per_minute, scout_per_minute`。

派生脚本: `scripts/top10_build_master_matrix.py`, `scripts/top10_analyze.py`, `scripts/top10_per_team_summary.py`。所有图表保存在 `reports/top10_analysis/`。

---

## 3. 第二部分: 选手视角的 10 份档案

每队列出: ID 卡, 核心打法, 唯一差异, 主要弱点 (失败模式), 我们的针对反制。所有数字来自 `reports/top10_analysis/per_team_dossier.md` (60 局 bunterrrrr + 25 局其他)。

### #1 bunterrrrr (2221.4, 我们样本 W-L-D 54-4-2)

- **核心打法**: Silent Miner。0 scout (100% episode), 4.07 miners/ep, 0.9 workers/ep, first_miner 中位数 47, peak factory energy 7067, final 6729——economy 怪物。33% NORTH, 50% IDLE。
- **唯一差异**: 不仅"不建 scout", 还会**建 mine 后让工厂直接踩上去吸 energy + 50/turn**——这是公开 baseline 没有的机制 (已在 docs/research.md §Bunterrrrr Leader Study 验证)。miner 方向分布 NORTH 55% + EAST/WEST 33% + SOUTH 2%, 比 W3 横向研究的"纯北流"更激进。
- **主要弱点 (失败模式)**: 4 损中 3 个是 `factory_collision`/`single_factory_death` (78466173 vs Betise, 77886516 vs ZERO HQR, 78049480 vs test_maze-crawl), 1 个是 `timeout_tiebreak` 被 harmo-miu 的更强 economy 磨死 (77981879)。它的 collision 多发生在工厂为了"踩矿"或"再次开矿"凑近敌方时, 例如 78049480 在 energy 8169 的情况下 `BUILD_MINER_EAST` 撞上敌方 EAST 移动。
- **针对反制**: 我们打 bunterrrrr 几乎必败 (我们 v24 在 60 个公开 bunterrrrr 对局里没数据可比, 但所有 top10 单赛季加起来才赢 bunterrrrr ~20 局)。**唯一可行反制**: 模仿 AI TOOK MY JOB——多 build_worker (4.4) + 高 IDLE, 在 step 500 timer 到时, 用 worker support energy 拉近 final energy 差距, 争取 draw。

### #2 Андрей Савельев (1677.5, W-L-D 11-11-3)

- **核心打法**: bunterrrrr 的 60 分克隆 (同 archetype 0)。0 scouts (100%), 3.28 miners, 0.64 workers, first_miner 中位数 29 (比 bunt 还早!), peak energy 5980。北方 jump (`JUMP_NORTH` 输出 295 次) 是他最强武器。
- **唯一差异**: 比 bunt 更激进的 EAST/WEST 侧矿——miner 中 EAST:WEST:NORTH = 17:18:46, 比 bunt 的 EAST 65 / WEST 38 比例反过来。所以他经济没 bunt 那么单边北倾。
- **主要弱点**: 11 损里 100% 是 `timeout_tiebreak` (step 500)。他活到底但 final energy 比 Klodt/Hazy/Takahiro 低, 在 tiebreak 里输。被 Klodt (3 损) / Takahiro (3 损) / Hazy (2 损) 杀。
- **针对反制 (我们)**: 同 bunt——我们没工具直接打赢他。**复制 Klodt 的"耐心高 energy"打法** (workers 1.2, peak energy 7381): 多 worker 把 final energy 拉到 4500+ 即可 in tiebreak 赢他。

### #3 Takahiro Matsumoto (1659.8, W-L-D 9-13-3)

- **核心打法**: Hybrid 中的 SCOUT-MAX 异类。7.32 scouts/ep (10 队中最多!), 5.36 miners (top 3 多), 1.24 workers, first_miner 中位数 29。peak energy 6373。SOUTH 行动占 13.4% (top10 第二高), 说明会主动 save-south。
- **唯一差异**: miners 100% 标记为 `UNDIRECTED` (BUILD_MINER 而不是 BUILD_MINER_NORTH)——说明他在 mine cell 上直接 BUILD, 而非"先走到 cell 再 spawn"。这种"直接吸"配合 7 个 scout 找点能让他第一矿在 step 6-29 内出。
- **主要弱点**: 13 损里 `timeout_tiebreak:5, boundary_scroll:4, factory_collision:3, simultaneous_tiebreak:1`——失败模式分布最广, 没有单一致命点, 但 boundary_scroll 4 个表示他在末期工厂 gap 收紧时会失去节奏。
- **针对反制**: 因为他有 SOUTH 13.4% 的高比例 save-south 行为, 我们可以利用"敌方 SOUTH 时段"伪装继续北推 (他 SOUTH 时我们多 NORTH 1-2 步), 把 final row 拉开。具体: v24 已经在做 v34 phase explore——这里可以加 `if opp_recent_action == SOUTH: prefer_NORTH_aggressively`。

### #4 Hazy Maze Crawler (1588.2, W-L-D 10-12-3)

- **核心打法**: K-means 分到 **Silent Miner** 簇——但是"带 worker 的变种"。1.48 scouts (median 0! 68% 的 episode 不建 scout), 1.92 workers (Silent Miner 簇里最高), 3.52 miners。peak energy 7099 (top10 第二高)。
- **唯一差异**: pct_episodes_no_scout = 68% ——跟 bunt (100%) / Andrey (100%) / ZERO HQR (76%) 同流派, 但 worker 1.92/ep 是这个簇里最高 (vs Andrey 0.64, ZERO 0.76)。证明 "Silent Miner + 1-2 worker" 是这个流派的进阶版, 比纯 0-scout 更稳。
- **主要弱点**: 11/12 损都是 `timeout_tiebreak`——他活, 但 final energy 5245 不够拉开。被 Andrey 5 次, Pavel/Klodt 各 3 次。
- **针对反制**: 同 bunt 系——我们短期没法打赢他。

### #5 PavelLiashkov (1526.5, W-L-D 11-11-3)

- **核心打法**: Hybrid 中的 MINER-MAX。5.8 miners/ep (top10 最多!), 2.68 scouts, 0.88 workers, first_miner 中位数 40, peak energy 6606, max_mines 2.6 (同时拥有的矿数 top10 最高)。
- **唯一差异**: 同时拥有多个矿——max_mines 中位数 3.0, 是 bunt 的 1.0 的 3 倍。他用"广撒矿网"压制对手能量补充。
- **主要弱点**: 11 损中 `timeout_tiebreak:6, factory_collision:3, boundary_scroll:2`——比 Andrey 多元化。被 Andrey 5 次 (Pavel 跟 Andrey 都是 Silent/MinerHeavy, 内部互克)。
- **针对反制**: 他的 multi-mine 需要 transfer 路径连接, 任何时候我们能切断他 mine→factory 的路径 (堆墙) 就能拖他经济节奏。但短期内我们的 wall 控制弱, 实际反制还是先把自己的经济堆起来。

### #6 Nicolas Klodt (1500.3, W-L-D 12-13-0)

- **核心打法**: PATIENT-HIGH-ENERGY。first_miner 中位数 65 (top10 最晚!), 5.28 scouts, 2.32 miners (top10 最少之一), 1.2 workers, peak energy 7381.5 (top10 最高!), median first_scout 46。
- **唯一差异**: 他用极致的耐心换取最高 energy 池。极少 `JUMP_NORTH` (0.49%), 高 `TRANSFER_SOUTH:258 + TRANSFER_WEST:204`——靠 transfer 把 support 单位的 energy 全部抽回工厂。
- **主要弱点**: 10/13 损都是 `timeout_tiebreak`。打不死, 但跟 Andrey/Pavel 这种 economy slightly weaker 但 row 推得更快的对手就会被反 timeout。被 Andrey 5 次, Bekker 3 次。
- **针对反制**: 他在 step 100 前推 row 较慢 (row_100 = 21.5, 我们 22.1 已经持平)。**如果我们能在 step < 100 之前争取到 row 优势 + 不死**, 末期 Klodt 自己会 IDLE 47% 而我们继续移动, 完全可以反 timeout 赢。具体: 维持 v24 早期 scout 推进, 但避免末期 BUILD_SCOUT 浪费能量。

### #7 Daniel Bekker (1399.8, W-L-D 11-14-0)

- **核心打法**: WORKER-MAX 异类。3.16 workers (top10 最多, 跟 Joseph/AI TOOK 类似), 2.32 scouts, 2.16 miners (top10 最少之一)。peak energy 5182, final 3585 (top10 最低!)。
- **唯一差异**: 是 top10 里唯一 SOUTH miner = 0 的队伍 (NORTH 59%, EAST 17%, WEST 24%, SOUTH 0)。他从不向南挖矿, 是更保守的"全北经济" + worker 辅助。
- **主要弱点**: 14 损中 `timeout_tiebreak:9, boundary_scroll:4`——他的 final energy 太低 (3585), tiebreak 几乎必输。被 PavelLiashkov 杀 6 次 (PavelLiashkov 的 max_mines 2.6 对 Bekker 的 1.5 是 1.7 倍能量补充优势)。
- **针对反制**: Bekker 的 worker spam 有上限 (3.16/ep), 我们可以照搬轻 worker (1-1.5) 模式, 又因为我们 row 推进比他快 (我们 row_200=40 vs 他 36), 在前 200 步可以拉开足够距离, 再用 worker 末期撑 energy, 反 timeout 赢他。

### #8 AI TOOK MY JOB AND YOUR JOB! (1398.6, W-L-D 6-16-3)

- **核心打法**: Scout Swarm 唯一代表。4.12 scouts + 4.44 workers + 4.28 miners——全面 SPAM。peak energy 4240 (top10 最低), final 2218 (远低于其他 top10)。median first_scout = 3, first_miner = 23 (极早)。
- **唯一差异**: 1218 个公开 episode (top10 最多, 玩了很多局)。jump_dirs_total 里 EAST:85 (远超其他队), 行动靠侧向 jump 占位。
- **主要弱点**: 16 损里 14 个 `timeout_tiebreak`——他活到最后但 energy 不够, 跟 Klodt 7 次. 但他对 bunterrrrr 取得 3 平 (我们样本里), 是唯一持续平 bunt 的队伍——靠 worker spam 把 bunt 拖到 step 500 平局。
- **针对反制**: AI TOOK 的 spam 风格在 row_200=35.5 一项上跟我们 v24 row_200=40 有 4.5 row 差距。**我们的 row 推进比他快**——如果我们 step <200 内保持 row 领先, 末期他靠 spam 也补不回来。具体: 把 v24 的 NORTH/JUMP_NORTH 比例从当前 18% + 1.4% 提到 22% + 2%。

### #9 ZERO HQR (1369.4, W-L-D 11-11-3)

- **核心打法**: Silent Miner 的弱化版。1.04 scouts (中位数 0, 76% no scout), 4.12 miners, 0.76 workers, first_miner 中位数 46 (比 bunt 32 晚 14 步!), peak energy 5172 (vs bunt 7067)。
- **唯一差异**: 战略上跟 bunt 同 archetype, 但 EXECUTION 差距巨大——first_miner 晚 14 步, peak energy 少 1895, final energy 少 3745。证明 Silent Miner 不是"无脑 0 scout"就能学会, 时序紧度才是关键。
- **主要弱点**: 11 损中 8 个被 Nicolas Klodt 杀!——8/11 = 73%。Klodt 的"超耐心 + 超高 energy" 是 ZERO HQR 的天然克星。
- **针对反制**: ZERO HQR 是我们最有机会赢的 top10 队伍之一。他 final energy 中位数 3011, 我们 v24 final energy 中位数 1036。但 v24 升级到 final 3000+ 后, 跟 ZERO HQR 至少可以 timeout 50-50。建议: 复制 Klodt 路线 (高 worker, 高 IDLE, 高 peak energy), 即可以 ZERO HQR 为试验对手。

### #10 JosephMontana (1338.4, W-L-D 10-13-2)

- **核心打法**: WORKER-MAX + 早 miner。5.12 workers (top10 最高!), 1.0 scouts (median 1), 5.44 miners (top10 第二高), first_miner 中位数 32, peak energy 6543。也是 top10 里 JUMP_NORTH 输出最大的一队 (325 次, 跟 harmo-miu 322 并列)。
- **唯一差异**: 工人和矿工都堆很多, 但比 AI TOOK 多了"高经济结果"——peak 6543 跟 top5 持平。
- **主要弱点**: **失败模式集中在 `boundary_scroll:7, timeout_tiebreak:6`**——7 个 boundary_scroll 是 top10 最严重的"末期被卷死"。看 78469482 vs harmo-miu (step 463 死, south=97, our row=96, energy 6460——能量很高但被卷出了边界); 78470073 vs ZERO HQR (step 467 死, our row=98 vs opp row=101)。
- **针对反制**: Joseph 的 boundary_scroll 病跟我们 v30 的 6 个 boundary_scroll 死亡完全同源!——这是同一类 bug。意思是: **如果我们解决 boundary_scroll, 我们对 Joseph 可以反超**。具体修复方向 (跟 v32/v33 的 late scroll mode 是一类): step ≥ 400 且 factory_gap ≤ 10 时强制 NORTH/JUMP_NORTH, 禁用 BUILD/REMOVE 之类的 tempo loss action。

---

## 4. 第三部分: 总体视角的 Emergent Meta

### 4.1 Archetype 自动发现 (K-means, k=3)

在 13 个 team-level 策略特征上做 K-means (StandardScaler 后), 自然分出 3 簇:

| Archetype | 成员 | 关键中心值 (mean) |
|---|---|---|
| 1: **Silent Miner** | bunterrrrr (#1), Андрей Савельев (#2), **Hazy Maze Crawler (#4)**, ZERO HQR (#9) | 0.63 scout, 3.75 miner, 1.06 worker, peak energy 6330, **86% episode 无 scout** |
| 0: **Hybrid** | Takahiro (#3), Pavel (#5), Klodt (#6), Bekker (#7), Joseph (#10) | 3.72 scout, 4.22 miner, 2.32 worker, peak energy 6417, **10% episode 无 scout** |
| 2: **Scout Swarm** | AI TOOK MY JOB (#8) | 4.12 scout + 4.44 worker + 4.28 miner spam, peak energy 4240, first_miner step 32 |

PCA 可视化见 `reports/top10_analysis/plot_pca_archetypes.png`。我们 v24 (灰色 X) 在 PCA 平面上**完全孤立**——既不在 Silent Miner (我们 0% no-scout, 他们 86%) 也不在 Hybrid (我们 build_worker=0, 他们 2.32 平均), 离 Scout Swarm 最近但仍差 build_worker 0 vs 4.44。**没有任何 top10 团队跟我们 v24 在策略空间靠近**——这是非常糟糕的信号。

**Silent Miner 是 ELO 上限最高的簇** (4 队中 1+2+4+9 三个进 top 5)。Hybrid 是 ELO 中位最稳的簇 (5 队都在 1338-1660 之间)。Scout Swarm 只 1 队代表, n 不够下结论。

### 4.2 Top 1-10 共同做但我们 v24 没做的 3 件事 (硬证据)

1. **建 worker** (重要度 #1)。Top10 全员都建 ≥ 0.64 worker/ep:
   - bunterrrrr 0.9, Andrey 0.64, Takahiro 1.24, Hazy 1.92, Pavel 0.88, Klodt 1.2, Bekker 3.16, AI TOOK 4.44, ZERO HQR 0.76, Joseph 5.12。
   - 我们 v24: **0.0**。
   - 数据证据: `reports/top10_analysis/team_aggregate.csv` `build_worker_mean` 列, 44 局 v24 sample 0/44 局含 worker。
   - 解释: worker 用于 wall removal 或 energy support, top10 共识是"至少 1 个"作为末期 energy buffer。

2. **首矿提前**。Top10 队的 first_miner 中位数中, 最早 23 (AI TOOK), 最晚 65 (Klodt)。我们 v24 first_miner 中位数 43, mean 64。看似不算晚, 但**有 38.6% 的 episode 我们根本不建 miner**, 即 17/44 局是 0-miner。Top10 里只有 Andrey (28%) / harmo-miu (12%) 偶尔 0 miner, 其他基本 100% 建。
   - 数据证据: `pct_episodes_no_miner` 列, 我们 38.6%, top10 中位数 4%。
   - 解释: 我们的 north-mine 触发条件太严, 导致大量 game 完全没有矿经济。

3. **更高的能量峰值**。我们 peak factory energy 2616 vs top10 范围 4240-7381。
   - 数据证据: `max_factory_energy_mean` 列。AI TOOK MY JOB 是 top10 最弱 (4240), 我们仍少 38%。
   - 解释: 这是 (1) + (2) + miner-collection 三个缺陷的合成结果, 单独修补任一项都救不回。**先修 (1) 和 (2)** 可能就把 energy 抬到 4000+。

### 4.3 Top 1-10 内部分歧 (≥2 流派)

**流派 A: Silent Miner (#1, #2, #4, #9)**——0/低 scout (≥68% episode 不建 scout), miner-driven, 高 IDLE。共识假设是 "scout 是 50 energy 的浪费, 直接堆 miner 把 factory 喂饱"。代表 bunterrrrr 上分 2221.4。Hazy Maze Crawler 是这个簇里多 worker (1.92) 的变种, 也是这簇唯一进 top 5 但不是 top 2 的队。

**流派 B: Patient High-Energy Hybrid (#5 Pavel, #6 Klodt, #3 Takahiro)**——少量到中等 scouts, 1-2 workers, peak energy 6300-7400。代表 Klodt 1500.3。

**流派 C: Worker-Heavy + Scout Spam (#7 Bekker, #8 AI TOOK, #10 Joseph)**——3-5 workers, 1-5 scouts, energy 普遍较低 (3500-6500), 输靠 boundary_scroll 多。

**相对优劣**:
- A 上限最高 (#1 2221), 下限最低 (#9 1369)——同 strategy execution 差 14 步首矿就丢 800 ELO;
- B 中位最稳 (1500-1660);
- C 是 worker 的代价方——多 worker 多 build cooldown, 末期被 scroll 卡。

### 4.4 决策树挖出的可读规则 (depth 4)

完整规则见 `reports/top10_analysis/decision_tree_rules.txt`。关键路径:

```
build_worker ≤ 0.5  AND  scout_per_minute ≤ 0.29  AND  idle_pct ≤ 63.9  → top1-3
build_worker ≤ 0.5  AND  scout_per_minute >  0.29                       → us (任何 row_100)
build_worker >  0.5  AND  jump_north_pct > 2.41                         → top1-3
build_worker >  0.5  AND  south_pct ≤ 0.58  AND  energy_200 ≤ 4509  AND  idle_pct ≤ 53.9  → top1-3
```

**翻译**: 决策树看一眼我们的 scout_per_minute > 0.29 + build_worker == 0, 就直接判我们是 "us"。即"建 scout 频率太高 + 不建 worker"是被模型当作我们的指纹。

### 4.5 RF feature importance

前 12 重要特征 (gini decrease, see `reports/top10_analysis/plot_feature_importance.png`):
```
jump_north_pct        0.084  ← top1-3 用 JUMP_NORTH 显著更多
build_worker          0.073  ← top1-3 有 worker, 我们没有
row_100               0.070  ← 100 步时的位置
remove_wall_total     0.068  ← top 队伍主动拆墙
scout_per_minute      0.068  ← 我们最高
energy_100            0.065
north_pct             0.062
build_scout           0.047
south_pct             0.047
miner_per_minute      0.040
transfer_total        0.040
max_factory_energy    0.039
```

`jump_north_pct` 排第一很意外: 之前我们以为 jump 只在 v24 的安全检查里, 但 RF 认为 top1-3 用得显著更频繁。检查数据: top10 mean `jump_north_pct` = 0.31-2.56%, 我们 1.4%——分布上不算异常, 但**最高的两个是 bunterrrrr 2.56% + Andrey 2.38%, 都是 Silent Miner**。所以"jump_north 多"其实是 Silent Miner 的副产物 (他们建 miner 后用 jump 跳到下一矿)。

---

## 5. 第四部分: 反制矩阵 (Top 10 × 我们的 3 个策略选项)

|  | 经济稳进 (复制 Klodt) | 速攻反 timeout (强化 v24 北推) | 模仿 spam (复制 AI TOOK 类) |
|---|---|---|---|
| **#1 bunterrrrr** | 必败 (我们 final energy 2625 vs bunt 6728) | 必败 (他 row_200 32 vs 我们 40 表面我们快但 step 500 时他 energy 6700 我们 263) | 唯一可能平 (AI TOOK 是 3 平模板) |
| **#2 Andrey** | 必败 (同 bunt 系) | 必败 | 可能平 (跟 AI TOOK 类似策略) |
| **#3 Takahiro** | 反 timeout 可能 (他 boundary_scroll 4 次) | 推荐 (利用他 SOUTH 13%) | 不推荐 (他 scout 7.3 比我们还多) |
| **#4 Hazy** | 必败 (他 peak energy 7099) | 中性 | 不推荐 |
| **#5 Pavel** | 反 timeout 可能 | 推荐 (利用他 first_miner 40 较晚) | 不推荐 |
| **#6 Klodt** | 推荐 (他 row_100 21.5 跟我们持平, 末期 IDLE 47% 弱点) | 推荐 | 中性 |
| **#7 Bekker** | 推荐 (他 final energy 3585 我们升到 4000+ 即可反 timeout) | 推荐 (我们 row_200 40 vs 他 36) | 不推荐 |
| **#8 AI TOOK** | 推荐 (他 final energy 2218 比我们都低) | **强推** (他 row_200 35 vs 我们 40) | 不推荐 (镜像策略劣势) |
| **#9 ZERO HQR** | **强推** (他 final 2983 vs 我们 2625; 升 worker 即可超过) | 推荐 | 不推荐 |
| **#10 Joseph** | 推荐 (他 boundary_scroll 7 次, 我们若不死可以 timeout 赢) | 推荐 | 不推荐 |

**汇总**: 9/10 行至少有一个"推荐"格——意味着只要我们做出"经济稳进 + 北推 + 不死"的组合, 至少能在 top 6-10 拿到 50% 胜率。Top 1-3 我们短期内打不动, 战略重心是 "经济升级 + 不被 spam 队平"。

---

## 6. 第五部分: 数据驱动 actionable 建议 (按 ROI 排序)

每条标 effort (S/M/L), 估计 ELO impact (基于跟该团体的胜率差异)。

| # | 建议 | Effort | ELO 估计 | 证据 |
|---|---|---|---|---|
| **1** | **加入 BUILD_WORKER 分支** (当 step ≥ 300 & factory_gap ≥ 8 & factory_energy ≥ 500 & 无 idle scout 需求时, build 1 worker 朝北方支援) | S (~50 行代码) | +50 ~ +100 | Top10 100% 建 worker (0.64-5.12), 我们 0; 决策树直接把 build_worker ≤ 0.5 当作 us 的指纹 |
| **2** | **降低"无 miner episode"比例 from 38% to ≤10%** (放宽 v15 的"only 北方且 visible"条件, 允许 step 30-150 内对所有可见 mining_node 至少试一次 BUILD_MINER) | M (~80 行) | +30 ~ +60 | 我们 17/44 episode 完全 0 miner; top10 仅 4-12% 0-miner |
| **3** | **末期 boundary_scroll 防御** (step ≥ 400 & gap ≤ 10 时强制 NORTH/JUMP_NORTH, 禁用 BUILD_SCOUT/REMOVE/BUILD_MINER) | S | +20 ~ +40 | 我们 v30 sample 里 6 个 boundary_scroll 死, Joseph (#10) 也是 7 个——这是 top10-bracket 共病 |
| **4** | **彻底删除步 32 后的 routine BUILD_SCOUT** (只保留 step ≤ 32 的早期视野 scout, 或者干脆 0 scout 走 Silent Miner) | S (改 v19 的 SCOUT_DELAY_STEP 即可) | +20 ~ +50 | 决策树 "scout_per_minute > 0.29 → us"; bunt + Andrey + ZERO HQR 全 0 scout |
| **5** | **在 v24 的 JUMP_NORTH 安全检查里加 "factory_collision 风险预估 2-turn 内"** | M | +10 ~ +30 | bunt 4 损里 3 个 collision, top10 共病; 我们 v40 已有 2-turn collision predictor 但因为 public score 968 没保留——可以单独提取这模块复活 |
| **6** | **早期 scout 不要 6+ 个, 1-2 个就够** (top10 median first_scout 在 30-60 之间, 我们在 step 1-10 就 build 多个 scout 是浪费) | S | +10 ~ +20 | 我们 mean build_scout 6.79, top10 median 范围 0-8 但只有 Takahiro/Bridelance 这种特殊队会到 6+ |
| **7** | **加 transfer 路径**: 当某 mine 被建好且 factory 不能直接踩时, 用 worker/miner TRANSFER_NORTH 把 mine 的 energy 抽给 factory | L (~150 行, 需 mine ownership 跟踪) | +20 ~ +50 | bunt 的 `TRANSFER_NORTH:405` 是他 economy 关键, 我们 v24 transfer_total = 0 |
| **8** | **针对 Klodt/Andrey/Pavel 等"等死流"做 step ≥ 200 的 final-row 冲刺** (检测对手 IDLE 比例 > 50% 时, 我方放弃 BUILD, 全力 NORTH) | M | +10 ~ +30 | Klodt 47% IDLE, Andrey 60% IDLE——他们末期赢 tiebreak 靠 energy 不靠 row, 我们如果 row 拉 5+ 可以反 tiebreak |

**总 ELO 预算**: 1+2+3 单做就有 +100 ~ +200 上升空间, 即从 1129 → 1230+, 进 top 20 几无悬念; 完整 1-7 合做理论上限 +200 ~ +400, 进 top 10 (1338+) 可能性高。

**risk note**: ROI 估计基于 "vs 该 archetype 胜率差异" 的线性外推, 实际 Kaggle ELO 是非线性的——top10 内部争 1 局可能就 +30 ELO, 而 vs 弱队赢 10 局可能就 +5 ELO。所以建议优先打 #5-#10 段。

---

## 7. 附录

### 7.1 分析脚本
- `scripts/top10_build_master_matrix.py` — 把 14 队 + bunterrrrr + 我方 strategy_metrics 合并成 master_episode_matrix.csv (454 行)
- `scripts/top10_analyze.py` — 跑 K-means archetype, RF importance, decision tree, 生成 5 张图
- `scripts/top10_per_team_summary.py` — 每队 vs bunt / vs us 的 gap 表 + failure_mode aggregation

### 7.2 数据输出 (reports/top10_analysis/)
- `master_episode_matrix.csv` — 454 episode 单行特征
- `team_aggregate.csv` — 16 队 aggregate (mean/median 数十个特征)
- `archetype_assignments.csv` — 每队的 K-means archetype
- `archetypes_summary.csv` — 3 个 cluster 中心
- `feature_importance.csv` — RF feature importance ranking
- `decision_tree_rules.txt` — sklearn export_text
- `per_team_gap.csv` — 每队跟 bunt / 跟 us 的 gap
- `per_team_dossier.md` — 11 队的可读 dossier (本文 §3 的源数据)
- `per_team_dossier.json` — 同上 JSON

### 7.3 图表
- `plot_pca_archetypes.png` — Top 1-10 + us 在 PCA 2D 上的分布, archetype 颜色
- `plot_feature_importance.png` — RF top-15 feature importance bar plot
- `plot_energy_trajectory.png` — 11 队的 mean energy 在 step 50/100/200/300/400 的曲线
- `plot_row_trajectory.png` — 同上但 row
- `plot_scout_vs_miner.png` — 散点图 scouts/ep vs miners/ep
- `plot_first_miner.png` — 11 队 first_miner 分布 boxplot

### 7.4 已知偏差 / 数据限制
- 各 top10 队的 25 局 focus sample 是 W3 选的"high-signal" (含 losses, draws, strong opponents, recent), 不是 random sample——会高估失败率;
- 我们 v24 的 44 局来自 replays_v24 + replays_v30 (相同代码), 部分是 validation game (self-play), 会让 first_miner / first_scout 数据偏向"我们打自己";
- bunterrrrr 60 局是 focus 选股, 对 bunterrrrr 同样有 selection bias——但 W:L:D 比例 54:4:2 与真实 161:4:2 非常接近, 说明选股偏差对结果可控;
- failure_mode 字段是脚本自动识别 (factory_collision / boundary_scroll / timeout_tiebreak / single_factory_death), 在 simultaneous_tiebreak 类有 5-10% 错分概率。
