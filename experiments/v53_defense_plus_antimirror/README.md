# v53 = defense (v46) + anti-mirror (v47)

**状态:** 占位骨架。等 v46 / v47 各自验证后合并。

## 组合来源
- 基底: `experiments/v46_defense_bundle/main.py`
- 增量: `experiments/v47_dirs_split/main.py` 的方向 tie-break / hash 噪声段

## 合并方式
两者都基于 v37, 修改面互补:
1. 以 v46 当主干 (它的 final_kick / 能量地板已经覆盖大部分中后期决策)。
2. 把 v47 的 DIRS split 段贴到 v46 主决策树末端的 tie-break 位置。
3. 验证两者都没改同一条 `if turn >=` 分支。

## 预期 ELO
- v46: z ≈ +0.5 ~ +1.0 (防御保底)
- v47: z ≈ -0.3 ~ +0.5 (反镜像)
- 组合: 都是"防守类"改动, 增益基本可加但绝对值有限。z ≈ +0.5 ~ +1.2。

## 风险
- 都属"保守"型改动, 叠加后可能进一步推迟进攻 → reward 下滑。
- v46 的 emergency fallback 触发时, v47 的方向随机化可能导致 fallback 选不到 best dir。
