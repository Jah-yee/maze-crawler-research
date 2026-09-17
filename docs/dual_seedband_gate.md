# Dual Seed-Band Gate / 双 seed band 评测协议

## 协议

任何候选要算 gate-passing，**必须在两个独立 seed band 上都过 `z ≥ 1.7`**，**且同一条轴上**（v37 / v24 / top2 任选一条作为 gate 轴）。  
**单 seed band PASS 不算数**——80 seed × 2 sides = 160 games 在 z ∈ [+1.5, +2.5] 区间的噪声幅度 ≥ ±2.0（已实测）。  
**v37 轴下限不变**：任一轮 vs v37 z < -1.0 即立刻 DROP，不进入二轮。

> Any candidate must PASS `z ≥ 1.7` on the **same axis** in **two independent seed bands**.  
> Single-band PASS no longer qualifies. The vs-v37 floor of `z ≥ -1.0` still applies and aborts early.

---

## 噪声血证（2026-06-04 17:17）

| 候选 | 原 z (seeds 0-79) | 复测 z (seeds 80-159) | 差值 | 复测后判定 |
|---|---|---|---|---|
| v73_early_miner_v2 vs v37 | +2.14 | +0.00 | 2.14 | DROP（原 PASS 是噪声） |
| v75_v63_antimil vs v37 | +1.93 | -0.43 | 2.36（反向） | DROP |
| v76_v37_gap5_mine vs v24 | +1.43 | +0.43 | 1.00 | DROP |

三个 80g "PASS" 候选，**无一通过独立第二 seed band**。这是协议变更的直接触发。

> v51 (vs top2) 和 v67 (vs v24) 在 W12 时就已经过 160g PASS，并由 Kaggle 实盘 1223/1174 复证——它们是 "双重确认"，不在此次反例之列。

---

## 执行模板

```bash
# Round 1: seeds 0-79（baseline 轮）
.venv/bin/python scripts/paired_eval_sides.py \
  --a experiments/<CAND>/main.py \
  --b experiments/v37_late_save_jump_no_scout/main.py \
  --seeds 80 --start-seed 0 --workers 8 \
  --label "<CAND> vs v37 R1 (seeds 0-79)"

# 只有 R1 z ≥ 1.7 才跑 Round 2
.venv/bin/python scripts/paired_eval_sides.py \
  --a experiments/<CAND>/main.py \
  --b experiments/v37_late_save_jump_no_scout/main.py \
  --seeds 80 --start-seed 80 --workers 8 \
  --label "<CAND> vs v37 R2 (seeds 80-159)"
```

**判定 PASS**：R1 z ≥ 1.7 **AND** R2 z ≥ 1.7（同一条轴）。  
**判定 NOISE**：R1 PASS 但 R2 < 1.0 → DROP。  
**判定 BORDERLINE**：R1 PASS、R2 ∈ [1.0, 1.7) → 再跑 Round 3（seeds 160-239），取 R2+R3 平均 z ≥ 1.5 算 PASS，否则 DROP。

> Other axes (v24, top2) follow the same dual-band rule independently. Cross-axis combination is not allowed (a R1 v37-PASS + R2 top2-PASS does NOT count).

---

## 代价说明

每个候选的最低评测成本：
- **不通过 R1**：1 轮，160 games（~3 分钟）
- **R1 PASS + R2 DROP**：2 轮，320 games（~6 分钟）—— 这是抓噪声的关键投资
- **完整 PASS（R1 + R2 PASS）**：2 轮，320 games

旧协议（单 R1）每个候选 160 games；新协议典型成本是它的 **1-2 倍**。值得，因为 80g 单轮的假阳率太高。

---

## Don't

1. **不要**用 R1 的 PASS 单独决定提交 Kaggle——Kaggle 提交是 30 局公开赛 ELO，是非常昂贵的"R3"，没必要让噪声候选去消耗它。
2. **不要**跨轴合并（v37 R1 PASS + top2 R2 PASS）——可能是各自 seed band 的偶然偏差叠加。
3. **不要**用 `--seeds 160 --start-seed 0` 替代两个独立 80-seed 跑——单次连续 seed 区间的噪声不独立，相当于扩样而非复测。
