# W12: Route Map — Comprehensive Exploration Summary

Date: 2026-06-03
Period: 12:55 - 16:00 (~3 hours)
Base: v37_late_save_jump_no_scout (proven local optimum after 50+ experiments)
Kaggle peak: v24 1236.5, v40 1147.4

---

## 1. Overview

Today we launched 13+ agent variants across 5 architectural "schools":
- **修补派** (Patch): v57, v64, v67
- **经济派** (Economy): v63, v65, v66, v71
- **搜索派** (Search): v51, v62
- **架构派** (Architecture): v59
- **综合派** (Hybrid): v68, v69, v70, v72, v74

All evaluated against 3 baselines: v37 (our best), v24 (historical champion), top2 (Kaggle top-2).

---

## 2. Route Map — All Versions

### ✅ PROMISING ROUTES (gate-passing or strong signal)

| Route | Version | Mechanism | vs v37 160g | vs v24 160g | vs top2 160g | Kaggle | Gate |
|---|---|---|---|---|---|---|---|
| **R1 TRANSFER_NORTH** | v51 | Factory donates energy to north-adjacent support unit (280-600e band) | +0.62 | -0.25 | **+2.20** 🚀 | **1125.6** | ✅ |
| **Anti-IL Hash** | v67 | Player-asymmetric BFS order + ~23% hash-based lateral perturbation | +0.86 | **+2.27** 🚀 | +1.01 | **1131.8** | ✅ |
| **Dynamic Scout + Side Mine** | v63 | Scout energy 50/150/250 phased + idle-side mine EAST/WEST (1200e/14gap) | **+1.44** 🚀 | **+1.36** 🚀 | +1.14 | **1032.5** | ❌ no 1.7 |
| **Early Miner** 🆕 | v71 | Build first miner at 350e/gap3 instead of 650e/gap6 + miner pathfinding | **+0.70** | — | 0.00 (80g) | 703↑ | ❌ needs gate |
| **Knob1 Fix** | v57 | Enemy factory cell always unsafe (fix 78598494) | +0.91 | +0.80 | +1.28 | — | ❌ no 1.7 |

### ⚡ INTRANSITIVE SPECIALIST

| Route | Version | vs v37 | vs v24 | vs top2 | Kaggle |
|---|---|---|---|---|---|
| **Bunter Phase** | v34 | Forced-idle side mine + dynamic scout + light late rebuild | **-1.39** ❌ | +0.95 | **+2.26** 🚀 | **1071.5** |

v34 loses to v37 but crushes top2 and beats v24. Genuine intransitive agent.

### ⚠️ NEUTRAL / LOCAL SUCCESS (dead-end hybrids)

| Route | Version | vs v37 160g | Note |
|---|---|---|---|
| v64 (Knob1 conditional) | v37+only block when gap>3 | +0.25 | Neutral, improvement over v57's -0.39 |
| v46c+v44b | v37+wider jump save + miner TRANSFER | +0.89 | Positive but covered by v51 now |
| v68 (full stack) | v63+v46c+v44b combined | -0.70 | Components conflict when combined |
| v70 (v63+Knob1) | v63 + Knob1 fix | **-1.69** ❌ | Knob1 destroys v63's gain |
| v72 (v51+Knob1) | v51 + Knob1 fix | **-2.12** ❌ | Knob1 destroys v51's gain |
| v74 (early+hash) | v71 + anti-IL hash | **-0.26** | Neutral — no synergy |

**Key finding: Knob1 fix is v37-specific.** It helps v37 (+0.91) but HURTS v63 (-1.69) and v51 (-2.12). Component modifications do NOT compose linearly.

### 💀 DEAD ROUTES

| Route | Version | Mechanism | Worst axis | Verdict |
|---|---|---|---|---|
| **2-ply BFS** | v62 | Two-ply forward search | -4.17 vs v37 | Cost function fundamentally broken needs total rebuild |
| **Phase Switch** | v59 | Three-phase explicit state machine | -5.85 vs v37 | Over-engineered, confirmed across all axes |
| **K6 Miner TRANSFER** | v65 | 2-step K6 coordination (miner→factory→back) | -1.33 vs v37 | K6 conditions too rare in practice |
| **Late Worker Buffer** | v66 | Build worker at turn≥250 | -1.10 vs v37 | Wrong timing, wrong placement |
| **R1+hash on v50** | v58 | Utility container + anti-IL on v50 base | -2.05 vs v37 | v50 base was worse than v37 |
| **C1/C3/C5 data** | v60 | Data-driven rule learning | -3.49 vs v37 | Rules didn't generalize |

---

## 3. Kaggle Convergence History

```
Time   v34    v46c+v44b  v58    v57    v63     v67     v51     new v67  v71
12:55  —      600        600    600    —       —       —       —        —
13:20  940    —          1055   1052   —       —       —       —        —
13:50  1071   987        1055   1052   718     —       —       —        —
14:20  1071   987        1055   1052   1017    729     —       —        —
14:50  1071   replaced   1055   1052   1098    964     600     —        —
15:00  1071   —          1055   1052   1032↓   1071↑   744     —        —
15:10  1071   —          1055   1052   1032    1072    1125↑   —        —
15:20  1071   —          1055   1052   1032    1131    1125↑   600      600
15:35  1071   —          1055   1052   1032    1131    1125    717      703
```

**Peak scores observed:**
- v67 (old): **1174.0** → settled at **1131.8**
- v51: **1125.6** (still converging, submitted 14:46)
- v34: **1071.5** (stable)
- v63: **1098.5** → settled at **1032.5**
- v58: **1055.0** (historical)
- v57: **1052.8** (historical)

---

## 4. Gate Status — Updated

The evaluation gate: vs v37 160g z ≥ -1.0 AND any axis 160g z ≥ 1.7.

| Version | vs v37 | vs v24 | vs top2 | Axis≥1.7? | PASS? |
|---|---|---|---|---|---|
| **v51** ⭐ | +0.62 ✅ | -0.25 | **+2.20** 🚀 | **top2** | **✅** |
| **v67** ⭐ | +0.86 ✅ | **+2.27** 🚀 | +1.01 | **v24** | **✅** |
| v63 | +1.44 | +1.36 | +1.14 | ✗ none | ❌ |
| v57 | +0.91 | +0.80 | +1.28 | ✗ none | ❌ |
| v34 | -1.39 ❌ | +0.95 | +2.26 | top2 | ❌ v37 fail |

**Only v51 and v67 pass the gate.** Both are currently on Kaggle.

---

## 5. Architecture Anti-Synergy Pattern

A clear pattern emerged: **components that work individually do NOT combine.**

```
v37 (+0.91 Knob1) ────────┐
v63 (+1.44 dyn scout/side) ──┤ v70 → -1.69 ❌
v51 (+0.62 TRANSFER) ───────┼──┤ v72 → -2.12 ❌
v71 (+0.70 early miner) ────┘
v67 (+0.86 anti-IL) ────────┼──┤ v74 → -0.26 ❌
                           v69 → -0.70 ❌ (full stack)
```

Hypothesis: Each mechanism improves a specific failure mode. When combined, they fight over limited turns/energy and degrade overall performance. The agent has only ONE action per unit per turn — you can't fix all problems at once.

---

## 6. Key Takeaways

1. **Anti-IL hash (v67) is the most powerful single change**: 1174 peak, 1131 stable. Player-symmetric BFS + ~23% direction randomization is extremely effective.
2. **R1 TRANSFER_NORTH (v51) is the best specialist**: +2.20 vs top2, passes gate purely on top2 axis.
3. **Early miner (v71) is the #1 untapped opportunity**: First try at attacking the step-27 research gap achieved +0.70. Room for iteration.
4. **Hybridization consistently fails**: All combined modifications (v69, v70, v72, v74) are worse than individual components.
5. **The field is intransitive**: No single agent dominates all axes. v34 loses to v37 but beats top2. v51 beats top2 but ties v37. v67 beats v24 (+2.27) more than v37 (+0.86).
