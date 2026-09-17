# 工程方法论与 13 天工作流 (W7)

> 综合 W1 (`docs/ml_rl_and_refactor.md`)、W2 (`docs/external_research_and_first_principles.md`)、W3 (`docs/top_competitors_compendium.md`) 与 `docs/research.md` 的"做什么"结论, 本文只回答"怎么做"。
>
> 写作日期: 2026-06-03. 当前: rank 24/345, v37 publicScore 1129.0 (峰值 1142.4), v24 历史峰 1236.5. 距 6-16 截止 13 天.

---

## 0. 执行摘要 (10 行)

1. **架构选择已收敛**: 13 天 + CPU + 单文件 + 3s/turn + 数据稀缺, 唯一合理路线是"规则 + 学到的常数 + 用 ML 离线挖规则", 不做端到端模型。
2. **表达形式已收敛**: Utility scoring (Option A, 见 W1 §4.1) + phase label 作为 ctx 特征, 不重新发明 DSL / 行为树 / YAML。
3. **当前是修补瓶颈**: v24 → v37 → v40 是 3 个 patch 叠在同一段 elif 上, 第 4 个 patch 会引入横向回归 (v40 漏掉敌 factory 当前格已经是一次)。
4. **工作流瓶颈不在写代码**: 而在 (a) active slot 安全替换 (b) paired-seed 显著性判定 (c) 失败 replay 局部回归验证。3 件事每天都重复, 必须脚本化。
5. **W1/W2/W3 已经各自给出"做什么"**: W1 给重构, W2 给反 imitation + time-expanded BFS + energy floor + 1-ply, W3 给早 miner + 砍 scout + 侧矿 + late wall remove。W7 的任务是把它们排进 13 天日历, 不再扩张研究面。
6. **最致命的一条原则**: "永远不要让两个 active slot 同时是未验证的实验代码" — v26 教训 (research.md §v29) 让 v24 的 1236 一天内消失。
7. **明天 D+1 唯一一件事**: 启动 Option A 重构 PoC (1-2 天), 重构完成前停止往 v40 上叠新 patch。

---

## Q1. 纯策略 vs 加模型 (决策树)

```
if 数据 ≤ 1000 (state, action) 标注 OR deadline < 2 周 OR CPU only OR 3s/turn 紧张:
    纯规则 + 手调常数                                            # 起步
elif 有 ≥ 30 paired-seed 评估通道 AND 候选参数 ≤ 30 个数值:
    规则 + 学到的常数 (ES / CMA-ES 在 knob space 搜索)            # 调优
elif 有稳定模仿对象 (≥ 50 episode 全状态) AND 标注问题离散且可解释:
    规则 + 学到的局部 policy (用 decision tree 挖规则, 上线规则)   # 抽规则
else (大数据 + GPU 周级 + 单步 reward 可信 + 稳定 sim):
    端到端学习 (PPO / IL + DAgger / AlphaZero)                    # 不在我们桌上
```

**分支条件论证**:

- **第 1 层 (纯规则)**: 13 天 / 5 提交/天 = 65 次在线信号, 单次 ELO 稳态需 ~50 episode ≈ 24h, 算上失败重提, 真实可用迭代 ≤ 25 次。Halite IV / Lux S2 / Kore 2022 / maze-crawler 自己的 Top 15 都是规则胜出 (W3 §1, W1 §1)。
- **第 2 层 (规则 + 学常数)**: v37 / v40 已经累积 ~15 个数值常数 (`SCOUT_DELAY_STEP`, gap 4/6/8, energy floor 200/350/650 等)。本地 paired-seed 在 30-50 seed 时 σ ≈ 7%, 足以做 ES 收敛 (W1 §3.8)。
- **第 3 层 (规则 + 学局部 policy)**: 我们已经下载 17 条 bunterrrrr 全状态 replay + 167 条元数据。深度 4 决策树 1 小时跑完, 输出"规则上 main.py", 不挂模型 (W1 §3.1)。这是产出"做什么"的来源, 不是 inference path。
- **第 4 层 (端到端)**: Lux S1 IL-only 排 93/1178 (W1 §1), AlphaZero 需要 fast sim 我们没有 (kaggle-environments 30-50ms/step → 2-ply ≈ 3s 极限), 端到端 PPO 需 GPU 周级 → 13 天死线下负 EV。

**位置判定**: 我们**现在**站在第 2 层与第 3 层之间 (W1 已经在做 ES 思路, 决策树挖规则 script 尚未启动)。**13 天后**应仍在同一位置 — 因为截止日后 ELO 还要稳态 ~2 周 (W2 §6 风险 B), 最后 3 天必须冻代码, 没时间往第 4 层试。

---

## Q2. 策略的"表达形式" (6 × 6 表)

| 表达方式 | 可读性 | 修改成本 | 回归风险 | 性能 (3s/turn) | 单文件兼容 | A-B 统计友好度 |
|---|---|---|---|---|---|---|
| elif 链 (现状) | ✗ 共享 fallthrough, 5+ 层后失控 | ✗ 每加 1 patch 改 3-5 处 | ✗ 高 (v40 漏掉 enemy current cell) | ✓ 纯 if, 微秒级 | ✓ | ✗ 切优先级要全表重算 |
| Utility scoring | ✓ 每条规则是一个 scorer 函数 | ✓ 新增 patch = 加 1 函数 + 1 权重 | ✓ 硬 gate (-1e6) + 软评分天然隔离 | ✓ 候选 ≤ 13 × scorer ≤ 10, 100µs 级 | ✓ | ✓ 关闭单 scorer 就是 A-B |
| Phase 状态机 | ? 3 phase 内仍是 elif | ✗ 改 phase 边界全炸 | ✗ phase 抖动 (v32 / v33 已栽过) | ✓ | ✓ | ? 需对 phase 标签 stratify |
| Behavior tree | ? 库化引入名词噪音 | ? Sequence/Selector 重 wire | ? 同 elif | ✓ | ✗ 通常引外部依赖 | ✗ 树结构难局部消融 |
| Internal DSL | ✗ 自造语法, 新人成本高 | ✗ 同时维护 DSL + 解释器 | ? 解释器自身可能有 bug | ? 增加间接层 | ✗ 解释器代码 ≥ 200 行 | ? 取决于 DSL 设计 |
| YAML 规则表 | ✓ 表格直观 | ? 改 YAML 易, 加新维度难 | ✗ 类型/边界都在运行时炸 | ? 需 parse, 缓存可救 | ✗ 需嵌 YAML 字符串 | ✓ 表行就是规则单元 |

**推荐**: **Utility scoring 作为主架构** (W1 §4.1 已给 skeleton ~150 行), **Phase label 作为 ctx 特征喂进 scorer 权重** (W1 §4.2 的退化用法, W2 §3.2 b 的 K → r 切换正好需要)。Behavior tree / DSL / YAML 不达标; 单纯 phase machine 在我们这个尺寸下退化为短 elif 链, 不解决 fallthrough 问题。

---

## Q3. 13 天工作流

### 3.1 每日 routine 模板 (8 小时)

1. **0.5 h** 拉昨日提交的 publicScore 和最新 replay, 跑 `scripts/analyze_replay_failures.py` 看失败分类是否漂移。
2. **0.5 h** 检查 2 个 active slot: 弱槽若 < 保底 - 50 持续 6h+, 立即 refloor (`v24 mainline`)。
3. **2 h** 选今日 1 个 patch 候选 (顺序按 Q3.5 day-by-day 简表), 写代码, py_compile + smoke vs random 5 seeds。
4. **2.5 h** 本地 paired gate (见 3.2), 失败则直接弃; 成功则准备 commit message + Experiment Log 条目。
5. **0.5 h** 提交 (探索槽), 同步检查保底槽是否仍在线; 不在 24h 内连替同一槽。
6. **1 h** 失败 replay 局部回归: 用 `scripts/replay_action_regression.py` 验证今日 patch 在历史失败点上确实改了行为。
7. **1 h** 写 `docs/research.md` Experiment Log 条目 (强制 inline 文档, 见 Q4 原则 6)。

### 3.2 每次提交 checklist (8 项)

1. `py_compile main.py` 通过, 无 syntax / import error。
2. smoke vs `random` 5 seeds, 0 crash, 平均奖励 > 0。
3. **paired vs 主线 (v37 + v24)** 各 50 swap-sides seeds, **z ≥ 1.5** (W2 §3.5 b)。
4. **paired vs 历史代际** (v9, v15, v19, v24) 各 30 seeds, 任何代际胜率 < 45% → 拒绝 (W2 §1.3 frozen teacher)。
5. 若 patch 起因是某条在线 loss replay, `replay_action_regression.py` 必须证明该 step 行为改变了 (否则等于没改)。
6. `research.md` Experiment Log 新条目: ref, 父版本, diff 一行说明, 4 组 paired 结果, 失败分类预期。
7. 提交命令带明确 message: `vNN <one-line intent>`; 不重用旧 message。
8. 提交后 30 min 复检 Kaggle submissions 表, 确认进入 active slot, 且另一槽仍是保底。

### 3.3 Active slot 管理策略

- 配置: **1 个保底 (v24 / v37 mainline, 在线 ≥ 1100 已验证) + 1 个探索 (今日新 patch)**。
- **升级条件**: 探索槽 publicScore ≥ 保底 + 30, 持续 24h (≥ 30 在线 episode) → 探索槽变保底, 旧保底退役。
- **降级条件**: 探索槽 publicScore < 1100 持续 6h, 或单段连掉 ≥ 50 → 立即 refloor。
- **禁止**: 同时把两个槽换成未验证代码 (v26/v28/v29 教训, research.md §v29 让历史 1236.5 一天内消失)。
- **禁止**: 一日内同一槽提交 ≥ 3 次 (浪费 daily quota, 也让在线样本拼不齐)。

### 3.4 失败处理

- **连续 3 次 paired 不过 z = 1.5 gate**: 暂停当前分支, 改做 (a) ES on knob 微调当前最优, 或 (b) 启动新方向 (W3 §5 highest-ROI 三条之一: 早 miner / 砍 scout / 侧矿)。不要硬上不显著的 patch。
- **active slot 单段掉 ≥ 50 ELO**: 立即 refloor 回 v24 mainline (research.md §v40 的 v41 refloor 是模板); 失败 replay 留作明日 patch 输入, 不当场拼凑救场。
- **5 daily quota 用完仍未上分**: 当日停手, 跑离线 ES / 决策树挖规则 (W1 §3.1, W1 §3.8); 不要为了用满 quota 而提弱版本。
- **某天连续 2 个 patch 都触发 z < 1.5**: 强烈信号当前架构已到瓶颈, 提前启动 Q3.5 的 Option A 重构。

### 3.5 day-by-day 简表 (D+1 = 2026-06-04, D+13 = 2026-06-16)

| Day | 主任务 (W1-W6 产出排序) | 提交目标 |
|---|---|---|
| D+1 | **W1 §4.1 Option A 重构 PoC** + 并行启 `scripts/mine_decisions.py` (W1 §3.1) | 无 (重构日, 保留 v37 + v38) |
| D+2 | Option A 完成 + 与 v37/v40 parity 测试 (W1 §7.1 风险 1) | v41 = Option A 等价版 (本地 ≥ v37) |
| D+3 | 集成决策树挖出的第 1 条规则 (W3 §5.1 早 miner) | v42 早 miner @ step ≤ 25 |
| D+4 | W2 §3 原则 3 energy hard floor (≤ 10 行 diff) | v43 floor |
| D+5 | W2 §3.4 b time-expanded BFS (c, r, jcd, mcd) | v44 BFS 4D |
| D+6 | W3 §5.2 受控侧矿 (mvcd > 0 且 gap ≥ 6) | v45 gated side miner |
| D+7 | ES on Q3.2 通过的 knob 集合, 跑 1 整天 | v46 ES-tuned |
| D+8 | W3 §5.3 砍 routine scout (gap > 4 + 距敌远) | v47 |
| D+9 | W2 §3.4 a 1-ply lookahead tie-break (top-2 cost 差 < 10% 时) | v48 |
| D+10 | 整合: 把 D+3 ~ D+9 通过的规则合到当前最强 mainline | v49 combined |
| D+11 | **稳定期开始**: 只允许 ≤ 10 行 narrow patch, 修最近 6h 内出现的 loss class | v50 narrow fix |
| D+12 | 仅 refloor / 复盘, 不上新代码 | v51 mainline refloor |
| D+13 | 截止日: 早上做最后一次 active slot 状态体检, 之后不再提交 | (可选) v52 = D+10 mainline 复盘版 |

注: 上表是 **乐观顺序**, 任一步触发 Q3.4 失败处理就回退到 Q3.4 分支。预计真实通过率 50-60%, 约能落地 6-7 条 patch。

---

## Q4. Engineering Principles (6 条)

1. **Never break the active slot** — 永远保持至少 1 个 slot 是已知在线 ≥ 1100 的稳定版本; 永远不要在 24h 内同时替换两个槽。**案例 (失败)**: research.md §v29: v26 + v28 + v29 三连提交后, v24 历史 1236.5 在 leaderboard 消失, 24h 后才靠 v30/v31 把分数从 600 拉回 1123。
2. **Reject any patch with paired-seed z < 1.5σ** — 本地 50 seeds 时 σ ≈ 7%, +1 的 delta (z ≈ 0.14) 是噪音; 占 active slot 的机会成本远大于潜在收益。**案例 (失败)**: research.md §v40: v40 vs v37 +1/50, 在线 publicScore 858 vs v37 1142, 拖累整个 leaderboard 一日。
3. **Active slot 一保底一探索, 不要双探索也不要双保底** — 双保底浪费一次实验机会, 双探索任一翻车就掉分。**案例 (成功)**: research.md §v38: v37 (探索) + v38 (v24 保底) 配置让我们在 v37 中段震荡时仍守住 1007+。
4. **Patch over refactor 直到 N (≈ 10) 个 patch, 之后强制重构** — 重构是负 EV 直到 elif 链开始横向回归。v24 (1 patch) → v37 (+1) → v40 (+3) 已经 3 个; 第 4 个开始引入 fallthrough bug, 必须切 Option A。**案例 (失败)**: research.md §v40 follow-up: knob 1 漏把 enemy 当前格无条件加进 threats, 因为只在 `collision_tiebreak_bad` 分支里加 — 这正是 elif 共享 fallthrough 的典型 bug。
5. **Reproduce online failure locally before patching** — 任何针对在线 loss 的 patch 必须先用 `scripts/replay_action_regression.py` 在该 episode 上证明改动会生效; 不能"看 replay 改一行就提交"。**案例 (成功)**: research.md §v24: v24 在提交前用 replay regression 验证 step-159 由 `JUMP_EAST` 改成 `IDLE`, 因此挂上线后 publicScore 直接到 1188.9 / rank 12; **案例 (失败)**: v40 没有为 `78598494` 那一类做事先回归, 上线后才发现 knob 1 漏判。
6. **13 天倒计时, 留最后 3 天稳定期** — 截止日后 ELO 还要 ~14 天稳态, 最后 3 天上 5-knob 大改 = 把无法恢复的版本钉死在 leaderboard 上。最后 3 天只允许 ≤ 10 行 narrow patch + refloor。**案例 (预防)**: research.md §v40 的 5 knob 同时上 + 同日重复提交导致采样混乱; 同样的事在 D+13 发生就是不可逆。

---

## 附录: 与 W1/W2/W3 的映射

- 原则 1 ↔ research.md §v29 (W7 总结)
- 原则 2 ↔ W2 §3.5 b (统计显著性 gate)
- 原则 3 ↔ W2 §3.2 c (Kelly + 双 slot 正交)
- 原则 4 ↔ W1 §4.1 (Option A 触发条件)
- 原则 5 ↔ W2 §3.1 b (1-ply 局部回归) + research.md §v24 vs v40
- 原则 6 ↔ W2 §6 风险 B (截止后 2 周稳态)
- Q3.5 day-by-day ↔ W1 §6 + W2 §7 + W3 §5 的合并日历, 不是新方向

**未在本文重复**: W1 给的 Option A 完整代码 skeleton; W2 给的 time-expanded BFS / energy floor / 1-ply / 反 imitation 内部随机化具体公式; W3 给的 top-15 矿/scout/jump 统计表。需要细节请直接读源文档。
