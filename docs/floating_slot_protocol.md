# Floating Slot Protocol / 浮动槽位协议

## 协议

**v51 是固定锚点**：`experiments/v51_r1_transfer_north/main.py`（publicScore ≈ 1223.5）始终占据 Slot A。  
**每次实验前必须先重发 v51**：先 Step 1 重锚再 Step 2 提交新实验，顺序不可颠倒。  
**2 次提交 = 1 个实验成本**：每次测试新版本固定消耗 2 个提交配额。

> v51 is the fixed anchor, always in Slot A. Re-anchor first, experiment second. 2 credits per experiment.

---

## 执行模板

```bash
# Step 1: re-anchor v51（必须先跑）
.venv/bin/kaggle competitions submit -c maze-crawler \
  -f experiments/v51_r1_transfer_north/main.py \
  -m "v51 re-anchor (before submitting <NEW>)"
sleep 30

# Step 2: 提交新实验
.venv/bin/kaggle competitions submit -c maze-crawler \
  -f experiments/<NEW>/main.py \
  -m "<NEW>: <one-line description>"
```

---

## 代价说明

每次 swap 花费 **2 个提交配额**（v51 重锚 + 新实验各一次）。  
v51 重发后需约 **30 局（~1–2 小时）** 才能爬回 1223 稳态；期间 publicScore 暂时偏低属正常，不代表退步。

---

## 当前槽位状态（2026-06-03 22:20 UTC+8 执行重锚后）

| Slot | ref | 描述 | 状态 | publicScore |
|------|-----|------|------|-------------|
| A (newest) | 53341993 | v51 re-anchor (floating_slot_policy start) | PENDING | — |
| B | 53341746 | v67 anti-IL hash | COMPLETE | 898.6（爬升中）|
| 已出窗口 | 53340058 | v51 prior | COMPLETE | 1223.5 |

---

## Don't

1. **不要先提交新实验再补 v51 重发**：逻辑倒置，还需多花一次配额纠正。
2. **不要在 v51 重发仍 PENDING 时再提交另一个实验**：会破坏协议不变量。
3. **不要假设 Kaggle 有 pin/lock 功能**：平台只保留最新 2 个，唯一保护方式是手动重发。
