# v52 = econ (v44b) + anti-mirror (v47)

**状态:** 占位骨架。等 v44b_transfer_only 与 v47_dirs_split 各自验证后再合并。

## 组合来源
- 基底: `experiments/v44b_transfer_only/main.py`
- 增量: `experiments/v47_dirs_split/main.py` 的"DIRS split / tie-break 扰动"段

## 合并方式
v44b 主干 + v47 在主决策树**末端 tie-break 处**的方向拆分逻辑:
1. v44b 的主决策树保持不变。
2. 找到 v47 在 `direction tie-break` 或 `random.choice` 周围的修改, 替换 v44b 同位置的代码。
3. 不要动 v47 的"已加 hash 噪声"逻辑里 v44b 没用到的字段。

## 预期 ELO
- v44b: z ≈ +1.0 ~ +1.5
- v47: z ≈ -0.3 ~ +0.5 (反 IL 中性, 但减少被对手镜像吃)
- 组合: 增益主要来自 v44b, v47 贡献 robustness。z ≈ +0.8 ~ +1.5。

## 风险
- 经济链对 tie-break 的方向变化敏感: 早 miner 可能因方向洗牌导致采矿延迟 1-2 turn。
- 若 v47 的 hash 噪声覆盖了 v44b 的早期决策, 早 miner 会被打散。
