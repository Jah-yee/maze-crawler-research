# W13: Stage 2 — New Directions & Next Generation

Based on W12 route map and 3-hour gap analysis vs top-15 (from W1-W11 research).

---

## 1. Three Confirmed Gaps (from W1-W11 Research)

| Gap | Description | Status | Best Attempt |
|---|---|---|---|
| **#1** | K6 miner TRANSFER engine | ❌ Failed (v65 -1.33) | K6 2-step coordination too rare |
| **#2** | Worker buffer (top-15 all build workers) | ❌ Failed (v66 -1.10) | Wrong timing (turn 250) |
| **#3** | First miner step 27 vs step 90+ | 🆕 **PARTIAL SUCCESS** (v71 +0.70) | Lowered energy 650→350, gap 6→3 |

**#3 is now the highest-value direction for iteration.**

---

## 2. Stage 2: Next-Generation Routes

### Route A: Early Miner Iteration (v71 → v73 → v75)
**Current: v71 at +0.70 vs v37.** The initial attempt lowered miner build threshold but the miner TRANSFER code was dead code (miner always on mining node → always TRANSFORMs first).

**v73 fix**: Made TRANSFER priority over TRANSFORM when factory_energy < 500 and miner adjacent. Also added miner pathfinding to nearest mining node.

**Next iterations (v75+):**
- Lower TRANSFORM threshold from 100 to 50 (faster mine income)
- Increase miner search range from 6 to 12 (find mining nodes further away)
- Add scout-first condition: only build miner after scout is deployed
- Try building miner WITHOUT requiring a mining node adjacent (let miner pathfind)

### Route B: Anti-IL Hash on Early Miner (v74 — failed)
v74 (v71 + v67 anti-IL hash) showed z=-0.26 at 160g. The hash perturbation interferes with the miner's delicate pathfinding.

**Alternative**: Apply anti-IL hash ONLY to the factory decision layer, not to BFS directions. Use hash to occasionally override the factory build/move decision, not the path search order.

### Route C: R1 TRANSFER_NORTH Optimization
v51 at +2.20 vs top2, 1125 Kaggle. The R1 rule only fires when counts[MINER]==0 (very early game). Could be extended to later game phases.

**Ideas:**
- R2: TRANSFER when miner exists AND factory_energy < 300 AND support unit adjacent has > 400 energy
- R3: TRANSFER between miners (miner→miner chain)
- Combine with v63's dynamic scout energy thresholds (v51 lacked this)

### Route D: Worker Buffer — Second Attempt
v66 failed at -1.10 with late worker (turn ≥ 250). Top-15 build workers early (~step 50-100).

**New approach:** Build worker BEFORE miner (at ~100 energy, step 30-50). Worker harvests crystals near factory. This provides energy income without the 300-cost of a miner.

### Route E: Anti-IL + Dynamic Scout (v63 base)
v63 had the best all-axis paired_eval consistency (+1.44 v37, +1.36 v24, +1.14 top2). v67's anti-IL hash was on clean v37. Add anti-IL hash to v63 base.

**Status**: Not attempted yet. Would test if anti-IL hash works with v63's modified factory behavior.

---

## 3. Decision Framework

### Immediate: Backfill pending experiments (~20 min)
- v73 (early miner v2 with working TRANSFER) vs v37 80g
- v71 vs top2 160g (confirm 80g z=0.00)

### Short-term: Iterate on v71 (early miner)
- Fix TRANSFER priority → test v73
- If v73 > v71, submit to Kaggle
- Try energy threshold at 250/300/400 to find optimum
- Try scout-first precondition

### Medium-term: New independent directions
- Worker buffer attempt #2 (early, not late)
- Anti-IL hash on v63 base
- R1 TRANSFER extended (later game trigger)

### Long-term: Architecture introspection
- Component anti-synergy is the fundamental obstacle
- Might need to refactor to a modular architecture where each mechanism has "slots" (e.g., "economy slot: early/standard", "combat slot: aggressive/passive")
- Or accept that one agent can't do everything → multi-agent strategy

---

## 4. Anti-Synergy Pattern — Root Cause

Every hybrid we tried was worse than components alone:

```
v63 +1.44 ─┐
v51 +0.62 ─┤ v69 → -0.70
v57 +0.91 ─┘

v63 +1.44 ─┐
v57 +0.91 ─┤ v70 → -1.69

v51 +0.62 ─┐
v57 +0.91 ─┤ v72 → -2.12

v71 +0.70 ─┐
v67 +0.86 ─┤ v74 → -0.26
```

Hypothesis: **Each improvement creates a local optimization that assumes the baseline behavior of the other systems.** When combined, they fight over the same limited resource (factory turn, energy, miner build slot).

Example: v63's side mine creation assumes factory will NOT receive early energy transfers (no R1). v51's R1 TRANSFER assumes factory WILL receive early energy. When combined, the factory gets energy from the scout but ALSO spends it on side mines, leading to energy shortage.

**Implication**: Don't combine mechanisms that compete for the same resource. Choose ONE economic strategy per agent.

---

## 5. Kaggle Strategy (as of 16:00)

| Entry | Score | Status | Recommendation |
|---|---|---|---|
| v67 (old) | 1131.8 | Replaced by new v67 | Keep as reference |
| v51 | 1125.6 | Converging (14:46→16:16) | **Keep as active** — gate passer, rising |
| v67 (new) | 717 | Just started (15:05) | **Keep** — proven 1174 ceiling |
| v71 | 703 | Just started (15:06) | **Keep** — new direction exploration |

Active Kaggle slots:
- **Slot 1**: v71 (15:06, 703↑) — new direction
- **Slot 2**: new v67 (15:05, 717↑) — proven performer

If v51's 1125 continues rising past 1132 (surpassing old v67), consider re-submitting v51 or keeping its 14:46 submission locked.

## 6. Immediate Next Steps

1. ✅ Write W12/W13 reports
2. 🔲 Run v73 (early miner v2) vs v37 80g
3. 🔲 Run v71 vs top2 160g
4. 🔲 Check v51 convergence at 16:16
5. 🔲 Decide: submit v73? Resubmit v51 with improvements?
6. 🔲 Build worker buffer attempt #2 (early worker, step 50)
