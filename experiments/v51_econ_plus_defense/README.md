# v51 = econ (v44b) + defense (v46)

**状态:** 占位骨架。等 v44b_transfer_only 与 v46_defense_bundle 通过各自 paired_eval (vs v37, z ≥ 0) 后再合并。

## 组合来源
- 基底: `experiments/v44b_transfer_only/main.py` (经济线: 早 miner + TRANSFER)
- 增量: `experiments/v46_defense_bundle/main.py` 的"防御段"(final_kick / late save jump / 能量地板)

## 合并方式
在 v44b 基础上叠加 v46 的防御逻辑:
1. 拿 v44b 当主干 (保留它的早 miner / TRANSFER 决策)。
2. 从 v46 抽出**只属于防御段**的代码块: `final_kick` 触发条件、`emergency_north_fallback`、能量地板相关的 if 分支。
3. 注意不要重复双方都改过的"BUILD_MINER"段——以 v44b 为准。

## 预期 ELO
- v44b vs v37 单独: 估计 z ≈ +1.0 ~ +1.5 (经济叠加)
- v46 vs v37 单独: 估计 z ≈ +0.5 ~ +1.0 (防御保底)
- 组合预估: 增益不完全可加, 取 0.6 倍系数 → z ≈ +1.2 ~ +1.8

## 风险
- 早 miner 抢走能量, 触发 v46 的"能量地板"保底, 导致防御段反复 fire → 反而少打仗。
- 两者都改了 build 优先级时可能互冲, 需用 magic comment 隔离段。
