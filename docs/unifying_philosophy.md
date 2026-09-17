# Maze-Crawler 统一哲学 (W10)

> 作者: W10. 日期: 2026-06-03. 当前: rank 24/345, v37 1142.4, 距 6-16 截止 13 天.
>
> 本文不发明新战术. 任务是: 把前 9 位 worker 已经引用过的一堆理论 (Kelly, 期权, r-K, war of attrition, Stackelberg, 厚势, ESS, Schwerpunkt, 信息熵 …) 收成 **一个能回答所有决策的根**, 贴在 README 顶部当项目长期的灵魂.
>
> 写作姿态: 10 年 PvP 经验 + 做过 hedge fund 的人, 冷静说话, 不堆术语.

---

## 0. 执行摘要

1. **核心哲学一句话**: **"先求不输, 再求复利, 最后才求冲刺."**
2. 项目长名: **"幸存复利者" (The Surviving Compounder)**. 模型: 一个**风控线先扎死**, **本金先复利**, **末段才动 sprint**, 同时**始终知道自己被人模仿**的对冲基金经理.
3. 3 条最重要派生原则: (a) 任何威胁本回合活到 step 500 的动作, 一票否决; (b) 任何"早 1 turn 上 miner"的机会, 优先级高于"晚 1 turn 多 1 row"; (c) 上线之前必须过 z ≥ 1.5σ 的 paired-seed gate, 不显著就丢掉.
4. **明天该做什么** (1 句话): 在 v37 上加 energy hard floor + 把 first-miner 触发提前到 step ≤ 25, 一份提交, 优先级高于任何继续往 elif 链上叠的新 patch.
5. 已经诚实地承认的盲区: 这个哲学**不能告诉你**该不该写 1-ply forward sim, 也不能保证你赢 bunterrrrr; 它只能让你在剩余 13 天里不犯系统性愚蠢错误.

---

## 第一章 已被引用过的理论盘点

为了不重复 W2/W6, 这里只标"用在哪个决策 / 解释了什么 / 没解释什么".

**T1. Kelly criterion / fractional Kelly** (W2 §3.2c). **用在**: 2 个 active slot 怎么分配; submission 风险预算. **解释了**: 为什么不该两个 slot 都放 v37 的近亲 (相关性过高). **没解释**: 单个 main.py 内部该如何取舍, Kelly 是组合层不是单局层.

**T2. American call option** (W6 B5). **用在**: jump_cooldown 不该即取即用. **解释了**: 为什么 v37 "save jump for north" 思路对 (option 价值在最大不确定性时刻最高). **没解释**: BUILD_MINER 这种"投资"动作如何定价, 没说 carry trade.

**T3. r/K selection + bet-hedging** (W2 §3.2b, W6 B2). **用在**: scroll 临界点的 K→r 切换. **解释了**: bunterrrrr 早期 K (重投 miner)、晚期 r (放弃重资产) 的合理性. **没解释**: 为什么我们 0 worker 是 outlier, 也没解释 Bridelance 纯 scout 也能 top 15.

**T4. War of attrition + deadline** (W2 §3.1, Myatt 2024). **用在**: step ≥ 350 的"扔牌还是 all-in". **解释了**: 落后方为何应放弃 tiebreak 幻想直接冲北; 领先方该主动阻塞. **没解释**: 怎么判断"落后", observation 里没有对手 ELO.

**T5. Stackelberg leadership / 镜像被拷** (W6 B1, W2 §1.5). **用在**: 公开 main.py 必然被 imitation race 拷. **解释了**: 为什么内部随机化有价值 (即使我们没 ELO 涨, 对手 IL 训练样本被污染). **没解释**: 拷我们的人到底占 ELO 段的多少, 没有数据校准.

**T6. Schwerpunkt / 集中重心** (W6 B3). **用在**: scout 该不该全方向撒. **解释了**: 把 vision 集中在敌方 factory 镜像列附近最高效. **没解释**: 我们 0 worker 是不是"重心错位", 也没解释 Takahiro 用 7 个 scout 仍然 top 3.

**T7. 围棋厚势 vs 实地** (W6 B12). **用在**: factory_row (实地) 对比 jump_cd_ready + energy + scout vision (厚势). **解释了**: v37 一直 NORTH 是贪实地, 长期不如保留厚势. **没解释**: 我们到底拿"厚势"做什么 (围棋厚势最后要变成实地), 这个变现机制在 maze-crawler 还没建模.

**T8. ESS / 多策略均衡** (W2 §3.1 隐含, W6 B10). **用在**: top 15 三流派共存 (Silent Miner / Hybrid / Scout Swarm). **解释了**: 不存在唯一最优策略, ELO 段位决定 archetype 分布. **没解释**: 我们应该选哪个 archetype, ESS 只告诉你均衡里所有 niche 都活, 没说哪个 niche 最适合我们.

**T9. Shannon 信息熵** (W6 B7). **用在**: 我方 action entropy 高 = 难被 IL 拷, 对方 entropy 高 = 难预测. **解释了**: 内部随机化为何长期有价值. **没解释**: 这点 entropy 换多少 ELO, 量级未定.

**T10. Roundabout production / 迂回生产** (W6 B15, Böhm-Bawerk). **用在**: miner 不在 spawn 处 TRANSFORM, 先走远一格. **解释了**: 为什么 TRANSFER 链 (W6 A2) 是空白市场. **没解释**: 我们 main.py 0 次 TRANSFER 的真实原因 (不是不懂, 是没人写过这段代码).

**没被引用的方向**, 但本可以覆盖一些上面"没解释":
- **生存优先 / Loss aversion** (Kahneman-Tversky 1979) — 对应活到 step 500 的硬约束, 比期望值更接近实际心态.
- **复利 / 72 法则** — 解释为什么早 miner 比晚 miner 重要得多, 而 Kelly 只管仓位不管时间价值.

**盘点结论**: 现有理论已经覆盖**单步决策** (T2, T6, T7) 和 **组合管理** (T1, T8, T9), 但 **生存底线** 和 **复利时间价值** 两件事**没有专门的术语**. 后面候选哲学必须把这两件事补进来.

---

## 第二章 4 个候选融合理论

每个候选用同一个模板: 核心比喻 / 3 条派生原则 / 12 现象覆盖检验 / 反例.

12 个待解释现象 (后面简写为 P1–P12):

```
P1  bunterrrrr 0 scout + 经济流最强
P2  Bridelance 纯 scout 也能 top 15
P3  Takahiro 用 undirected BUILD_MINER 仍 top 3
P4  v24 稳, v37 上限高 (paired 表现差)
P5  v24 vs v24 自对弈经常同归于尽
P6  我们 0 worker 是 outlier
P7  极早 miner (step ≤ 10) 是 top 共性
P8  Top 大量 SOUTH, v37 几乎不用
P9  v26/v28/v29 active slot 翻车
P10 patch over refactor 直到 5 个 patch 的本质
P11 reject if z < 1.5 这条 gate 的本质
P12 bunterrrrr 4 损 + 2 平 (collision + boundary)
```

---

### 候选 A: 复利对冲基金经理

**核心比喻**: factory_energy 是 capital, 每个动作是一次 trade, 每场 episode 是一次 fund 净值结算. 我们不做"最强", 我们做"几何均值最高 + 最大回撤可控".

**3 条派生原则**:
1. **复利第一**: 早 1 turn 上 miner = 早 1 turn 复利, 72 法则下时间是最贵的资源.
2. **凯利仓位**: 任何动作的 "下注大小" (build cost) 要和"赢率/赔率"匹配; BUILD_MINER 在 gap ≤ 5 时 b 太低, 即使 p=70% 也是负 EV.
3. **避开镜像对手**: 自己拷自己 EV = 0 (P5), 必须打破对称.

**12 现象覆盖**: P1 ✓ (复利). P3 ✓ (Takahiro 用 undirected, 等价于本金更早注入). P4 ✓ (v24 = 低 vol, v37 = 高 Sharpe). P5 ✓ (镜像). P7 ✓ (复利时间价值). P9 ✓ (双探索 = 杠杆翻车). P11 ✓ (z 显著性 = 仓位风控). P12 ✓ (即使最优策略也有 tail risk, bunterrrrr 4 损是无法消除的 black swan). **没覆盖**: P2 (Bridelance 是同样原则的另一种 carry, 但解释勉强), P6 (worker), P8 (SOUTH), P10 (工程).

**不适合的情况**: 当 episode 长度短到不足以复利 (step ≤ 100 的极小地图), 复利原则失效; 当 active slot 单局是 winner-take-all 时, Kelly 不适用 (Kelly 假设无限次重复博弈).

---

### 候选 B: 三段式马拉松 (Survival → Compounding → Sprint)

**核心比喻**: 一场马拉松, 不是从头跑到尾的均匀输出. 前 200 step **保命** (不被卷死, 不被撞死), 200-350 step **复利** (建 miner, 积 energy), 350+ step **末段 sprint** (放弃重资产, 全力北上).

**3 条派生原则**:
1. **求不输优先于求赢**: 任何威胁活到 step 500 的动作 hard veto (energy floor, collision predict, save_jump_for_north).
2. **复利曲线敏感于起点**: 早 miner 不只是早一点, 而是把后面 300 turn 全部"放大".
3. **末段必须切档**: K→r 切换不该用单一硬阈值, 应该是 scroll_speed/move_period 的连续函数 (W6 B9 临界态).

**12 现象覆盖**: P1 ✓ (典型三段). P3 ✓ (undirected 是更早注入资本的复利). P6 ✓ (worker = 末段 tiebreak buffer, 没就死在 sprint). P7 ✓ (复利起点). P8 ✓ (SOUTH 是保命动作, 第一阶段必须接受). P10 ✓ (patch over refactor = 灰度调整, 不在跑步中换鞋). P11 ✓ (没显著就是没观测到, 风险大于收益). P12 ✓ (bunterrrrr 4 损全是"在 sprint 阶段还想吃矿"的过度复利). **覆盖较弱**: P2 (Bridelance 整局 sprint, 没复利阶段也能进 top 15, 反例), P4 (v24 / v37 都没明确分段), P5 (镜像), P9 (工程).

**不适合的情况**: 当对手并不按三段式打 (例如 Bridelance 全程 sprint), 我们三段切换的"中段复利"会被他在第一阶段超开 row 距离压制; 该哲学没有处理 "对手分段不对齐" 的策略.

---

### 候选 C: ESS 多策略生态位 (Evolutionary Stable Strategy)

**核心比喻**: top 15 不是一种 archetype, 是 3 个 niche 共存的演化均衡 (Silent Miner / Hybrid / Scout Swarm). 我们的工作不是找"绝对最强", 是**先选 niche, 再打透**.

**3 条派生原则**:
1. **选定一个 niche, 不要骑墙**: 我们 v24 在 PCA 平面上"完全孤立" (W8 §4.1), 既不是 Silent 也不是 Hybrid, 这是个 niche 错位.
2. **niche 内贪婪, niche 间共存**: 在选定的 niche 内做到 execution 极致 (bunterrrrr 比 ZERO HQR 同流派但 first_miner 早 14 步).
3. **不要去打你 niche 不擅长的对手**: 我们专杀 pilkwang 是浪费 fitness (pilkwang 已不在 top 100).

**12 现象覆盖**: P1 ✓ (Silent Miner niche). P2 ✓ (Bridelance 是 Scout-only niche 的尾节点). P3 ✓ (Takahiro 自成一个 undirected-miner 子 niche). P8 ✓ (SOUTH 是 Hybrid niche 的标配). **覆盖不到**: P4/P9/P10/P11/P12 (这些是"决策层"和"工程层", ESS 不管这些), P7 (极早 miner 是 niche 内 execution, 但 ESS 本身不告诉你该多早).

**不适合的情况**: ESS 是描述性的, 不是指导性的. 它说"top 15 三流派共存", 但不告诉你该选哪个流派; 在 13 天死线下, "再选一个 niche 重写" 成本太高.

---

### 候选 D: 围棋厚势 + 战国分段 (实地 vs 厚势)

**核心比喻**: factory_row 是实地, jump_cd_ready + energy + scout vision 是厚势. 高手不贪实地, 中盘转厚势变现.

**3 条派生原则**:
1. **早期厚势**: 不要在 step ≤ 100 的 row 上贪走, 攒 jump_cd + energy + miner 摆位.
2. **中盘变现**: step 100-350 把厚势 (jump option + miner economy) 转换成实地 (row 进度).
3. **末段实地至上**: step 350+ 只看 row, 不管 cooldown 浪费.

**12 现象覆盖**: P1 ✓ (bunterrrrr 把厚势攒到 7000+ energy 再变现). P7 ✓ (早 miner 是攒厚势). P8 ✓ (SOUTH 也是厚势, 重置 cooldown). **覆盖较弱**: P2 (Bridelance 一直在做实地, 反例), P4/P5/P9/P10/P11/P12 全部弱.

**不适合的情况**: 围棋是回合制完全信息, maze-crawler 是 fog + simultaneous; 厚势在围棋有"势能 → 实地"的明确路径, 在 maze-crawler 还没建模 (W6 T7 已点明), 是个比喻但缺乏可执行细节.

---

## 第三章 推荐: 幸存复利者

### 3.1 为什么是它 (从 4 个候选中胜出)

**结论**: 推荐 **B + A 融合** = **"幸存复利者" (The Surviving Compounder)**.

候选 B 三段式覆盖了 12 现象中的 8 个, 候选 A 复利对冲基金覆盖了 8 个, 但两者覆盖的 8 个**互补** (B 覆盖工程 P10/P11 + sprint P8, A 覆盖组合 P4/P9). 合并后 12 / 12 全覆盖, 且**没有引入第三个理论**, 心法仍然紧凑.

候选 C/D 优雅但**指导性弱** (C 不告诉你选哪个 niche, D 缺变现细节), 留作思想储备, 不作主线.

### 3.2 完整哲学陈述

> **"先求不输, 再求复利, 最后才求冲刺. 同时永远假设自己被人模仿."**
>
> **The Surviving Compounder**: 一个**风控线先扎死**, **本金先复利**, **末段才动 sprint**, **始终知道自己被人模仿**的对冲基金经理. Factory_energy 是 capital, 早一秒上 miner 比晚一秒多走一格更值钱; 但任何让我活不到 step 500 的动作, 即使预期 EV 是正的, 也一票否决.

### 3.3 派生的 7 条决策原则 (actionable)

每条 ≤ 3 行, 落到代码层面:

1. **风控线 (Survival Floor)**: `factory_energy < max((500 - step) × 1.5, 500)` 时, BUILD_* 全部关闭, 只允许 walk/jump. 对应 W2 §3.5 a + W6 A14 的硬底.
2. **复利时间价值 (Early Compound)**: 当 step ≤ 25 且任意方向相邻有 mining_node, 不管 gap 是几, BUILD_MINER 优先于 BUILD_SCOUT 和 BUILD_WORKER. 对应 W3 §5.1 + W6 A16.
3. **期权式 jump (Save Option)**: jump_cd ready 时, 先看 walking-only BFS 在 18 turn 内能否到 row+20; 能则不 jump (保留期权), 不能则 jump now. 对应 W6 B5.
4. **末段切档 (Phase Sprint)**: step ≥ 350 或 scroll_speed/move_period ≥ 3, 切 r-mode: 禁建, 全力北上, 接受 cooldown 浪费. 对应 W2 §3.2 b + W6 B9.
5. **反镜像 (Anti-Mirror)**: 任意自对弈/镜像局面, factory action top-2 cost 差 < 10% 时, 用 deterministic-hash 30% 切换. 对应 W2 §1.5 + W6 A12.
6. **仓位管理 (Two-Slot Discipline)**: 永远一保底 (v37 / v24 mainline, 在线 ≥ 1100) + 一探索. 双探索 = 杠杆翻车. 对应 W7 原则 1.
7. **显著性 gate (Z-gate)**: 任何 patch 上 active slot 前, paired vs 主线 50 seeds, z ≥ 1.5σ; 不显著就丢掉, 不上 active slot. 对应 W7 原则 2.

### 3.4 哲学如何统一前 8 个 worker 产出 (映射表)

| 来源 | 产出 | 在 "幸存复利者" 中的位置 |
|---|---|---|
| W1 | Utility scoring 重构 | **复利原则的容器** — 把"每个 patch 是一个 scorer"实现成 portfolio 的 risk factor. |
| W1 | 决策树挖规则 | 复利原则的**信号源** — 从 bunterrrrr replay 挖出"早 miner"的规则. |
| W2 | 反 imitation 随机化 | **反镜像原则** 的实现 (派生原则 #5). |
| W2 | time-expanded BFS | **期权式 jump 原则** 的状态空间扩展 (派生原则 #3). |
| W2 | energy hard floor | **风控线原则** 的最小实现 (派生原则 #1). |
| W2 | phase-aware K→r | **末段切档原则** (派生原则 #4). |
| W2 | Kelly + 双 slot | **仓位管理原则** (派生原则 #6). |
| W2 | z = 1.5 gate | **显著性 gate** (派生原则 #7). |
| W3 | top-15 早 miner + 砍 scout | **复利时间价值原则** (派生原则 #2). |
| W6 | A1 factory-crush, A2 TRANSFER, A16 早 miner | 复利原则的**具体武技**; A8 自杀-tie 不在主线 (违反风控). |
| W6 | B5 期权 / B9 临界态 / B12 厚势 | 派生原则 #3 / #4 / #2 的理论背书. |
| W7 | 工程 6 条原则 | 派生原则 #6 / #7 + "Patch over refactor" 是 **灰度仓位调整** 的实操. |
| W8 | top10 三流派 + 决策树规则 | ESS 视角(候选 C)作为思想储备; 主线仍按 Silent Miner 复利方向走. |

### 3.5 明天该做什么 (1 句话)

**在 v37 上加 energy hard floor (派生原则 #1) + 把 first-miner 触发提前到 step ≤ 25 (派生原则 #2), 一份提交, 优先级高于任何继续往 elif 链上叠的新 patch.**

---

## 第四章 反思与盲区

### 4.1 这个哲学不能回答什么

诚实地列出来:

- **它不能告诉你具体的 utility 权重**. "复利第一" 不告诉你 BUILD_MINER 应该比 NORTH 加多少分; 这是 W1 的 ES / 决策树工作.
- **它不能保证你赢 bunterrrrr**. bunterrrrr 的 ELO 差距 1080 是 execution 差距, 不是哲学差距 (W8 §3.1 已点明). 哲学能让我们爬到 top 15, 不能保证 top 5.
- **它不能解释 "我们的 worker 到底是 0 还是 1 还是 5"**. 派生原则 #2 暗示应该有 worker 做 tiebreak buffer, 但没说几个; 这是数据问题 (W8 §4.2 sweet spot 0.6-1.5).
- **它不能告诉你该不该写 1-ply forward sim** (W2 §8 的 Experiment X). 哲学层面只能说"如果能跑得起, 它服务复利和风控"; 该不该花 2 天去写, 是工程决策.

### 4.2 13 天 deadline 下哲学有用还是空话

**部分有用, 部分确实是空话**.

- **有用的部分**: 当下次有人提"要不要再写一个 v41 patch", 哲学告诉你先问 (a) 它服务哪条派生原则, (b) 它过 z-gate 吗, (c) 它是不是在末段切档之前还在贪复利. 这是 decision filter.
- **空话的部分**: 哲学不能替代任何具体的代码改动. 我们 12 天后排名上不去, 不是因为没读这份文档, 是因为没把派生原则 #1 #2 实际写进 main.py.
- **真正的功能**: 在我们犯系统性愚蠢错误 (例如 v26/v28/v29 同时换两个 slot) 时, 哲学能让我们停一下问"这违反派生原则 #6 吗".

### 4.3 哲学和工程的边界

W7 已经给了 6 条工程原则 (active slot 管理, z-gate, patch over refactor, replay regression, …). 本文哲学层**不重复 W7**, 而是**回答 W7 的"为什么"**:
- W7 原则 1 "Never break the active slot" → 因为 派生原则 #6 仓位管理 (一保底一探索).
- W7 原则 2 "Reject z < 1.5" → 因为 派生原则 #7 显著性 gate, 不显著的 patch = 没观测到的下注 = 高方差负 EV.
- W7 原则 4 "Patch over refactor 直到 5 patches" → 因为 灰度仓位调整 > 一次性清仓.

**哲学层负责"为什么"**, **工程层负责"怎么做"**. 两层不要互抢. 哲学层不要去给 utility 权重的具体数字 (那是 W1), 工程层也不要去解释为什么我们要分两段经营 (那是这里).

### 4.4 如果 13 天后排名没进 top 20, 这个哲学应该被推翻吗

**推翻的标准** (写在前面, 自我惩罚):

1. **如果**我们派生原则 #1-#7 全部落地, 13 天后排名仍 < 25, **且**对 bunterrrrr 风格对手的 paired 胜率仍 ≤ 35%, **则**: 哲学的"复利"主线被证伪 (说明我们的 execution 上限就是 1100-1200, 不是哲学问题, 是项目能力问题; 但同时也意味着哲学没给我们多余的指导价值).
2. **如果**只落地 #1 #2 (energy floor + 早 miner), 排名进 20-25 之间, **则**: 哲学是对的, 只是没完全实现, 不推翻.
3. **如果**派生原则 #5 (反镜像) 完全没落地, 排名进 20-25 之间, **则**: 反镜像可能是 over-engineered 的伪需求, 该子原则应被降级.
4. **如果**我们违反派生原则 #6 (双 slot 翻车), 排名暴跌 ≥ 100 ELO 一天内, **则**: 哲学没问题, 是执行问题; 此时该追责的是工程纪律, 不是哲学.

**不应该推翻哲学的情况**: 排名波动在 ±2 名内、单日掉分 < 30 ELO、单一 episode 输了 — 都是 sampling noise, 与哲学无关.

---

## 附录: 与前 8 个 worker 文档的兼容性

| Worker | 文档 | 与本哲学的关系 | 冲突点 |
|---|---|---|---|
| W1 | `ml_rl_and_refactor.md` | 哲学的**容器** (Utility scoring) + **信号源** (决策树挖规则) | 无 |
| W2 | `external_research_and_first_principles.md` | 哲学的**理论库** (Kelly / war of attrition / r-K / time-expanded BFS / energy floor / 反 imitation) | 无, 本哲学是 W2 的合成 |
| W3 | `top_competitors_compendium.md` | 哲学的**数据支撑** (top-15 早 miner + 砍 scout 是复利原则的实证) | 无 |
| W4 | (失败 audit, 散在 research.md) | 哲学的**风控案例库** (v26/v28/v29 翻车 = 双探索教训) | 无 |
| W5 | (阶段轴 / 对手轴 / 进攻轴) | 哲学的**轴框架**, 三段式是阶段轴的简化版 | 无, 但本哲学不细化对手轴 |
| W6 | `wide_brainstorm_and_framework.md` | 哲学的**武技库** (A2 TRANSFER / A1 crush / A16 早 miner) + **理论补强** (B5 期权 / B9 临界态) | 部分冲突: W6 A5 自杀-tie / A19 fake spawn 违反风控原则, 不在主线武技集 |
| W7 | `engineering_principles_and_workflow.md` | 哲学的**工程映射** (派生原则 #6 #7 直接对应 W7 原则 1 / 2) | 无, 本哲学只回答"为什么", W7 回答"怎么做" |
| W8 | `top10_deep_dive.md` | 哲学的**niche 校准** (top10 三流派) + 我们应该选 Silent Miner 复利方向 | 部分: W8 暗示我们也可走 Hybrid (Klodt 路线), 本哲学主线推 Silent Miner; 这是策略分歧, 不是哲学矛盾 |

**本哲学没新增任何理论**, 全部由前 8 位 worker 已经引用过的概念合成. 唯一的新词是 **"幸存复利者"** 这个标签, 用来当 README 顶部的一句话.

---

## 一句话脑图

```
                先求不输 (Survival)
                    |
                    v
                再求复利 (Compound)
                    |
                    v
                最后冲刺 (Sprint)
                    |
                    v
            被人模仿 → 反镜像 (Anti-mirror)
                    |
                    v
            双 slot 一保底一探索 + z-gate (Risk Budget)
```

把这 5 层倒过来看就是 7 条派生原则的来源: 风控线 (Survival) / 复利时间价值 + 期权 jump (Compound) / 末段切档 (Sprint) / 反镜像 (Anti-mirror) / 仓位 + Z-gate (Risk Budget).

---

**End of W10 unifying philosophy.**
