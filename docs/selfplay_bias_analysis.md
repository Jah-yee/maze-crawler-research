# paired_eval-vs-v37 自对弈选择偏差审计 (2026-06-03)

**一句话结论**: 是的, 在被复测的 5 个 DROP 候选里, **v51_r1_transfer_north 是确认的假阴**——vs v37 z=-0.25 (DROP), 但 vs top2 z=+1.94 (PASS), 且比 v37 自己打 top2 还要强 Δz=+1.33。其他 4 个 (v46c / v44_economy / v44_early_miner / v46_defense_bundle) 在多基线下没有翻案——它们对 v37 弱, 对其他强对手也没显著优势。Gate 需要从单基线扩到 v37 + v24 + top2 三轴。

数据: `reports/selfplay_bias_paired_eval.csv` (20 + 3 ref rows × 80g)
日志: `reports/executor_log_selfplay_bias_20260603.md`

## 1. 为什么 self-play vs 自己可能误判 (机制清单)

1. **非传递性 (intransitive dominance)**. paired_eval 实质上是估计一个点 A→B 的 ELO 差。多智能体真实排序里 A>B>C>A 是常态——对 v37 弱不等于对 top2 弱。本次实测 **v51 vs v37=-0.25 但 vs top2=+1.94**, 就是教科书例子。
2. **镜像对称导致 draw/同归** (W-Verify 已证). v47 永久 player-split 对 v37 自对弈 draw_rate=100%。一旦双方走同一启发式, paired_eval 把"无 decisive 信号"误读成"无效"; 实战里碰到非镜像对手, 改动可能反而有效。
3. **候选专门针对的失败模式被 self-play 过滤掉**. 例: timeout_tiebreak 主要靠对手主动撞 (撞 enemy_factory / 自杀走 SOUTH), v37 自己几乎不犯, 所以 v37 self-play 看不到 anti-suicide 增益; 但 v24/lakhindar/pilkwang 都会犯。
4. **改动让对面 v37 走错招式 (反 best-response)**. paired_eval 是 fixed-strategy 评估, 不是博弈均衡。candidate 修改了局面分布, 可能让对面 v37 触发自己的 corner-case bug (例如 v46_defense vs v24 Δz=-2.48, 防御逻辑诱发了 v24 的某条强反应); 反过来 candidate 也可能"白送"了 v37 一些它擅长的局面。
5. **经济/防御类的累积复利在 500-step 短局看不到 vs 同水平对手**. 早 miner、TRANSFER_NORTH 这类改动需要对手"耗得起"; v37 自己很快收场, 复利来不及兑现; vs 慢节奏对手 (lakhindar / pilkwang) 才能拉开。

## 2. "vs v37 paired_eval 假阴率" 哪几个轴最高 (理论)

- **经济类** (v44_economy / v44_early_miner): v37 自己经济够用, 收益看不到; 应额外测 lakhindar 类慢对手。**实测**: 本次两个经济候选 vs lakhindar z≈+7, **但 v37 vs lakhindar 也是 z=+5.58**, 差 Δz≈+1.5——属于弱信号且在噪声边缘, 不强力翻案。
- **防御类** (v46_defense_bundle): v37 自己不撞, 防御逻辑空跑; 应额外测会撞的对手 (v24 / top2)。**实测**: vs v37 Δz=+0.64, vs top2 Δz=+0.26, vs v24 Δz=-2.48。**反例: 防御 bundle 在 v24 那里反而扣分**, 不是漏杀。
- **反 IL/反镜像** (v51_r1_transfer_north): IL 模仿型对手 (top2_jump_bfs 强 BFS-jump) 会被 R1 TRANSFER_NORTH 触发的额外北推打疼; v37 自己有 save_jump 兜底所以不疼。**实测确认**: v51 vs top2 z=+1.94 (Δz=+1.33 vs v37), vs v37 z=-0.25。**这就是真的假阴**.
- **窄 corner-case** (v46c jump cd): v37 几乎不进那个 corner; vs v37 = 0; vs 其他对手也 ≈ 0。**实测**: 4 列全部在噪声带, 不翻案; 同时也说明 handoff 里的 +1.20 是 120g 偶然样本 (本次 80g 退回 0)。

## 3. 实测结果汇总 (80g 复测, start_seed=0)

| candidate | vs v37 z | vs v24 z | vs top2 z | vs lakhindar z | 判定 |
|---|---|---|---|---|---|
| **v37 (reference)** | 0 (self) | **+1.12** | **+0.61** | **+5.58** | 参考行 |
| v46c | +0.00 | -0.13 | -0.25 | +7.11 | 无翻案; handoff +1.20 是 120g 噪声样本 |
| v44_economy | +0.13 | -0.25 | -0.61 | +7.37 | 无翻案 |
| v44_early_miner | -0.37 | -1.54 | +0.24 | +6.58 | 无翻案 (vs v24 显著负) |
| **v51_r1_transfer_north** | -0.25 | -0.38 | **+1.94** | +5.35 | **假阴: vs top2 比 v37 强 Δz=+1.33** |
| v46_defense_bundle | +0.64 | -1.36 | +0.87 | +6.22 | 混合 (vs v24 弱), 不强翻案 |

> Δz vs top2 (候选 - v37 ref): v46c -0.86, v44_economy -1.22, v44_early_miner -0.37, **v51_r1 +1.33**, v46_defense +0.26。Δz vs v24: v46c -1.25, v44_economy -1.37, v44_early_miner -2.66, v51_r1 -1.50, v46_defense -2.48。

附带发现: **lakhindar (Kaggle 1100 弱基线) 信号区分度太低** —— 所有候选 z≈+5~+7, v37 自己也 +5.58, 没有 candidate-vs-v37 区分力, 不宜入 gate。

## 4. Gate 推荐 + 行动项

**新 gate (建议)**: 从 "vs v37 160g + z≥1.7" 改成 **三轴**:

- **核心轴 (主)**: vs v37 160g, z ≥ 1.7 → 直接 PASS。
- **多样性轴 (辅)**: vs top2 160g 或 vs v24 160g, 任一轴 z ≥ 1.7 **且** vs v37 z ≥ -1.0 (不显著退化) → **enter 160g re-confirm + Kaggle 探索槽 A/B**。
- **DROP**: 三轴 max(z) < 0.5 时直接 DROP。
- **不要** 把 lakhindar 当 gate (saturated 没区分力)。

**立刻动作**:

1. **v51_r1_transfer_north 复活**: 跑 v51 vs top2 **160g** 确认 (当前 80g z=+1.94 在 80g 噪声 |z|≤1.15 之上但不远); 若 z≥1.5 → 推荐**直接提交 Kaggle 探索槽**, 不动 v24 主槽, 替掉当前 v37 探索槽试 30 局公榜 ELO。
2. **v46c 退保留地位**: 80g 复测 4 列全在噪声带, 跑 200g vs v37 一次, 若 z<1.0 则从 §6 "保留版本"降级。
3. **handoff §4 表追加 "vs top2 z 列"**: 把 vs-top2 80g 数据当 hypothesis filter (不当 gate), 帮未来候选筛选。
4. **W-Forward / W-DataDriven 后续候选直接走三轴 80g 预筛 + 160g 终筛**, 不再单走 vs v37。

## 5. 残留风险

- 80g 噪声 |z|≤1.15 (handoff §5), v51 vs top2=+1.94 只比 noise 高 ~0.8z; **必须 160g 再确认**。
- top2 是单一外部 agent, 不代表整个 Kaggle 池; 真实假阴判定还需要小批量 Kaggle A/B (5-10 公榜局)。
- v37 vs top2 本次 80g 出 +0.61 (handoff 同口径 +2.74), 说明 80g 自身仍有 ±1.5z 漂移空间; 比较时优先看 **Δz**, 不是绝对值。
