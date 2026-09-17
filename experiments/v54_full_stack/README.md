# v54 = full stack (v44b + v46 + v47)

**状态:** 占位骨架。**只在 v51 / v52 / v53 至少有两个 z ≥ +0.5 时**再考虑做 v54。

## 组合来源
- 基底: `experiments/v44b_transfer_only/main.py` (经济)
- 防御层: `experiments/v46_defense_bundle/main.py` 的 final_kick + 能量地板
- 反镜像层: `experiments/v47_dirs_split/main.py` 的 DIRS split

## 合并方式
按层叠加, **每加一层都要单独 paired_eval 一次**, 否则定位不到回归源:
1. base = v44b
2. v44b + v46 防御段 → 等同 v51
3. (v44b + v46) + v47 tie-break 段 → v54
   - 强烈建议在每段周围加 `# === BEGIN vXX_segname === / # === END vXX_segname ===` magic comment, 方便回滚。

## 预期 ELO
- 单分量加权和粗估: 0.5×v44b + 0.4×v46 + 0.3×v47 ≈ +1.0 z 上限。
- 但三向叠加的非可加性 + 决策链相互踩, 实际可能只有 +0.5 ~ +1.0, 也可能负 (尤其是 v44b 与 v46 都对 BUILD 优先级动手时)。

## 风险
- 最大风险: 三方都改了"中期能量分配 / build 优先级", **互冲概率高**。
- 第二风险: 代码体积扩大 → main.py 接近 700 行, IL 对手能更准抓你的模式 (反镜像收益反而下降)。
- 落地策略: 任一中间组合 (v51/v52/v53) z < 0 → **跳过 v54**, 转去做策略上更正交的改动。
