# Maze-Crawler 外部研究 + 第一性原理报告

> 任务: 跳出"启发式补丁"思路，用外部历届 Kaggle 模拟赛、博弈论、生存博弈、计算理论给当前 v37/v30 双槽组合带来"机制级"洞察。
>
> 写作日期: 2026-06-03. 当前在线状态: `v37 publicScore 1142.4 (rank 24/345)` / `v30 985.2` / `v40 sampling`. 公榜第一 `bunterrrrr 2221`. 截止 2026-06-16.

---

## 0. 执行摘要 (10 行内)

1. **历届 Kaggle 模拟赛唯一统计上稳定的赢家形态是"高度模块化的规则 + 替换/微调"**(Halite IV, Lux S2, Kore 2022, maze-crawler 当前 Top10 全是规则)；纯 RL 只在 Lux S1/S3 等"大量训练时间 + 大计算"环境胜出。我们在 14 天窗口里必须坚持规则路线，不要写 RL。
2. **2 个 active slot 应当跑分形"安全 + 高方差"**(Halite IV KhaVo team 的 "stable of agents"；Lux S3 冠军 tonykozlovsky 的 85/15 双模型并发法)。当前 v30 / v37 已经天然处在这个分布上, 但 v30 仍处在 985.2, 应该立刻把弱槽换成 v37 同代码、不同随机化的复制，让对手的 IL 工具混淆。
3. **从 War of Attrition + 死线定理**(Myatt 2024) 来看, **死线越近, 唯一均衡里"被感知为更强"的玩家必赢, 等价于他应该立刻把"剩余实力"全压上**。对我们而言这意味着 step ≥ 350 后**电量、视野、矿数三件中任何一项明显领先, 都应进入"强制对方花 cooldown"模式**, 而不是继续囤积。

---

## 1. 类似 Kaggle 比赛策略提炼

为每条引用同时回答"**对 maze-crawler 的具体动作是什么？**"。

### 1.1 Lux AI Season 3 1st place — Tony Kozlovsky (PPO / IMPALA, MARL)
- 来源: <https://github.com/tonykozlovsky/lux-ai3-pub>
- 通用 pattern: **双模型 85/15 混合提交**。submission 里同时打包"已在 LB 验证的强模型"和"新候选模型", 用 15% 概率随机切换, 让 IL 对手拿到的训练样本既有强模型的赢局又有弱模型的输局, 拷不出干净策略。
- **对 maze-crawler 的具体动作**:
  - 把 `experiments/v37_*/main.py` 与 `experiments/v40_*/main.py` 合成一个 wrapper, episode 内 `random.random() < 0.15` 时调度 v40, 其余调度 v37, **同一个 submission ID 同时充当"安全槽 + 探索槽"**, 我们的 2 个 active slot 实际上能跑 4 套策略。
  - 同时, 因为 `Kaggle` 已经公开 `daily episodes` (我们的 docs/research.md 已经提到 `kaggle/maze-crawler-episodes-index`), bunterrrrr 的 167 条 replay 是公开的, 他自己**没有做这种隐藏**, 所以我们模仿他的 mining-trigger 在低段位非常 OK, 但同样地我们的 v24/v37 风格也已经被对手拷走了; 这就是为什么 v37 在 1100 区间反复震荡。

### 1.2 Lux AI Season 2 1st place — ry_andy_ (纯 Python → C++ 规则)
- 来源: <https://github.com/ryandy/Lux-S2-public>; <https://www.kaggle.com/competitions/lux-ai-season-2/discussion/407982>
- 通用 pattern: 纯规则 + 极致剪枝, 用 `FUTURE_LEN = 5` 这种"前向预测多少回合"参数来 trade-off 时间和强度。
- **对 maze-crawler 的具体动作**:
  - 我们的 `bfs_jump` 当前 depth=20, 只跟踪 jump cooldown, 不跟踪 move cooldown (2 回合)。把 BFS 改成 **time-expanded** (节点 = (c, r, jcd, mcd)), depth 加到 30-40, 直接解决 "v30/v40 在 step 481 选 JUMP_WEST 把跳跃 lock 20 回合" 这种死亡决策 (research.md §v30/v24 Replay Failure Audit 已观测)。这对应 ry_andy 的 "把所有 cooldown 都建到状态空间里, 让 BFS 自己选" 的精神。
- 不直接适用的部分: ry_andy 后期写到 C++ 是为了在 3 秒/turn 内做更深搜索; maze-crawler 每 turn 时限我们没爆过, 不需要 C++。

### 1.3 Lux AI Season 1 1st place — Toad Brigade / Isaiah Pressman (深度 RL)
- 来源: <https://github.com/IsaiahPressman/Kaggle_Lux_AI_2021>; <https://www.kaggle.com/c/lux-ai-2021/discussion/294993>
- 通用 pattern: IMPALA + UPGO + TD(λ) + **frozen teacher KL** (周期性把当前网络当 teacher, 防止 "strategic cycle" - 反复输给已被自己打败过的旧版本)。
- **对 maze-crawler 的具体动作**:
  - 直接做 RL 在 14 天不现实。但 **teacher KL 思想可以直接借鉴**: 我们的 `scripts/evaluate_agents.py` 应该在每次提交前**强制和 v1, v9, v15, v19, v24 五个历史代际打 50 paired seeds**, 任何代际胜率 < 45% 就拒绝, 这能避免 "v37 在 v24 上正, 但在 v15 上输到 33%" 这种 strategic cycle。当前 `research.md` 显示 v17 就是这种问题: 对 v1 正, 对 v9 负。
- 不直接适用的部分: 比赛 1 周后才会出现稳态对手分布, 在线 ELO 已经替我们做了"对手池采样", 我们不需要写自己的 league。

### 1.4 Halite IV 1st place — ttvand (纯规则, Python)
- 来源: <https://github.com/ttvand/Halite>; <https://www.kaggle.com/c/halite/discussion/183543>
- 通用 pattern: 每个 unit 在每一回合**枚举所有可能任务 (mining / defend / attack / shipyard) 并按 expected halite/turn 排序, 用匈牙利 / 贪心做 assignment**; 全局只有一个 priority loop。**关键: 不写"if 紧急情况"**, 让所有逻辑都是同一个 cost function 的输出。
- **对 maze-crawler 的具体动作**:
  - 我们的 main.py 现在是大段 `if obs.factory_gap <= 2: emergency_escape()` 这种硬阈值, 这是 v32/v33 反复被 v24 打回的根因 (硬阈值切换无法平滑过渡)。
  - 应该把 factory action 改成: 列出 9 个候选 (4 walk + 4 jump + idle), 每个候选给一个 expected_value, 选 argmax。expected_value 的输入: (1) `north_progress` (1.0 北上, -0.5 南下), (2) `cooldown_cost` (jump 用 -20, walk 用 -2), (3) `collision_risk` (敌人 1 步内能到 → -10), (4) `mine_landing_bonus` (踩到自己矿 → +5)。这正是 Halite IV winner ttvand 用了 ~2000 行实现的核心循环。

### 1.5 Halite IV 8th, Gold — KhaVo Dan Gilles Robga Tung (规则 + ML 混合)
- 来源: <https://github.com/digitalspecialists/halite4>; <https://www.kaggle.com/c/halite/discussion/183312>
- 通用 pattern: "stable of agents" — 团队故意维护一群**实力梯度的 bot**, 用低段位 bot 占住 ELO 池的低层匹配, 让 IL 对手训练样本被低质数据稀释; 高段位 bot 自己专心刷分。
- **对 maze-crawler 的具体动作**:
  - 我们没有团队, 但**"两个 active slot" 自带这个能力**。当前 v30 + v37 都是"我们最好的两件作品", 这是浪费; 更优配置是 **v37 (强) + 一个故意带"诱饵动作"的 v37 变体** (例: 30% 概率把 BFS 第一选的 JUMP 改成 IDLE), 让对手把我们建成"难以预测"的目标。
  - 公开的 `kaggle/maze-crawler-episodes-index` 已经在被高段位选手用于"分析对手" (我们就在干这件事); 这意味着 LB 1200-1300 的位置, IL/规则模仿是最常见的"上分手段", 我们应该是 **被模仿的人**, 不是模仿的人。

### 1.6 Kore 2022 4th place — qihuazhong (规则, fork from kore-beta-bot)
- 来源: <https://github.com/qihuazhong/kore-2022>; <https://www.kaggle.com/competitions/kore-2022/discussion/340157>
- 通用 pattern: **预先生成所有候选 route, 在每一回合用 LRU cache 选最佳**; 把游戏逻辑全部向量化 (numpy)。
- **对 maze-crawler 的具体动作**:
  - 当前 `bfs_jump` 每 turn 重新跑, 但**地图 wall 信息更新很慢** (大部分回合只新增 1-2 个 cell)。可以把 "(factory_pos, jump_cd, walls_hash) → first_action" cache 起来, 在 fog 没更新时直接复用, 节省 50%+ CPU, 给我们做 depth=40 BFS 留时间。我们的 `_memory` dict 已经在每 turn 被维护, 加这个 cache 是 ≤30 行的事。

### 1.7 Hungry Geese 1st place — DeNA HandyRL (RL + Decoupled UCT)
- 来源: <https://www.kaggle.com/c/hungry-geese/discussion/263279>; <https://github.com/DeNA/HandyRL>
- 通用 pattern: **torus-aware CNN** — 利用棋盘对称性 (循环边界) 让神经网络参数减少, 同时输入做 4 倍 augmentation。
- **对 maze-crawler 的具体动作**:
  - 我们已经在 `MIRROR_WALL` 里用了 E/W 对称, 但**只用于补 fog**, 没用于动作选择。Hungry Geese 的洞察是: 让"对称"参与到每一步的决策本身。具体到我们: BFS 的代价函数应该对 mirror cell 也用同样的代价 (现在我们偏向 EAST/WEST 中的一边, 是 random tie-break), 用 mirror 一致性会让对手更难预测我们走哪一侧。
- 不直接适用的部分: Hungry Geese 是 torus, maze-crawler 上下不循环, 所以"torus padding"不适用; 只有 E/W mirror 适用。

### 1.8 跨 5+ 比赛的共同 1st place pattern 总结

| Pattern | 出现于 | 对 maze-crawler 的可执行翻译 |
|---|---|---|
| **规则 + 全局 cost function, 不要硬 if-else 切换** | Halite IV, Lux S2, Kore 2022 | 把 v32/v33 失败处的硬阈值改写成连续打分 |
| **time-expanded / 包含 cooldown 的 BFS** | Lux S2, RTS 综述 (Time-Dep SP, Yu-LaValle) | `bfs_jump` 加入 move_cd 维度 |
| **frozen teacher / 历史代际防 cycle** | Lux S1, Hungry Geese | 提交前 vs v1/v9/v15/v19/v24/v30 各 50 seed gate |
| **stable of agents / 双模型隐藏** | Halite IV (KhaVo), Lux S3 (Tony) | 把 v37 + 一个诱饵变体作为 2 个 slot |
| **公开 replay 索引 → 一定有人在拷你** | Lux S1/S3, maze-crawler | 假设 v37 已被研究, 主动做出"不可拷贝"的随机化 |

---

## 2. maze-crawler 本身的外部讨论

**核心结论: 几乎没有 Kaggle 之外的外部讨论**。这本身就是 signal — 比赛只跑了 1 个月, Reddit / 知乎 / Medium / 微博都搜不到 high-signal 帖子 (做了中英文搜索: "maze crawler reddit kaggle", "Kaggle 比赛 maze crawler 知乎")。所有有效信号都在 Kaggle discussion 自己的 `docs/discussions/` 里, 我们已经全部下载并读过。

### Kaggle discussion 区已知 high-signal 帖子复核

| Topic | 来源 | 关键事实 (本研究复核后的) |
|---|---|---|
| 702108 [Sharing] Jump-Preferred BFS LB1223 | <https://www.kaggle.com/competitions/maze-crawler/discussion/702108> | **Top players 0 个建 worker/miner、0 个 IDLE turn**。这是 v1 baseline 的诞生, 也是我们 v15+ 已经被 bunterrrrr 替代掉的旧观点。**注意**: 这个帖子的作者 Nicolas Bridelance 自己当时 rank ~5 (~1500), 已经远低于 bunterrrrr 2200; **这意味着公开帖子里的"factory pathfinding speed dominates" 在 1100-1500 区间正确, 但在 1900+ 区间已经被矿经济压制**。 |
| 701583 Competition Updates (Bovard) | <https://www.kaggle.com/competitions/maze-crawler/discussion/701583> | 官方确认: scrollStart=10, scrollEnd=2, ramp=450; **collision tiebreak 不计 factory 自身能量** (lucian kucera 回复), 这解释了为什么我们的 collision_avoid 改用 support unit energy 是对的。 |
| 702770 [SOLVED] Strange tiebreak | <https://www.kaggle.com/competitions/maze-crawler/discussion/702770> | Bovard 亲自回复: 当两个工厂同步死亡(同一 step), 一定是 tie, **支持 unit 数和能量都不计入**。这意味着如果我们故意撞死对方, 哪怕我们 support 强, 也只能拿 tie, 不会赢。**对应动作**: collision avoid 在 support_advantage > 0 时收益是 "tie → 我们多 ELO" 而不是 "win → 大量 ELO", 应该重新校准 v24 的 collision_tiebreak 模型 (现在它假设 support 多 → 撞死也能赢)。 |
| 696486 Possible improvements for opponent allocation | (本地 0 byte, 在线被 Cloudflare 拦截) | 标题就足够: 有人已经在抱怨 ELO 匹配, **这是 v37 在 1100-1200 区间反复震荡的根因之一** — 我们经常被匹配到下面 800-900 的弱对手, 他们的输给我们贡献的 ELO 很少, 但偶尔被这群人"撞死"会扣很多分。 |
| 701822 Daily Episodes Datasets | <https://www.kaggle.com/datasets/kaggle/maze-crawler-episodes-index> | 公开 episode 数据集; **bunterrrrr 风格的对手已经在公开数据里, 公开数据也在反过来训练所有人**, 形成了 imitation race。 |

### "高段位选手没有公开任何写作"

到 2026-06-03, **bunterrrrr (#1, 2221), AI TOOK MY JOB AND YOUR JOB! (#2-#3), ZERO HQR, Takahiro Matsumoto, CurveCowboy 没有一个写了 writeup** (我们已 grep `docs/kernels/kernels_score.csv` 和 `docs/kernels/kernels_vote.csv`)。**唯一公开的 writeup 是 Nicolas Bridelance 的 LB1223 帖子** — 也就是我们 v1 baseline。这意味着 **1200 以上的所有 know-how 都还在私人手里**, 我们对 bunterrrrr 风格的 reverse-engineering 是当前少数 viable 信息源。

---

## 3. 第一性原理推导 (5 个层次)

### 3.1 博弈论层

**(a) 是不是 zero-sum？**

形式上是: 一方输的负分 (例如 -473) 和另一方赢的正分 (例如 +473) 在 reward 上对称, ELO 也是 zero-sum 更新。**但有一个隐藏的非 zero-sum 维度**: tie 状态。`docs/discussions/topic_702770.txt` 确认双方同步死亡 → tie, 双方 ELO 朝均值靠拢。**当我们的 ELO > 对手时, 主动撞死对方制造 tie 对我们是负 EV** (我们丢分, 对方涨分); 反之, 对手 ELO 比我们高时, 他主动撞我们对他是负 EV。**结论**: collision-avoid 策略的开关应该和 "对手 ELO ≷ 我方 ELO" 联动, 这是当前 v24/v37 完全没考虑的维度 (我们没有 observation 里直接给对手 ELO, 但可以从最近几局对手历史推断, 或干脆用 self ELO 近似)。

**(b) 对方撞我们 = 牺牲机动性换 tiebreak**

War of Attrition 的经典分析 (Bishop & Cannings; Bulow & Klemperer 1999): 对方付出 cooldown 成本主动撞我们, 等价于在 "bid b, lose b regardless" 的全付费拍卖里下注; 他只有在 **(他在 tiebreak 上的预期收益 - 他付出的 cooldown 成本) > 0** 才会这么做。我们的 v24 之所以在 78532503 输, 是因为对方 ELO 在我们之上 (他主动撞 → 大概率赢 ELO), **同时我们的 factory 处在 mvcd>1, 他不需要付任何"主动 cooldown"** 就能撞我们 → 这是单边占优。**直接动作**: factory 一旦进入 mvcd>1, 必须在动作选择前先做"对方下一步是否能踩到我"的 1-ply 预测 (v40 的 Knob 1 已经是这件事), 但更优做法是 **3 步前就主动避免让自己进入 mvcd>1 的 1-step distance 内有敌 factory 的局面** (而不是事后修补)。

**(c) "war of attrition with deadline" 的均衡**

Myatt 2024 (<http://dpmyatt.org/uploads/war-of-attrition-2024-may-wp.pdf>) 证明: 有限死线 T 下, war of attrition 有唯一均衡, 且当 T → ∞ 时, 均衡选择的赢家是 "asymptotic hazard-rate dominance" 一方 — 简单讲, **被对方感知为"剩余战斗力分布右尾更厚"那个人, 几乎一定立刻被另一方放弃**。
- **对 maze-crawler 的翻译**: 我们的 "right tail" = factory_energy + miner count + gap_to_south。step ≥ 350 时, **如果我们在所有这三项都低于对方, 我们应该立刻放弃 tiebreak 幻想, 全力 jump north**; 反之如果我们都领先, **我们应该主动消耗 cooldown 在敌方 factory 路径上制造拥堵** (而不是继续囤经济)。当前 v37/v40 都没有这种 "局势对比 → mode 切换" 的逻辑, 它们一直只在做"自己尽量北上", 这在我们落后时是浪费机会窗口。

**(d) 高段位 vs 低段位的过拟合**

我们 v24 是为修补 v19 在某具体 replay (78529554) 输给 Mathieu W 而写的; **这是对个例对手的过拟合**。Hendricks-Weiss-Wilson (1988) 证明 war of attrition 在对手类型不确定时**有连续多重均衡** — 翻译为我们的语言: **没有任何单一策略能同时最优响应所有对手类型**。**v37 之所以对 top2/pilkwang 强但对 v9 平**, 正是因为 v37 是"对常见 LB1100 风格"的最优响应, 不是"对所有对手"的。**结论**: 我们应该接受过拟合, 但应该过拟合到 **当前 1100-1200 ELO 段最常见的对手分布**, 而不是过拟合到具体 ID。

### 3.2 生存理论层 (经济学 ROI + 进化生物学 r/K)

**(a) Miner 的边际 ROI**

- Cost: 300 (build) + 200 (spawn drain, 因为 factory 损失 200) = 500 energy。占 factory 1 turn (idle)。
- Revenue: miner TRANSFORM → mine, factory 站上去每 turn +50 energy, 持续到 factory 移开或被滚动毁掉。
- Break-even: 500 / 50 = **10 turns 站在矿上**。
- bunterrrrr replay 数据 (`reports/bunterrrrr_focus_strategy_metrics.csv` 第 5 行 episode 78389263): 322 step, 2 mines, max factory_energy 6443, final 6348。**他从 step 41 第一个 miner 起到 322 step, 281 turns 中, 平均每 mine 提供了 ~6443/2 ≈ 3200 energy ROI, 远超 break-even 的 500**。
- **我们的 v24/v37 数据 (research.md §Miner Event Notes)**: first miner step 6-159, **几乎所有 miner 是 BUILD_MINER_NORTH 然后立刻被 factory 北上 "经过", 站矿时间 ≤ 3 turns**, 所以单矿 ROI 只有 ~150 energy < cost 500。**这就是为什么 v14 (side mining) 让 reward 飙升但 win rate 反而降**: 我们建对了矿但没站够时间。
- **结论 (可执行)**: 建 miner 的 cost function 应该是 **"接下来 10 turn factory 能在这个 cell 上站几 turn × 50 - 500"**, 不是简单的 "factory_gap > N"。这需要给 BFS 加一个 "factory dwell time on mine" 的虚拟节点。

**(b) r-strategist vs K-strategist**

- r-strategist (公司 baseline v1): 大量便宜 scout, 没有重资产, 死了再生。
- K-strategist (bunterrrrr): 少量重资产 miner, 经济螺旋累积, 一次大押注。
- **生物学最优混合 (Pianka 1970)**: 在 "环境承载力 K 高、资源密度 D 高、死亡率 m 低" 时, K-strategy 占优; 反之 r-strategy 占优。
- **对 maze-crawler 的具体计算**:
  - K (max factory_energy 可达): ≈ 10000 (bunterrrrr 上限观测)
  - D (mining_nodes 密度): 我们的 episode 中地图有 ~10-30 个 mining node 在 100-row 范围内
  - m (factory 死亡率): step ≤ 100 几乎为零, step ≥ 400 急剧上升
- **结论**: **step ≤ 350 应该走 K-strategy** (bunterrrrr 模式: 重投 miner), **step > 350 应该急转 r-strategy** (放弃所有重资产, 全力 jump north)。这正是 research.md §"Late-Game Learning From bunterrrrr" 已经诊断到的, 但 v37 还没完整实现。

**(c) Kelly 在 "active slot 选择" 的应用**

我们有 2 个 active slot, 等价于一个 bankroll W=1 在 N 种策略 (v15, v19, v24, v30, v37, v40 等) 上的分配。Kelly: 最优 fraction f* = (p × b - q) / b, p=胜率, b=赢的倍数, q=输概率。半 Kelly (fractional Kelly) 损失 25% 长期增长率但**减少 80% 方差** (KellyPortfolio docs, <https://thk3421-models.github.io/KellyPortfolio/>)。
- 当前 v30 (1133.4 历史峰值, std ≈ 50) 与 v37 (1142.4 近期, std ≈ 80) 的 Sharpe 大致相当, **但 v37 与 v30 高度相关** (都基于 v24), 这是 Kaggle "two similar submissions" 反模式 (<https://www.kaggle.com/general/414544>)。
- **正确分配 (半 Kelly + 相关性)**: 1 个 slot = v37 (最强单点), 1 个 slot = **行为正交的高方差候选** (例如 v15 的 north-mining 经济流, 或纯 jump-preferred 的 v1, 而不是另一份 v24 复制)。

### 3.3 对手建模 / 社会学层

**(a) ELO 系统 → 我们对手的密度峰**

公榜 snapshot (`data/raw/leaderboard_now2/...csv`): rank 20-30 区间 (1133-1180) 集中了 ~30 个对手, ELO σ ≈ 25。**Kaggle 内部 ε-greedy matchmaking 会让我们 70%+ 的对局发生在 ±100 ELO 内** (Evaluation.txt 第 9 行: "try to pick Submissions with similar ratings")。
- **对应动作**: 我们的本地 paired-seeds eval 应该**只用 1100-1200 区间的对手** (v9, v15, v19, v24, top2, pilkwang), 不要再花时间和 v1 (现在 < 900 ELO) 打 — 那只是在测试"我们能不能虐菜", 对 1130 这条线没增量。当前 research.md 里 v37 评估用了 top2 (50 seeds), 这条没意义, 应该删掉。

**(b) "保持兼容 vs 专杀"**

我们对 pilkwang_structure 胜率持续在 70%+ (v37 vs pilkwang: 29-10-1), 对 top2 是 60%+, 但 **pilkwang 在公榜的 ELO 是多少? 已经不在 top 100**。专杀这两个的策略是浪费 fitness。
- **应该专杀的对手**: 在 1100-1300 集中的、行为模式与我们正交的对手, 即"会主动撞我们 factory 拿 tiebreak 的 1100 段位玩家"。具体名字 (从 v37 在线失败 replay): Mathieu W (ELO ≈ 1300), Or4k2!, Kirito_arkerman, Alexander Smetannikov。**actionable**: 修改 `scripts/fetch_team_public_episodes.py` 把这几位的 public submissions 下载下来, 跑 paired seeds, 专门补这一类失败 pattern。

**(c) Game-theoretic equilibrium between IL bots**

由于 daily-episodes-index 公开, 整个 LB 1000-1500 区间事实上在玩一个 **imitation race**: 每个人都在拷上方 50 名的行为, 形成"贪婪的本地最优"。Lux S3 的研究 (tonykozlovsky writeup) 直接观察到这个动态。
- **结论**: 在这种 imitation race 里, **唯一稳定的赢家是要么不被拷 (做内部随机化), 要么改变 meta** (引入对手没见过的招式)。我们当前模仿 bunterrrrr 是后者 (引入 mining), 这是对的; 但**应该叠加前者** (内部随机化), 因为我们自己也在被 1000-1100 段拷。

### 3.4 计算理论层

**(a) State space + branch factor**

- 地图: 宽 W=16, 高 ~80 = 1280 cells, 每 cell 4 bit wall = 2^5120 个 wall 配置 — 但因 E/W 对称压缩到 2^2560。
- Robots: ≤ ~8 个 unit, 每 unit (type, x, y, energy, owner, cd) = ~10^4 states, ~8 units 全组合 ~10^32。
- 实际有效 state (考虑 fog) ≈ **10^20-10^30**, 这是 AlphaZero scale 的, **不能直接做完整 MCTS**。
- 每 turn 动作空间: factory 9 + 每 unit ~5, 1 factory + 5 units = 9 × 5^5 = **28125**。 1-ply 完全可枚举, **2-ply ≈ 8×10^8, 不可枚举**。
- **结论**: **1-ply 完全前向预测是 tractable 的**, 我们应该做。`scripts/replay_action_regression.py` 已经能跑单步检查; 把它升级为"对每个候选 action 用 `kaggle_environments` 跑 1 step 然后用 cost function 评估" 是 ≤ 200 行代码的工程任务。

**(b) Time-Expanded BFS**

我们当前 `bfs_jump` 状态 = (c, r, jump_cd 是否 ready)。但实际 cost function 还依赖 move_cd (2 turn cooldown after walk), build_cd (10 turn after BUILD_*) — 这些都不在 BFS state 里。
- 标准做法: time-expanded graph (Yu & LaValle 2012, <https://people.csail.mit.edu/jingjin/files/YuLav12WAFR.pdf>): 节点 = (cell, time mod T) 或 (cell, cooldowns), 这是教科书 polynomial-time 算法。
- **对 maze-crawler 的具体动作**: 把 `bfs_jump` 的 state 改为 `(c, r, jcd, mcd)`, depth 加到 30, 节点数从 ~1280×2 = 2560 上升到 ~1280×2×3 = 7680 — 仍然每 turn ≤ 10ms。这一改可能直接解决 research.md §"v30 / v24 Replay Failure Audit" 里的 step-481 致死决策。

**(c) Information theory of observations**

- 每 turn observation: globalRobots (~ 8 × 6 = 48 ints), walls (1280 × 4 bit = 5120 bit), mines (≤ 50 × 6 int) 等。**总 ~1.5KB 原始, 信息熵 ~3000 bit**。
- 但对决策**有用**的位 (经过 ML feature importance 估计, 类比 Lux S3): **factory_pos, opp_factory_pos, gap_to_south, jcd, mcd, energy, 邻近 8 cell walls** — 约 **80 bit**。
- **结论**: 决策有效信息 80 bit, 完全可以塞进任何手工 cost function。**用 ML 模型对这个任务收益极低**, 这也再次确认 14 天窗口不应做 RL。

### 3.5 风险管理层

**(a) v24 历史峰值 1236 但波动 1123-1236**

50-game window std ≈ 35 ELO。这个波动来源 (research.md §"v30 / v24 Replay Failure Audit"): boundary_scroll 6, factory_collision 4, timeout_tiebreak 3, single_factory_death 1. **集中在 boundary_scroll (low energy → 强制 IDLE) 和 factory_collision (mvcd > 1 时被撞)**。
- 这正是 Black Swan 形态: **绝大多数 episode 我们活到 step 500 拿 tiebreak, 但一旦撞上 "step 450 + energy 0 + jump_cd 18" 这种巧合, 必死**。
- **保险措施 (Kelly 风险约束, Busseti et al. 2016)**: 设一个 "energy hard floor" = **factory_energy ≥ scroll_remaining_steps × 1.5** (因为每 turn passive drain ~1, 加上 build/random 损耗); 一旦低于 floor, 强制 BUILD_* 全部关闭, 只允许移动。v11 的"late scout reserve" 是同方向的, 但 threshold 太静态; 应改成动态 floor。

**(b) v40 vs v37: 是真改进还是采样噪声?**

v40 = v37 + 3 个 narrow knobs。research.md 给了 50-seed paired: vs v37 23-22-5 (delta +1), 这个 delta 在 50 game 下 σ ≈ 7, **统计上无意义** (z ≈ 0.14)。在线 publicScore 858 vs v37 的 1142 差距 284, 远超 v40 的 50-game noise; **这意味着 v40 的真实 ELO 可能就是 v37 ± 20**, 当前低分纯采样。
- **结论 (统计学校准)**: 当一个改动的本地 paired delta < 1.5σ 时, **不要提交**, 因为占用 active slot 的成本远大于潜在收益。我们应该在 `scripts/evaluate_agents.py` 里加一个 `--require-z 1.5` 阈值, 否则脚本自己拒绝。

---

## 4. 跨学科整合: 3 条对本项目具体可用的指导原则

### 原则 1: "Cost function over hard branch"  (Halite IV + Lux S2 + Connect-4 综合)

**所有当前以 `if obs.factory_gap <= N` 切换 mode 的代码块, 重构为同一个 cost function 的不同权重**。
- 输入: action ∈ {9 factory actions × 每 unit 5 actions}
- 输出: scalar value = w_north × north_progress + w_econ × expected_mine_dwell × 50 + w_safe × (-collision_prob × tiebreak_advantage) + w_cooldown × (-cd_lock_cost)
- w_* 的初值: 用 100 paired seed 做 random search; 不要用 if-else 在 step/gap 上切换 mode, 而是让 w_* 是 step / gap 的连续函数。
- **预期收益**: 消除 v32/v33/v37 在 boundary 上的"硬阈值跳变"失败, 把当前 1133-1236 区间收紧到 1150-1220。
- **验证**: 已有 `scripts/evaluate_agents.py` 跑 paired seeds; 加 `--params w_north=1.0,w_econ=0.5,...` CLI 后, 用 grid / cma-es 调 5-10 个参数。

### 原则 2: "状态对称压力下做内部随机化"  (Lux S3 + Halite KhaVo + 信息论)

**承认 1000-1500 区间是 imitation race, v37 已被拷, 唯一脱颖而出的方式是制造"对手无法稳定预测"的行为**。
- 具体: 在每一步, factory action 的 top-2 候选若 cost 差距 < 10%, 用 30% 概率选 top-2 (而非 top-1)。这给对手的 IL 模型加 30% 标签噪声, 不影响我们自己的平均胜率 (top-2 cost 差 < 10% 时, 平均损失 < 5%, 但赢的 unpredictability 价值大得多)。
- **预期收益**: ELO 不见得立刻涨, 但**方差降低**, 因为对手的"事先建模"对我们效果下降。
- **验证**: 用 `scripts/replay_action_regression.py` 检查 30% 随机化下旧 replay 的最终结果分布; 用 50 paired seeds 确认平均胜率没掉。

### 原则 3: "Phase-aware K → r 切换 + energy hard floor"  (生物学 r/K + Kelly 风险约束)

step ≤ 350: K-mode (允许 BUILD_MINER, 接受 1 turn idle), step > 350: r-mode (禁建, jump north), **任意 step: 若 factory_energy < max(scroll_remaining × 1.5, 500) 则 emergency-only**。
- 当前 v37 的 `factory_gap > 4` (build) / `factory_gap > 8` (jump) 是同方向但参数选错; 应该用 step + energy 双门控, 而不是单纯 gap。
- **预期收益**: 直接消除 research.md 里 14 局损失中 6 局的 boundary_scroll 类 + 1 局 single_factory_death = ~50% loss reduction, 折算 ELO ~ +30 → 估计可达 1180-1200, 在 top 20 内稳定。
- **验证**: 已有 `scripts/analyze_replay_failures.py` 自动分类失败; 改完后跑 50 episode 自比 v37, 看 boundary_scroll 占比是否从 43% (6/14) 降到 20% 以下。

---

## 5. 数据 / 工具支持: 哪些洞察可以用现有脚本直接验证

| 洞察 | 现有脚本 | 需要的修改 |
|---|---|---|
| **原则 1 (cost function 替代 if)** | `scripts/evaluate_agents.py` | 加 `--params k=v` CLI, 让 cost function 权重作为外部输入 |
| **原则 2 (内部随机化)** | `scripts/replay_action_regression.py` | 加 `--randomize-top2-prob 0.3` flag, 比较老 replay 的结果分布 |
| **原则 3 (phase + floor)** | `scripts/analyze_replay_failures.py` | 已经能跑, 只要确认改动后 boundary_scroll 占比下降即可 |
| **专杀近 ELO 对手 (3.3 b)** | `scripts/fetch_team_public_episodes.py` | 加 `--team-ids "Mathieu W,Or4k2!,..."` 批量下载 |
| **统计显著性 gate (5 b)** | `scripts/evaluate_agents.py` | 加 `--require-z 1.5`, 计算 Wilson interval 后再 print verdict |
| **time-expanded BFS (3.4 b)** | `main.py` 自身 | `bfs_jump` 加 `mcd` 维度, ≤ 30 行 diff |
| **build_miner ROI cost function (3.2 a)** | `main.py` 自身 | 新增 `expected_dwell_turns(cell)` 助函数, 替换 `factory_gap > 4` |
| **mine ROI 数据回归 (3.2 a)** | `scripts/analyze_miner_events.py` | 加 "miner build → 后续 factory dwell turns" 列, 验证 break-even |

---

## 6. 风险与未解之谜

1. **未解之谜 A — bunterrrrr 的 step 350+ "强制北上模式" 触发条件**
   - 我们看到他在 step 400 之后从 mining 切回纯 jump 序列, 但触发判据未知。**实验候选**: 用 `scripts/analyze_strategy_metrics.py` 计算他每个 replay 的 `mode_switch_step` (定义: 之后再无 BUILD_MINER 动作的最早 step), 看是否与 `gap_to_south`, `factory_energy`, `scroll_speed` 有强相关。

2. **未解之谜 B — collision tiebreak 的精确规则**
   - 官方说"同 step 双死 = tie", 但**异步死亡** (我先死他下回合死) 的规则没明说, 也没人在 discussion 里验证过。**实验候选**: 写一个最小 reproduction agent, 故意制造各种死法 (撞墙, 撞 factory, 出南界), 用 self-play 测每种死法的 reward 输出。20 行 Python + 10 个 seed, 1 小时内可做。

3. **风险 A — `kaggle-environments` 版本漂移**
   - research.md 已经记录 1.29.3+ 把 `scrollStartInterval=10`, 但 v37 提交时间是 6-2, Kaggle 可能再次微调。**对策**: 每次提交前跑 `pip show kaggle-environments` 并记入 submission log。

4. **风险 B — 比赛截止后还会跑 2 周**
   - 最终 ELO 是截止后 2 周稳态。意味着 6-16 之后我们无法再改, **现在的"最强 submission"必须能在 2 周内稳定**。fractional Kelly 的"低方差"在这里特别重要, 不要在最后 3 天上 v40 这种 5-knob 大改; 改用窄改动 + 多次本地验证。

5. **风险 C — 主页发了什么我们没看见**
   - Kaggle 网页搜索接口反复返回 Cloudflare 拦截 (尝试 fetch 696486 和 maze-crawler 主 discussion 时), 意味着**可能错过新发的 discussion 帖子**。**对策**: 每天用 `kaggle competitions discussions maze-crawler` (CLI, 不走 web) 拉一次 topic 列表, 看 commentCount 变化。

---

## 7. 最 actionable 的 3 条原则 (给协调者)

1. **立刻把 v30 active slot 换成"v37 + 30% top-2 random 化变体"** — 即原则 1+2 的最小可执行组合。0 新参数, 只修改 `main.py` 末尾的 action 选择处, ≤ 20 行 diff。预期: 不输 ELO 给采样, 但对手 IL 难以稳拷我们。
2. **把 `bfs_jump` 改成 (c, r, jcd, mcd) 4 维 time-expanded BFS** — 直接消除 research.md §"v30 Replay Failure Audit" 里 step 481 那种 "选 lateral jump 锁 20 turn cooldown 然后死掉" 的致死决策。预计单独贡献 +20-30 ELO。
3. **加 energy hard floor**: `factory_energy < max((500 - step) × 1.5, 500)` 时立刻关闭所有 BUILD_*, 只允许移动 — 这是原则 3 的 simplest 实例, ≤ 10 行 diff, 直接砍掉 6/14 的 boundary_scroll 损失。

## 8. "理论上应该但实际还没做"的实验候选

**Experiment X: 1-ply forward predicted cost function (基于原则 1)**

具体: 在 main.py 的 factory action 选择处, 对每个候选 action 用一份"轻量级 game-state simulator" 推 1 turn, 计算 5 个 cost 项 (north_progress, mine_dwell, collision_prob, cooldown_lock_cost, energy_change), 再用 cost 加权和选 argmax; 5 个权重用 `scripts/evaluate_agents.py` 调 100 paired seed 的 random search 找最优。

为什么是它:
- 在第 3.4 节我们论证过 1-ply 完全 tractable (28125 actions);
- 在第 4 节原则 1 我们论证过这是所有 Halite IV + Lux S2 winner 的共同 pattern;
- 在第 1.8 节我们论证过 maze-crawler 当前 1100-1500 区间几乎所有 agent 都还在 if-else, 没人做完整 cost function (除了 pilkwang_structure 的简化版, 它在 LB 1000 区间);
- 我们已经有所有需要的脚本基础 (paired eval + failure analysis + replay regression)。

为什么还没做: research.md 显示我们一直在做 "v24 + 1 narrow knob" 的微调, 没人花 1 整天做架构重写。这条实验估计需要 2 天 + 50 paired seed 调权重, 风险大, 但若成功直接把 1133 推到 1300+。

## 9. 引用

外部资料 (URL 完整, 方便复核):

- Lux S3 1st: <https://github.com/tonykozlovsky/lux-ai3-pub>
- Lux S2 1st (ryandy): <https://github.com/ryandy/Lux-S2-public>, <https://www.kaggle.com/competitions/lux-ai-season-2/discussion/407982>
- Lux S1 1st (Toad Brigade): <https://github.com/IsaiahPressman/Kaggle_Lux_AI_2021>, <https://www.kaggle.com/c/lux-ai-2021/discussion/294993>
- Halite IV 1st (ttvand): <https://github.com/ttvand/Halite>, <https://www.kaggle.com/c/halite/discussion/183543>
- Halite IV 8th (KhaVo team): <https://github.com/digitalspecialists/halite4>, <https://www.kaggle.com/c/halite/discussion/183312>
- Kore 2022 4th: <https://github.com/qihuazhong/kore-2022>, <https://www.kaggle.com/competitions/kore-2022/discussion/340157>
- Hungry Geese 1st: <https://www.kaggle.com/c/hungry-geese/discussion/263279>, <https://github.com/DeNA/HandyRL>
- War of Attrition with deadline (Myatt 2024): <http://dpmyatt.org/uploads/war-of-attrition-2024-may-wp.pdf>
- War of Attrition (Hendricks-Weiss-Wilson 1988): <https://ideas.repec.org/a/ier/iecrev/v29y1988i4p663-80.html>
- Generalized War of Attrition (Bulow-Klemperer 1999): <https://www.edegan.com/pdfs/Bulow%20Klemperer%20(1999)%20-%20The%20Generalized%20War%20of%20Attrition.pdf>
- Pursuit-evasion robust real-time (R2PS): <https://arxiv.org/html/2511.17367v2>
- Pursuit-evasion 1-sided POMDP DP: <https://ar5iv.labs.arxiv.org/html/1606.06271>
- Time-expanded multi-agent path planning (Yu-LaValle 2012): <https://people.csail.mit.edu/jingjin/files/YuLav12WAFR.pdf>
- Time-dep SP with waiting limits: <https://optimization-online.org/wp-content/uploads/2019/02/7083.pdf>
- OpenAI Hide and Seek emergent strategies: <https://openai.com/index/emergent-tool-use/>, paper <https://huggingface.co/papers/1909.07528>
- Kelly criterion / fractional Kelly: <https://thk3421-models.github.io/KellyPortfolio/>, <https://matthewdowney.github.io/uncertainty-kelly-criterion-optimal-bet-size.html>
- Optimal sports betting review: <https://ar5iv.labs.arxiv.org/html/2107.08827>
- Kaggle "two similar submissions" advice: <https://www.kaggle.com/general/414544>
- Kaggle shake-up handbook: <https://medium.com/global-maksimum-data-information-technologies/kaggle-handbook-fundamentals-to-survive-a-kaggle-shake-up-3dec0c085bc8>
- Maze-crawler discussions (Kaggle): topics 696486, 701583, 701822, 702108, 702770 (本地 `docs/discussions/`)
- Wikipedia War of Attrition (背景): <https://en.wikipedia.org/wiki/War_of_attrition_(game)>
