# Maze-Crawler 总体规划 (Master Plan)

> 作者: 总揽者 (Overseer). 日期: 2026-06-03. 截止: 2026-06-16 23:59 (剩 ~13 天).
> 角色定位: 本文是项目的**唯一决策根 + 13 天执行蓝图**。它综合 v1→v41 的全部历程
> 与 V40 之后的 10 份 worker 研究 (W1-W10), 替项目做出**已经拍板的决定**, 而不是再列选项。
> 配套文件: 给执行 Agent 的 prompt 见 [`docs/EXECUTOR_PROMPT.md`](EXECUTOR_PROMPT.md)。
>
> 阅读顺序: 先读 §0 (当前真实状态, 有惊吓) → §1 (执行摘要) → §5 (总揽者裁决) → §7 (版本规划) → §8 (行动清单)。

---

## 0. 当前真实状态 (好消息: 我们在 #13)

> 更正: 本文第一版基于 `after_v40` 08:23 UTC 的**陈旧快照**误判成 rank 66 — 那是 refloor 进行中的瞬时低点。项目方确认**当前已稳在 rank #13**。下文按 #13 重写, 战略相应从"止血"翻成"前置价值冲 top 10"。

| 项目 | 状态 |
|---|---|
| 排名 | **rank #13 / ~342** (已穿过 top 20 / top 15, 紧贴 top 10) |
| 含义 | floor 健康; v41 refloor + 时间稳态生效, 已回到/超过历史最强带 |
| 历史样本 | v24 峰 1236.5 / v37 峰 1142.4 / v30 稳态 1123-1133 |
| 公榜分数线 (参考) | top 10 ≈ 1338 / top 12 ≈ 1202 / **#13 ≈ 1194** / top 15 ≈ 1177 / top 20 ≈ 1154 |

**第一性结论 (重写)**: 我们**不在急救状态**。Goal A "求不输 (回 top 20-15)" 的目标**已经达成**。
本轮任务从"止血爬回去"变成 **"把高 ROI 的价值工作全部前置, 冲 top 10"**。
唯一仍然成立的红线: **不要再用一次双槽翻车 (v40 式) 把 #13 送回去** — 健康的 floor 是我们前置激进改动的本钱, 不是可挥霍的筹码。

**5 件必须立刻知道的事实 (重写)**:
1. **floor 健康, 但脆**: #13 靠 active slot 撑着; 任何提交仍守"一保底一探索 + 绝不 24h 双换"纪律 (§6.2)。
2. **`main.py` 仍是纯 v24**: W1-W10 所有洞察 (连 1 行 bug P01) 一个都没上线。**价值全在前面, 还没拿。**
3. **目标上移**: top 15-20 已达成, **新主线目标 = top 10 (≈1338)**。从 #13 到 top 10 的唯一路径是**经济引擎**, 不是再修执行。
4. **经济引擎现在是主线 (不再是上行赌注)**: 与 bunterrrrr 的 final energy 差距 (351 vs 6729) 是仅剩的大杠杆。仍只上探索槽、严 gate (v14/v40 教训), 但**优先级提到最前**。
5. **时间是最紧的约束**: 想算分的改动**必须 Jun 11 前上线** (ELO ~2 周稳态), 最后 3 天 (Jun 14-16) 冻结。**所以"前置" = 把经济引擎尽早送上榜抢稳态时间。**

---

## 1. 执行摘要 (TL;DR, 10 行)

1. **一句话哲学 (沿用 W10)**: **"先求不输, 再求复利, 最后才求冲刺. 同时永远假设自己被人模仿."** 项目代号 **幸存复利者 (The Surviving Compounder)**。
2. **当下不是止血, 是前置价值**: floor 健康在 #13, 第一步是把高 ROI 改动 (worker buffer + 经济引擎) 尽早送上榜抢稳态时间。
3. **Goal A 已达成 (已在 #13), Goal B 经济引擎升为主线并前置**: 把 worker buffer + 早 miner + TRANSFER 回流提到最前几天; 执行修复 (P01/boundary) 作为零风险底色一起带上, 不单独占 slot-cycle。
4. **架构裁决**: 先 ship 1 行正确性修复 (P01) 作为新 floor → 再做 Option A utility-scoring 重构 (W1) 作为后续所有 patch 的容器 → 经济招式以 scorer 形式落在重构之上, 不再往 elif 链上塞 (W7 原则 4: v40 的 bug 就是 elif fallthrough)。
5. **上线纪律 (不可违反)**: 永远一保底一探索; 任何 patch 过 paired-seed z≥1.5σ 才上探索槽; 探索槽连续 6h < 1100 或单段掉 ≥50 → 立即 refloor; 绝不 24h 内换两个槽。
6. **最高 ROI 的三个具体改动**: (a) P01 enemy-current-cell 1 行修复; (b) 末期 boundary_scroll 防御 (我们 6 死 + Joseph 7 死的共病); (c) 砍 step 32 后的 routine scout + 加 1 个 worker buffer (修 "0-worker + 高 scout" 这个被决策树一眼认出的指纹)。
7. **经济引擎的核心杠杆 (Goal B)**: K6 三步绞 = 早 miner (step≤25) + miner TRANSFER_SOUTH 回流 + 工厂踩自家矿吃 +50/turn。这是 bunterrrrr 把 energy 推到 7000 的机制, 但必须 gate 严、只上探索槽。
8. **ML 的定位 (沿用 W1)**: **用 ML 找规则, 上线规则, 不上线模型。** 决策树挖 bunterrrrr replay 给 1 天, 要么挖出新规则 (便宜 ELO), 要么证明经济已被榨干 (省得我们瞎赌)。不碰 PPO/AlphaZero/端到端。
9. **终止条件 (止损)**: 若 Jun 11 前经济引擎在线没确认 ≥ floor, **放弃 Goal B**, 锁定 floor agent, 余下时间只做执行打磨 + ES 微调。
10. **明天 (Jun 4) 三件事**: ① ship v42 = v24 + P01 + 末期 boundary 防御 (零风险底色, 新 floor 候选) 到探索槽; ② 准备 v43 = worker buffer (W8 #1 ROI); ③ 并行起 `scripts/mine_decisions.py` 决策树挖矿。研究冻结, 全力上线。

---

## 2. 历程回顾 (v1 → v41)

完整 changelog 见 `docs/full_pattern_compendium.md` 附录 A。这里只标**转折点**:

| 阶段 | 版本 | 关键事件 | 在线结果 |
|---|---|---|---|
| 起步 | v1 | 公开 top2 jump-preferred BFS baseline (镜像墙/乐观 fog/emergency escape) | 736→997 |
| 防撞探索 | v6-v11 | 敌工厂避撞 / gap guard / late scout reserve, 多数被 paired-seed 否决 | v9 1016 |
| **经济觉醒** | v14-v19 | bunterrrrr 研究 → 加北向 mine 经济 + scout 延迟。**v19 (delay24 北矿) 成第一条经济线** | v19 809→ |
| **当前主干诞生** | v24 | v19 + jump-only 敌工厂 guard。**历史最强, 峰 1236.5 / rank 12** | 1188→1236 |
| slot 翻车 #1 | v26/v28/v29 | 同时换两槽, v24 的 1236 在榜上消失, 一天后靠 v30/v31 拉回 | 跌到 600 再回 1123 |
| 稳态部署 | v30/v31 | v30=v24 主干, v31=v19 备选; rank 25-26 | v30 1123-1133 |
| 末期修补尝试 | v32-v36 | late scroll / 侧矿 / save-jump, 多数本地负, 不上线 | — |
| 当前探索线 | v37 | late save-jump + 低 gap 不建 scout/miner。**与 v24 paired 略胜, ladder 友好** | 峰 1142.4 |
| **slot 翻车 #2** | v40 | 2-turn collision predictor 等 3 knob, 本地 +1~+14 但**在线沉到 968**, 且自己带一个新 collision bug (P01) | **968 → 拖到 rank 66** |
| 止血 | v41 | resubmit v24 refloor (pending) | 恢复中 |

**历程的三条铁律 (用血换的)**:
- **铁律 1**: 本地 paired-seed 好看 ≠ ladder 好看 (v14/v21/v40 全部应验)。本地只能当 crash check + 显著性 gate, 真实裁判是在线 active slot。
- **铁律 2**: 同时动两个 active slot = 必翻车 (v26 一次, v40 一次)。
- **铁律 3**: 我们最强的两条线 (v24 / v37) 都是**窄改动 + 守住北推节奏**赢的; 每次"贪经济/贪防御"的宽改动都给回了核心强度。

---

## 3. V40 之后的研究汇总 (W1-W10)

V40 之后, 项目并行做了 10 份 worker 研究 (≈300KB)。一句话各是什么 + 它给主线贡献了什么:

| Worker | 文档 | 一句话 | 对主线的净贡献 (已被本 plan 采纳的) |
|---|---|---|---|
| **W1** | `ml_rl_and_refactor.md` | ML/RL 全谱调研 + Option A 重构 skeleton | **Option A utility-scoring 重构** (§6 架构) + "用 ML 找规则不上模型" + 决策树挖矿 (Action) |
| **W2** | `external_research_and_first_principles.md` | 跨比赛冠军复盘 + 第一性原理 (Kelly/r-K/期权/energy floor/反 IL) | energy hard floor / phase-aware K→r / z≥1.5 gate / 反 imitation 的理论背书 |
| **W3** | `top_competitors_compendium.md` | top-15 数据编目 | **三条最高 ROI: 早 miner / 砍 scout / 受控侧矿** + "economy 才是 rank24→15 的 gap" |
| **W4** | `full_pattern_compendium.md` | 项目内代码总册 + 30 条技巧编目 | 3 个被忽视的窄改动点 (worker 死代码 / 二级 BFS / emergency 块无 north-only 保护) |
| **W5** | `phase_axis_design.md` | 显式 `current_phase()` 4 相位设计 | **末期 Final Kick 相位** (修 boundary_scroll) + 把 9 个散落阈值收敛到 2 个 |
| **W6** | `wide_brainstorm_and_framework.md` | 引擎源码审计 + 15+ 反直觉武技 + 跨学科心法 | A1 factory-crush / A2 TRANSFER 回流 / A16 早 miner / 期权式 jump 心法 |
| **W7** | `engineering_principles_and_workflow.md` | 13 天工作流 + 6 条工程原则 | **上线纪律全套** (active slot / z-gate / patch-over-refactor / replay 回归) |
| **W8** | `top10_deep_dive.md` | top10 三流派 K-means + 决策树指纹 | **"我们是 0-worker + 高 scout 的 PCA 孤立点"** + worker buffer 是 #1 ROI |
| **W9** | `tactical_patches_and_killer_moves.md` | 25 条行号级补丁 + 6 杀招 + 5 反 mirror 机制 | **P01-P25 具体补丁** + K6 三步绞 + D01/D02 player-asymmetric tiebreak |
| **W10** | `unifying_philosophy.md` | 把所有理论收成一个决策根 | **"幸存复利者" + 7 条派生原则** (项目灵魂) |

**研究的收敛结论 (三句话)**:
1. **方向已经收敛, 不需要再研究了** — 该读的引擎源码读了, 该挖的 top-15 数据挖了, 该想的跨学科心法想了。剩下的全是**执行**。
2. **三个数据驱动的硬缺口**: ① 0 worker (top10 全员 ≥0.64); ② 38% 的局完全 0 miner (top10 仅 4%); ③ peak energy 2616 (top10 最低的都有 4240)。
3. **一个唯一的灵魂**: 先求不输 (survival floor) → 再求复利 (early compound) → 末段冲刺 (phase sprint), 且永远假设被模仿 (anti-mirror)。

---

## 4. 决策根: 幸存复利者 + 7 条派生原则

(完整论证见 W10 `unifying_philosophy.md`; 这里钉成执行约束。每条 patch 上线前必须能回答"它服务哪条原则"。)

> **"先求不输, 再求复利, 最后才求冲刺. 同时永远假设自己被人模仿."**

1. **风控线 (Survival Floor)**: 任何威胁"活到 step 500"的动作一票否决。energy 不够时关闭所有 BUILD_*。
2. **复利时间价值 (Early Compound)**: 早 1 turn 上 miner > 晚 1 turn 多 1 row (72 法则)。
3. **期权式 jump (Save Option)**: jump_cd ready 不等于立刻用; 在最大不确定性时刻 (walking BFS 18 turn 内到不了 row+20) 才行权。
4. **末段切档 (Phase Sprint)**: step≥400 或 scroll 临界 → r-mode: 禁建、全力北上、接受 cooldown 浪费。
5. **反镜像 (Anti-Mirror)**: 自对弈/镜像局面用 deterministic-hash (非 `random()`) 打破对称。
6. **仓位管理 (Two-Slot Discipline)**: 永远一保底一探索, 双探索 = 杠杆翻车。
7. **显著性 gate (Z-gate)**: 任何 patch paired vs 主线 50 seeds z≥1.5σ 才上探索槽。

---

## 5. 总揽者裁决 (我对"不妥之处"的判断 + 已拍板的决定)

> 用户要我以总揽者身份, 对不妥之处做决定。以下是我**已经拍板**的, 不是选项。

### 5.1 [已诊断的不妥] 重研究、轻上线 — 立即纠偏

- **现象**: 10 份 worker 文档 ≈300KB, 但 `main.py` 仍是纯 v24, 连 1 行的 P01 bug 都没修。W10 自己承认"空话的部分: 我们排名上不去不是因为没读文档, 是因为没把派生原则 #1 #2 写进 main.py"。
- **裁决**: **即日起研究冻结。** 不再产出新 worker 文档 (W11+)。所有人力转上线。唯一允许的"研究"是 1 天的决策树挖矿 (因为它直接产出可上线规则, 且能判定 Goal B 值不值得赌)。

### 5.2 [战略裁决·已更新] Goal A 已达成, Goal B 经济引擎升为主线并前置

| | **Goal A: 求不输 (已达成)** | **Goal B: 求复利 (新主线, 前置)** |
|---|---|---|
| 目标 | 稳在 top 20-15 — **✅ 已在 #13** | 上探 **top 10 (~1338)** |
| 手段 | 执行修复: P01 + 末期 boundary 防御 (作为零风险底色继续带上) | 经济引擎: worker buffer + 早 miner + TRANSFER 回流 + 踩矿 + 侧矿 (K6) |
| 确定性 | 高 (已兑现) | 低/高方差 (v14/v21/v40 历史: 本地好、ladder 沉) |
| 风险 | 几乎无 | 可能拖沉 ladder → 故只上探索槽, 安全槽守 #13 floor |
| 决定 | 作为底色一起带, 不单独占 slot-cycle | **前置到最前几天, 抢稳态时间; 严 z-gate; ≥30 episode 确认 ≥floor 才促正** |

**裁决理由 (更新)**: 我们已在 #13, Goal A 兑现了。从 #13 到 top 10 没有"执行修复"的便宜路, 只有经济引擎这一条大杠杆。时间 (Jun 11 前必须上线才有稳态) 比确定性更稀缺, 所以**把经济引擎前置**。红线不变: 健康的 #13 floor 用安全槽守死, 经济只在探索槽试, **绝不为 Goal B 双押翻车**。

### 5.3 [架构裁决·已更新] 前置价值, 重构降级为"按需"

用户要求"把重要工作往前推"。重构 (Option A) 是基础设施, 不是价值; 价值是 worker buffer + 经济引擎。所以裁决从"先重构再经济"翻转为**"先抢价值, 重构按需"**:

1. **P01 + 末期 boundary 防御 = 零风险底色** → 直接进 v42 当新 floor 候选, 不单独耗 slot-cycle。
2. **价值改动直接打在 v24 elif 链上, 一次一个可归因块** (W9 设计的就是"原位插入不重写"): v43 worker → v44 经济引擎 → v45 侧矿。每个独占探索槽一轮, 严 z-gate。
3. **Option A 重构降级为按需**: 只有当 elif 链在叠加中**真的出现 fallthrough 回归** (v40 式), 或还想再叠 ≥3 个 patch 时, 才插入重构。若价值改动落得干净, **可以完全不重构到截止** (W7 原则 4: 重构在链开始回归前是负 EV)。这样把 slot-cycle 全留给价值。

**代价与缓解**: 前置 = 在 elif 链上快速叠 patch, 重新引入 v40 式 fallthrough 风险。缓解: 一次只叠一个、每个 replay 回归验证、安全槽全程守 #13。

### 5.4 [需修订的不妥] 文档过时描述

`research.md` L11 "main.py = v1 baseline" (早已是 v24) 和 L30 "factory pathfinding speed dominates economy" (被 W3 推翻, economy 才是 gap) 会误导新读者/新 agent。**裁决**: 由执行 Agent 在 D+1 顺手修订这两行 (见行动清单 A0-c)。

### 5.5 风险登记册 (Risk Register)

| 风险 | 概率 | 影响 | 缓解 (已落到纪律里) |
|---|---|---|---|
| 经济引擎再次拖沉 ladder (v40 重演) | 中高 | 高 | 只上探索槽; z≥1.5; ≥30 在线 episode 确认 ≥floor 才促正; 安全槽永远守 floor |
| 双槽再次同时翻车 | 中 | 高 | 硬纪律: 24h 内绝不换两槽; 每次提交后 30min 复检另一槽仍是 floor |
| 时间不够 (经济没来得及稳态) | 中 | 中 | Jun 11 硬截止: 之后不上能算分的新逻辑; Goal B 没成就锁 floor |
| 重构引回归 | 中 | 中 | parity 测试 (≥80% 逐 step 一致) + 安全槽保护 + Jun 8 放弃线 |
| 本地评估误导 (side-sensitive) | 高 | 中 | 一律 `--swap-sides` + ≥50 seeds; 在线才是裁判 |
| 我们打不动 top 1-3 | 高 | 低 | 已接受: 1080 ELO 差是 execution 差距, 13 天内不可能。目标是 top 10-15, 不是夺冠 |

---

## 6. 开发及上线战略

### 6.1 架构: Option A — Utility-based Action Scoring

(完整 skeleton 见 W1 `ml_rl_and_refactor.md` §4.1。)

- 工厂决策从"100 行 elif 链"改为"枚举全部合法 candidate action → 每个用一组具名 scorer 加权打分 → 取最高分"。
- 硬 gate 用 `-1e6` (safety / 非法), emergency 用 `1e3`, 其余 scorer 落在 `[-50, +100]`。
- **每条现有 patch = 一个 scorer 函数; 每条新经济招 = 加一个 scorer + 一个权重。** 关掉单个 scorer 即天然 A-B。
- BFS helper (`bfs_jump`/`bfs_first_step`/`can_move`/`safe_factory_action`) **原样保留**, 不动。
- Phase label (W5 的 `current_phase()` 4 相位) 作为 **ctx 特征喂进 scorer 权重**, 不做成顶层状态机 (避免 phase 抖动, v32/v33 栽过)。

### 6.2 上线纪律 (W7 六原则, 不可违反)

1. **Never break the active slot**: 永远 ≥1 个槽是已知在线 ≥1100 的版本。
2. **Reject z < 1.5σ**: 本地 50 seeds σ≈7%, +1 是噪音, 不占探索槽。
3. **一保底一探索**: 不双探索, 不双保底。
4. **Patch over refactor 直到链失控**: 已到极限 → 这轮做 Option A 重构。
5. **改 bug 前先在 replay 上回归**: 用 `scripts/replay_action_regression.py` 证明该 step 行为变了才提交 (v24 这么做上了 1188; v40 没做, 沉了)。
6. **留最后 3 天冻结**: Jun 14-16 只 ≤10 行窄 patch + refloor。

### 6.3 每日 routine (8 项 checklist, 每次提交)

`py_compile` ✓ → smoke vs random 5 seeds 0 crash ✓ → paired vs (v24+v37) 各 50 swap-seeds **z≥1.5** ✓ → paired vs 历史代际 (v9/v15/v19/v24) 各 30 seeds 胜率 ≥45% ✓ → 若起因是在线 loss 则 replay 回归证明行为变了 ✓ → `research.md` Experiment Log 新条目 ✓ → 提交带明确 message ✓ → 30min 后复检另一槽仍是 floor ✓。

### 6.4 升降级规则

- **升级 (探索→保底)**: 探索槽 publicScore ≥ 保底 +30 且持续 ≥30 在线 episode → 升为新保底。
- **降级 (refloor)**: 探索槽 < 1100 持续 6h, 或单段掉 ≥50 ELO → 立即 resubmit floor agent。

---

## 7. 版本规划 (Roadmap — 前置价值版)

时间轴: D+1 = 2026-06-04, D+13 = 2026-06-16。版本号承接 v41。我们已在 #13, 所以**把最高 ROI 的价值 (worker + 经济引擎) 全部前置到最前几天抢稳态时间**; 执行修复作为零风险底色一起带; 重构降级为按需。
**约束: 只有 1 个探索槽 = 候选串行验证。所以把"安全且独立"的修复 bundle 进同一次提交省 slot-cycle, 把高方差/需归因的价值改动单独一轮。**
**预计真实通过率 50-60%, 任一版本不过 z-gate 就跳过顺延; 乐观顺序, 非承诺。**

| Phase | 日期 | 版本 | 内容 | 目标 | 风险 | 槽 |
|---|---|---|---|---|---|---|
| **1 焊地板** | D+1 | v42 | v24 + **P01** (1 行 bug fix) + **末期 boundary 防御** (Final Kick: step≥400/gap≤4 强制北推禁 BUILD/REMOVE) — bundle 成零风险新 floor | ≥ #13 | 极低 | 探索 |
| **2 前置价值** | D+2 | v43 | + **1 worker buffer (P21)** (step≥300 & gap≥8 & energy≥500 & 0 worker & ≥1 miner) — W8 #1 ROI, 修 0-worker 指纹 | +50~100 | 低 | 探索 |
| | D+3~D+4 | v44 | + **经济引擎 = 早 miner (step≤25 任意方向) + miner TRANSFER_SOUTH 回流 + 工厂踩自家矿** (K6 三步绞) — **最大单杠杆** | +70~130 | 中 | 探索 |
| | D+5 | v45 | + **受控侧矿** (gap≥8 & energy≥700 & 距敌>6) + **D01/D02 player-asymmetric tiebreak** (反镜像, 0 随机) + 砍 step>32 routine scout | +30~70 | 中 | 探索 |
| **3 收束** | D+6~D+7 | v46 | **整合** D+2~D+5 过 gate 的改动到最强主线 + **ES 微调**阈值/权重; **若 elif 链已出现 fallthrough 回归 → 此时才插入 Option A 重构** | 合成 | 中 | 探索→≥floor 促正 |
| | D+8~D+10 | v47+ | 二线 ROI 择优 (factory-crush A1 / 1-ply lookahead tie-break / 镜像扩展到 mining_nodes); 经济稳态观察 | 上探 | 中 | 探索 |
| **4 冻结** | D+11~D+13 | v50+ | 只 ≤10 行窄 patch 修最近 6h loss class; **Jun 14-15 promote 最佳已验证 agent 到两槽; Jun 16 只体检不提交** | 守住 | 低 | 锁定 |

### 7.1 每个版本的执行方案 (条件 / 动作 / 验收 / 失败回退)

> 行号引用 v24 `main.py`。每条带"派生原则"标签确认它服务哲学。每个版本从父版本 copy 到 `experiments/vNN_<name>/main.py`。

**v42 — P01 修复 + 末期 boundary 防御 (bundle, 零风险新 floor)** [原则 #1 风控 + #4 末段]
- 动作 a (P01): 把 `main.py:263` 的 `enemy_factory_threats.add((ec, er))` **移出** `if collision_tiebreak_bad:` 块 (line 258), 对所有可见敌工厂无条件添加当前格。
- 动作 b (boundary): `step≥400` 或 `gap≤4` 时进 Final Kick — 强制 `NORTH`/`JUMP_NORTH` (无北路才 E/W), 禁 `BUILD_*` / `REMOVE`, support 全 IDLE 锁能量 (参 W5)。
- 验收: `replay_action_regression.py` 证明 `78598494` 不再走进静止敌工厂 + 6 个 boundary_scroll 样本 ≥3 个不再末期 BUILD; paired vs v24 z≥0 (纯修复+保命, 不应变差)。
- 回退: 若 boundary 阈值太激进伤中盘, step 400→430 再测 (W5: 保守侧代价 ≤10 ELO, 激进侧 30-50)。两个动作独立, 若 bundle 退化可拆分 bisect。

**v43 — 1 worker buffer** [原则 #1 末段 tiebreak buffer; W8 #1 ROI]
- 条件: `turn≥300` & `gap≥8` & `energy≥500` & `counts[WORKER]==0` & `counts[MINER]≥1`。
- 动作: `main.py:330-336` scout 分支后加 `BUILD_WORKER_NORTH` 分支。修 "0/44 局有 worker" 这个被决策树一眼认出的 PCA 孤立指纹。
- 验收: paired vs v42 z≥1.5; 末期 timeout_tiebreak 胜率提升 (worker 撑 final energy)。
- 回退: 绝不堆 5+ worker (Joseph/AI-TOOK 教训 → boundary_scroll 暴增), cap 在 1。

**v44 — 经济引擎 K6 三步绞 (最大单杠杆)** [原则 #2 复利]
- 三部分合一: ① 早 miner — `turn≤25` 且任意方向 (N/E/W) 邻格可见 mining_node 时跳过 `gap>5`/`energy≥650` 门槛 (`main.py:314`); ② TRANSFER 回流 — miner 在 node 上且工厂 1-ply 邻近时, miner 段 (`main.py:421-429`) 先 `TRANSFER_<朝工厂>` 回流 ~250 energy, 下回合再 `TRANSFORM`; ③ 踩矿 — 工厂踩自家矿条件 `gap>10`→`gap>6` (`main.py:340/345`)。
- 验收 (严, v14/v40 教训): paired vs v43 **z≥1.5σ** (低于 1.0σ 直接弃); first_miner 中位数 ~90→≤30; transfer_total 0→正; peak factory energy 2616→≥4000。**上探索槽后, 在线 ≥30 episode 确认 ≥ floor 才促正; 沉了立即 refloor。**
- 回退: 沉 ladder → 收紧早 miner 到 `turn≤15` + 仅 NORTH; TRANSFER 仅在 `factory_energy<500` 时走。

**v45 — 受控侧矿 + 反镜像 + 砍 scout** [原则 #2 + #5]
- 动作 a (侧矿): `gap≥8` & `energy≥700` & E/W 邻格是 node & Manhattan-6 内无敌工厂 (比 v21 失败教训严)。
- 动作 b (反镜像, 零风险): BFS `DIRS` 迭代顺序按 `obs.player` 分两版 (p0 偏 EAST, p1 偏 WEST, D01); 侧矿方向同此偏好 (D02)。0% 随机度。
- 动作 c: `BUILD_SCOUT` 在 `step>32` 后不再 routine (决策树指纹 `scout_per_minute>0.29 → us` 的对治)。
- 验收: paired vs v44 z≥1.5; 自对弈 draw_rate ~20%→≤10% 且单边胜率不变; vs pilkwang/top2 不负。
- 回退: 侧矿沉 ladder 就只留 D01/D02 (零风险) + 砍 scout, 砍掉侧矿。

**v46 — 整合 + ES (+ 按需重构)** [收束]
- 动作: 把 v42-v45 过 gate 的改动合进当前最强主线; ES (CMA-ES) 在阈值/权重上跑 30-seed paired fitness 1 整天。
- **按需重构**: 仅当 elif 链在叠加中出现 fallthrough 回归 (v40 式), 才按 W1 §4.1 skeleton 做 Option A utility-scoring 重构 + `tests/test_refactor_parity.py` (≥80% 逐 step 一致)。否则**不重构**, 把 slot-cycle 留给价值。
- 验收: 整合版 paired vs 各代际全 ≥ floor; 在线 ≥ floor 持续 30 episode → 促正为新保底。

**v47+ — 二线 ROI (时间富余才做)**
- factory-crush 主动碾压 (W6 A1 / W9 P13): 1-ply 内有敌 support 时主动撞, 单向碾压零代价 (需重排工厂优先级, 单独测)。
- 1-ply lookahead tie-break (W1 §4.4): top-2 scorer 差 <5 时 sim 1 turn 选优, 修"被撞死在 cooldown"。
- 镜像扩展到 mining_nodes/crystals (W6 A3 / W9 P19)。

### 7.2 关键判定门 (Decision Gates)

- **Gate 1 (Jun 5)**: v42 (底色) + v43 (worker) 在线是否 ≥ #13 floor? 否 → 排查是哪个改动拖分, 修或退, 再上经济。
- **Gate 2 (Jun 8)**: 经济引擎 v44 是否在线确认 ≥ floor 且出现 jackpot 局 (peak energy 抬升)? 是 → 继续叠 v45; 否 → 收紧经济条件重试一次。
- **Gate 3 (Jun 11, 硬止损)**: 经济引擎是否在线稳定 ≥ floor? 否 → **放弃 Goal B**, 锁 floor agent, 余下时间只做二线 ROI + ES。
- **Gate 4 (Jun 14)**: 冻结。promote 最佳**已在线验证** agent 到两槽 (经济变体须在线证过 ≥主干才放第二槽, 否则两槽都放主干), 之后只 ≤10 行窄 fix。

---

## 8. 行动清单 (Action Backlog)

> 按优先级排序。`effort`: S=≤30min, M=2-4h, L=6h+。`ELO`: W9/W8 估计 (本地外推, 仅排序用)。
> 状态留给执行 Agent 在 `research.md` Experiment Log 更新。

### A0. 第 0 优先级 (D+1, 并行起步)
- **A0-a [slot 体检]** 查 `kaggle competitions submissions maze-crawler`, 确认两个 active slot 仍是撑住 #13 的样本; 提交任何实验前先确认安全槽是 floor。(S)
- **A0-b [挖矿]** 起 `scripts/mine_decisions.py`: re-replay bunterrrrr focus episode, dump `(features, factory_action)`, fit depth-4 决策树, 打印 split。判定经济还有没有未挖规则。(M, 后台并行)
- **A0-c [修文档]** 修订 `research.md` L11 (main.py 已是 v24 非 v1) 和 L30 (economy 才是 gap, 非 pathfinding)。(S)

### A1. 焊地板 — 零风险底色 (D+1, bundle 成 v42)
| # | 行动 | effort | ELO | 原则 | 来源 |
|---|---|---|---|---|---|
| A1-1 | **v42a** P01 enemy-current-cell 1 行修复 | S | +20~40 | #1 | W9 P01 / research L626 |
| A1-2 | **v42b** 末期 boundary_scroll 防御 (Final Kick) | S | +20~40 | #4 | W5 / W8 #3 |
| A1-3 | (可选 bundle) emergency 块 north-only jump 保护 | S | +15~30 | #1 | W4 B-3 / W9 P09 |

### A2. 前置价值 — 主线 (D+2~D+5, 每个独占探索槽一轮)
| # | 行动 | effort | ELO | 原则 | 来源 |
|---|---|---|---|---|---|
| A2-1 | **v43** 1 worker buffer (step≥300, cap 1) — 修 0-worker 指纹 | S | +50~100 | #1 | W8 #1 / W9 P21 |
| A2-2 | **v44** 经济引擎 K6 = 早 miner (step≤25) + TRANSFER_SOUTH 回流 + 踩矿 — **最大单杠杆, 严 z≥1.5** | M | +70~130 | #2 | W6 A2/A16 / W9 P02+P03+P06 |
| A2-3 | **v45** 受控侧矿 (gap≥8 严 gate) | M | +15~30 | #2 | W3§5.2 / W9 P04 |
| A2-4 | **v45** D01/D02 player-asymmetric tiebreak (反镜像, 0 随机) | S | +10~20 | #5 | W9 D01/D02 |
| A2-5 | **v45** 砍 step>32 routine scout | S | +20~50 | #2 | W3§5.3 / W8 决策树 |

### A3. 收束 (D+6~D+7, v46)
| # | 行动 | effort | ELO | 来源 |
|---|---|---|---|---|
| A3-1 | 整合 A1+A2 过 gate 的改动到最强主线 + ES 微调阈值/权重 | L | 合成 | W1 Action 3 |
| A3-2 | **按需** Option A 重构 + parity 测试 — **仅当 elif 链出现 fallthrough 回归才做** | L | 中性 | W1 §4.1/§7.1 |

### A4. 二线 ROI / 机会池 (D+8~D+10, 时间富余择优)
- A4-1 factory-crush 主动碾压 (W6 A1 / W9 P13): 1-ply 内有敌 support 时主动撞 (单向碾压零代价)。(M, +20~40)
- A4-2 1-ply lookahead tie-break (W1 §4.4): top-2 scorer 差 <5 时 sim 1 turn 选优, 修"被撞死在 cooldown"。(M, +50~100, 不确定)
- A4-3 镜像扩展到 mining_nodes/crystals (W6 A3 / W9 P19): node 可预测。(S, +10~25)

### A5. 冻结期 (D+11~D+13)
- A5-1 只 ≤10 行窄 patch 修最近 6h 的 loss class。
- A5-2 Jun 14-15: promote 最佳**已在线验证** agent 到两槽 (经济变体必须在线证过 ≥主干才放第二槽, 否则两槽都放主干)。
- A5-3 Jun 16: 早上做最后一次 active slot 体检, 之后不再提交。

---

## 9. 度量与终止条件

**北极星指标**: 在线 active slot publicScore (不是本地胜率, 不是排名波动)。
**辅助指标 (每日看)**: 失败分类漂移 (`analyze_replay_failures.py`: boundary_scroll / factory_collision / timeout_tiebreak 占比) + first_miner 中位数 + peak/final factory energy + build_worker 计数 + 自对弈 draw_rate。

**成功标准 (按野心分级, 已在 #13 基线上)**:
- **保底成功**: Jun 16 守住 #13 带 (≥1190, top 13-15) — 经济引擎即使没成, floor 不崩。
- **目标成功**: ≥1250, top 10-12 (worker + 经济引擎部分成形)。
- **超额成功**: ≥1340, 稳进 top 10 (K6 经济引擎完整成形 + jackpot 局)。

**哲学被证伪的条件 (W10, 自我惩罚)**: 若 7 条派生原则全部落地, Jun 16 仍 <1130 且对 bunterrrrr 风格 paired 胜率 ≤35% → "复利"主线被证伪, 说明我们 execution 上限就是 1100-1200。

**不应慌的波动**: 排名 ±2、单日 <30 ELO、单局输 — 都是 sampling noise, 不触发任何动作。

---

## 10. 给执行 Agent 的交接

执行 Agent 的完整 prompt 见 **[`docs/EXECUTOR_PROMPT.md`](EXECUTOR_PROMPT.md)**。
交接要点 (总揽者 → 执行者):
- 你 (执行 Agent) 负责"怎么做"; 本 plan + W10 负责"为什么"。不要重开战略辩论, 不要产新研究文档。
- 严格按 §7 版本顺序 + §6.2 上线纪律执行。每个 Gate 暂停, 把结果回报给总揽者 (用户) 再继续。
- 任何与本 plan 冲突的"更好想法", 先写进 `research.md` 候选区, 不要直接改 main.py 绕过 plan。

---

**End of Master Plan. 一切以"先求不输"为先。**
