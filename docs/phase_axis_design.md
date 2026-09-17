# Phase Axis Design — `current_phase(obs, mem)`

## 0. 执行摘要

v24 没有显式 phase。factory 分支由 **5 个独立调过的 `factory_gap` 阈值** (2/3/4/5/10)
+ **1 个 step 阈值** (`SCOUT_DELAY_STEP=24`) + **3 个 `factory_energy` 阈值** (50/200/650)
拼出来, 各子系统 (emergency jump / mine build / worker last-resort / collision predict) 各自比较 gap, 边界既不 align 也没人替"末期 boundary_scroll 出口"背书。
top10 数据里 Joseph #10 死 7 个 boundary_scroll, 我们 v30 死 6 个 — 同病。
本文把 step / factory_gap / factory_energy 三轴显式合并成 4 个相位 + soft-transition flag, 让 factory/support/scoring 都从同一个 `current_phase` 读 label, 不再各自比阈值。

---

## Q1. 4 个相位 + 切换 signal

| Phase | Label | 进入条件 (按优先级 short-circuit) | 依据 |
|---|---|---|---|
| 1 | **Mine Sprint** | `step < 30` | top10 median first_miner: bunt 31 / Andrey 27 / Takahiro 29 / Hazy 33 / Joseph 32 — 4/5 落在 [27,33], 30 是 cluster 中位。compendium §2.1 |
| 2 | **Conveyor** | `30 ≤ step < 200` AND `factory_gap > 8` AND `factory_energy ≥ 300` | gap>8 = bunterrrrr 中后段稳态空间 (compendium §1.5: 该段允许 `BUILD_MINER_EAST/WEST` 侧矿)。energy ≥ 300 排除 emergency starve。step 200 是 row_200 metric 边界 |
| 3 | **Pressure** | `200 ≤ step < 400` OR `factory_gap ≤ 8` (且未触发 P4) | 反直觉发现: SOUTH 是 routine 工具 (Takahiro 89/局, Klodt 71/局)。gap ≤ 8 时 collision_tiebreak 风险拉高 (v24 line 245 已经在 gap > 3 时跑) |
| 4 | **Final Kick** | `step ≥ 400` OR `factory_gap ≤ 4` | step 400 是 top10 boundary_scroll 死亡集中段 (Joseph 7 局 step 463–467 死)。gap ≤ 4 是 v24 现行"worker 最后挣扎" + "south fallback" + "desperation jump" 的合并阈值 (v24 lines 376/381/392) |

短路顺序: P4 > P3 > P2 > P1 (即先看末期/危险, 再看正常)。soft-transition flag 在距离最近边界 ≤ 2 step 或 ≤ 1 gap 时点亮, 让 utility scoring 把 next-phase 的 action 也纳入候选。

阈值依据小结: step 30/200/400 来自 top10 first_miner 中位与 row_200/boundary_scroll 死亡集中区; gap 8/4 直接用 v24 已经在用的隐式断点 (gap>5 mine build, gap≤4 worker last-resort), 只是把分散的 5 个阈值收敛到 2 个。

---

## Q2. 每个相位的 action profile (伪代码)

**Phase 1 — Mine Sprint** (step < 30)
```
factory:    if adj mining_node visible (any of N/E/W) and energy ≥ 300:
                BUILD_MINER_<dir>           # 不再要求 gap > 5
            else: NORTH / JUMP_NORTH (open corridor)
build:      MINER yes (≤1)            SCOUT no (压住 SCOUT_DELAY_STEP)
            WORKER no                 directional miner yes
emergency:  gap ≤ 2 才触发 (按 v24 现行)
support:    无 (此时基本只有 factory)
```

**Phase 2 — Conveyor** (30 ≤ step < 200, gap > 8, energy ≥ 300)
```
factory:    walk onto own_mine -> IDLE (吃 +50/turn)
            else BUILD_MINER_E/W if 侧矿可见 (compendium §1.5 侧矿学派)
            else JUMP_NORTH proactively (corridor 开 2 格就跳)
build:      MINER yes (≤2)            SCOUT cap=1 (总量, 不再 routine)
            WORKER yes if energy ≥ 500 且 counts[WORKER] < 1
emergency:  gap ≤ 3 触发 (略松, 因为 step 还早, scroll 慢)
support:    SCOUT 推前 8 格做 vision; WORKER 拆 NORTH 墙 / 接 crystal
```

**Phase 3 — Pressure** (200 ≤ step < 400 OR gap ≤ 8)
```
factory:    JUMP_NORTH 优先于 NORTH (v24 jump-preferred 已经默认)
            允许 SOUTH/JUMP_SOUTH 当 collision_tiebreak_bad 且没北向出口
            (反直觉: Takahiro 13.4% SOUTH 行动)
build:      MINER 仅当 already-on-mining-node 且 energy ≥ 500
            SCOUT no (新建)            WORKER yes if energy ≥ 400 且 counts < 2
emergency:  gap ≤ 4 触发 (拉早 1 格, 给 jump_cd 缓冲)
support:    所有 support 朝北推 row, 不再 detour 找 crystal
```

**Phase 4 — Final Kick** (step ≥ 400 OR gap ≤ 4)
```
factory:    强制 NORTH / JUMP_NORTH; 没北路走 EAST/WEST
            禁用 BUILD_* (BUILD 一回合 = boundary_scroll 一格)
            禁用 REMOVE (除非 worker 已就位且 energy ≥ 200)
build:      全部 no
emergency:  gap ≤ 4 即拉满 (jump_cd 一好就跳)
support:    全员 IDLE 锁能量 (top10 tiebreak 看 final energy + final row)
```

---

## Q3. v24 隐式相位审计 (重点)

grep 出来的 hard-coded 阈值, 按轴归类:

| 轴 | 阈值 | 出现位置 (v24) | 语义 |
|---|---|---|---|
| step | `turn >= 24` (`SCOUT_DELAY_STEP`) | line 334 | 早期 no-scout 窗口 |
| gap | `gap <= 2` | line 294 | emergency NORTH-jump |
| gap | `gap <= 3` | line 376, 381 | south fallback / desperation jump |
| gap | `gap <= 4` | line 392 | worker last-resort |
| gap | `gap > 3` | line 245, 272 | collision tiebreak 启动 |
| gap | `gap > 5` | line 314 | 允许 BUILD_MINER_NORTH |
| gap | `gap > 10` | line 340 | factory IDLE on own_mine |
| energy | `>= 50` | line 334 | scout 起步 |
| energy | `>= 200` | line 392 | worker last-resort |
| energy | `>= 650` | line 314 | mine build |
| worker_gap | `<= 4` | line 444 | worker 回防 vs 找 crystal |

**最大发现**: gap 轴有 **5 个独立断点 (2/3/4/5/10)**, 每个断点只服务 1 个分支, 彼此没 align。
具体不一致:
- gap=4 时: collision_tiebreak 已经活 (gap>3), 但 worker last-resort 还**没**触发 (gap≤4 才触发, 这里是 ≤ vs >, off-by-one 边界);
- gap=5 时: 既允许 BUILD_MINER (gap>5 false, 不允许), 又**没**进入 emergency 相 (gap≤4 false), 也**还没**进入"舒服 IDLE" 区 (gap>10 false) — 这 4≤gap≤10 的 6 格灰区里 v24 只剩 BFS 一种行为, 没有 phase-aware 的 mine/worker 决策;
- gap>10 的 IDLE on own_mine 完全是 dead code: gap>10 时 `factory_row` 在 south + 11 以上, factory 几乎不会主动停在自己挖的矿上 (除非 BFS 把它走过去), 触发率 < 5%。

**step 轴只有 1 个阈值 (24)**, 完全没有 step ≥ 400 的"末期收尾"出口, 这正好对上 v30 的 6 个 boundary_scroll 死亡。

**结论**: 显式 phase 函数确实是真问题。**最小可行收敛** = step 轴 +2 阈值 (200, 400) + gap 轴砍到 2 阈值 (8, 4) + energy 用作 P2 准入门槛 (≥ 300)。比当前 9 个独立阈值少一半, 且把"末期收尾"补全。

---

## Q4. 推荐的 Python 实现

```python
from enum import IntEnum
from typing import NamedTuple

class Phase(IntEnum):
    MINE_SPRINT = 1
    CONVEYOR    = 2
    PRESSURE    = 3
    FINAL_KICK  = 4

class PhaseLabel(NamedTuple):
    phase: Phase
    soft_transition: bool   # True 当 ≤2 step 或 ≤1 gap 到下一相
    next_phase: Phase       # 供 utility scoring 预热

def current_phase(obs, mem) -> PhaseLabel:
    step = getattr(obs, "step", 0)
    f = mem.get("factory_state")  # {row, south, energy}; 调用方填好
    gap = f["row"] - f["south"] if f else 99
    energy = f["energy"] if f else 0

    if step >= 400 or gap <= 4:
        nxt = Phase.FINAL_KICK
        soft = False
        return PhaseLabel(Phase.FINAL_KICK, soft, nxt)
    if step >= 200 or gap <= 8:
        nxt = Phase.FINAL_KICK if (step >= 398 or gap <= 5) else Phase.PRESSURE
        soft = (step >= 398) or (gap <= 5)
        return PhaseLabel(Phase.PRESSURE, soft, nxt)
    if step >= 30 and gap > 8 and energy >= 300:
        nxt = Phase.PRESSURE if (step >= 198 or gap <= 9) else Phase.CONVEYOR
        soft = (step >= 198) or (gap <= 9)
        return PhaseLabel(Phase.CONVEYOR, soft, nxt)
    nxt = Phase.CONVEYOR if step >= 28 else Phase.MINE_SPRINT
    soft = step >= 28
    return PhaseLabel(Phase.MINE_SPRINT, soft, nxt)
```

调用方 (在 v24 `_agent_inner` 找到 factory 之后) 写入 `mem["factory_state"] = {"row": factory_row, "south": south, "energy": factory_energy}` 然后 `phase = current_phase(obs, mem)`, 之后 factory/support 分支都读 `phase.phase` 做 switch, 不再各比 gap。

---

## 风险段: 误判阶段的代价

误把 P3 当 P2 (低估 scroll): factory 还在 BUILD_MINER 时被卷死 — 这是 Joseph #10 死亡模式, ELO 代价 ~30/局。缓解: P3 入口 `gap ≤ 8` 比 v24 现行 collision 启动线 `gap > 3` 早 5 格, 缓冲足够。

误把 P4 当 P3 (低估末期): step 480 还在建 worker, BUILD 的 cooldown 让 factory 错过 JUMP_NORTH 窗口, 终局少 1–2 row, tiebreak 输 — 我们 v30 6 个 boundary_scroll 主要源头。soft_transition 在 step 398 点亮就把 BUILD 关掉, 双层防御。

误把 P1 当 P2 (太早 BUILD_SCOUT): 浪费 50 energy + 1 build cd, P1 第一矿延后, 跌进 ZERO HQR (#9) 那种"同流派但晚 14 step"的执行陷阱。代价 ~50 ELO (同 strategy class 里 14 步差距 ≈ 800 ELO 上限差距)。缓解: P1 出口需要 step ≥ 30, 比 SCOUT_DELAY_STEP=24 严, 不会更早建 scout。

误把 P2 当 P3 (过早保守): 错失侧矿建仓窗口, 经济只剩纯北流 — 退化到 v24 现行表现。代价低 (~10 ELO), 因为 v24 baseline 就在这个状态, 误判只是不进步。

整体: 误判方向不对称, **激进侧 (晚切到 P3/P4) 代价 30–50 ELO**, **保守侧 (早切到 P3/P4) 代价 ≤ 10 ELO**。所以阈值应该偏保守 — 这也是为什么 P3 入口选 `gap ≤ 8` (而不是 6) 和 P4 入口选 `step ≥ 400` (而不是 450) 的原因。
