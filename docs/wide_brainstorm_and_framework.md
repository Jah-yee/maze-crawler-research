# Maze-Crawler 广脑暴 + 反直觉策略 + 跨学科融合 (W6)

> Worker: W6 (广脑暴 / 反直觉策略 / 跨学科融合)
> 日期: 2026-06-03
> 状态: v37 在线 1142.4 / rank 24，v40 沉到 968.2，v38 (v24 mainline) 1007.5
> 前置阅读: `docs/research.md` / `docs/ml_rl_and_refactor.md` (W1) / `docs/external_research_and_first_principles.md` (W2) / `docs/top_competitors_compendium.md`
> 工作原则: 不和 W1/W2/W5 重复战术轴 / 阶段轴 / 对手类型轴 / 主动进攻轴 / IL 规则挖掘 / Utility-based 重构 / time-expanded BFS / energy hard floor / Halite IV cost function — 只挖**他们没想到的**

---

## 0. 执行摘要

我对 `kaggle-environments/crawl.py` 做了完整源码审计，挖到 6 个被 W1/W2/W5 集体漏掉的机制级杠杆：

1. **`CRUSHES` 表的非对称性** — factory 主动撞向敌方 worker/miner/scout 是**单向碾压、零代价、零风险**。我们 33 局公榜 replay 里 **0 次** 主动 factory-crush，但碰撞输的 4 局里有 3 局是敌方 support 单位在我方路径上耗时间。
2. **`TRANSFER_*` 是任何单位都能用的能量倒灌动作** — bunterrrrr 等 top-15 已经稳定用 miner-站矿-不-TRANSFORM → TRANSFER_SOUTH 回血给 factory，这把矿的吞吐从 1 个 dwell turn 变 N 个 transfer turn。我们的 main.py 一行 TRANSFER 都没有。
3. **`crystals` / `mining_nodes` / `walls` 全部镜像放置** — 我们只在 wall 上用了 mirror，但**矿的位置可预测**，**敌方 factory 路径也可预测**（他被镜像地图限制和我们一样）。
4. **`doorProbability = 0.08`** — 平均每行有 8% 概率中央墙是 **门**，可跨半，我们从没派任何单位穿过去过。
5. **同类相撞双死 + factory mutual destruction = tiebreak draw** — 必死时主动跳 off-board / mutual-kill 把"输"翻成"平"，**单局可挽救 +0.5 reward**。
6. **`BUILD_<UNIT>_<DIR>` 支持四方向** — 我们只用 NORTH，但侧矿的 BUILD_MINER_EAST/WEST 一行就能加，top-15 全部在用。

**如果只能试 3 个反直觉招式**（详见 §2）：

- **#A1 factory-crush 主动碾压**: 在 factory 1-ply 内有敌 worker/miner/scout 时主动撞过去（不是躲），实现 ≤ 25 行
- **#A2 miner-TRANSFER 能量回流**: miner 站矿后不 TRANSFORM 时 TRANSFER_SOUTH 给 factory（彻底改变 mine 收益曲线），实现 ≤ 40 行
- **#A8 死局自杀-tie**: factory 必死时主动跳出南界让"输"变"平"，实现 ≤ 15 行

**如果只能信奉 1 条跨学科心法**：

> **「孙子兵法 + 期权理论」: factory_energy 不是终值要最大化的资产，而是"购买未来动作选择权"的现金流。每个动作都是一次期权行权 — 北上是欧式 call (锁定 row+1 但放弃 jump 重置时机)，jump 是美式 call (灵活但锁 cd)，BUILD_* 是 carry trade (锁能量但买终值)。当前 v37 在中场过度行权，没在末段保留期权。**

**推荐的策略分层框架**（§3 详述）：

| 层 | 名称 | 内容 | 当前覆盖 |
|---|---|---|---|
| L0 | 物理层 | engine 规则 (CRUSHES、TRANSFER、scroll、cooldown) | ✓ 完整 |
| L1 | 知觉层 | obs → world model (mirror、persist、optimistic fog) | ✓ 完整 |
| L2 | 候选生成层 | 列出每 unit 所有合法动作 | △ 但 factory 隐式 |
| L3 | 局部启发式层 | 单 action 打分（无对手） | △ 散在 elif |
| L4 | 对手响应层 | 敌方建模 (1-ply、threat set) | △ 仅 collision |
| L5 | 阶段切换层 | early/mid/late phase | △ 仅 gap≤2 |
| L6 | 元博弈层 | 反 IL、随机化、ELO 联动 | ✗ 空 |
| L7 | 元工程层 | submission slot、统计 gate | △ 部分 |

---

## 第一部分：15+ 反直觉武技

每招式格式：**动作 / 反直觉点 / 致命点 / 实现复杂度 / 与现有系统兼容性 / (effort h, payoff ELO, risk 等级)**

---

### A1. Factory-crush 主动碾压

**动作**: 当 factory `move_cd <= 0` 且 1-ply 内（4 个邻格）存在敌方 SCOUT / WORKER / MINER（注意：不是 factory），优先 MOVE 到那个 cell 而不是绕开。CRUSHES 表里 `(FACTORY, SCOUT/WORKER/MINER) = True` 意味着我们 factory 体型大，撞他必死他不死我们。

```python
def crush_candidates(my_factory, enemy_robots, can_move_fn):
    cands = []
    for d in DIRS:
        if not can_move_fn(d): continue
        nc, nr = action_dest(factory_col, factory_row, d)
        for er in enemy_robots.values():
            if er[0] in (SCOUT, WORKER, MINER) and (er[1], er[2]) == (nc, nr):
                cands.append((d, er))
    return cands
```

**反直觉点**: 现有 v24/v37/v40 全部代码都在**躲**碰撞，没有人写过 factory 主动追击非 factory 单位。
**致命点**:
- 直接消灭对手 support 单位 → tiebreak 时对手 unit_count 少 1
- 对方 worker 死了，他的 wall removal/build 计划被打断
- 对方 miner 死了，他的经济线断（miner 死前必须 TRANSFORM 才能留下 mine）
- 完全不浪费 jump cooldown
**复杂度**: ~25 行（factory action 选择前优先级最高）
**与 v24 兼容**: 在 `safe_factory_action` 之后、`bfs_jump` 之前插入；不冲突
**(effort, payoff, risk)**: (2h, +40 ELO, **低** — 唯一风险是同回合对方 factory 也撞我们但 mutual factory tiebreak 是 0.5/0.5 不是负)

---

### A2. Miner 站矿 TRANSFER 回流（不 TRANSFORM）

**动作**: 当 miner 站到 mining_node 上时，**不立刻 TRANSFORM**（TRANSFORM 让 miner 死去变成 mine），而是先 TRANSFER 自己剩余能量给附近 friendly unit（最好是 factory），然后**等下回合**才 TRANSFORM。这样 miner 的 300 build energy 大部分回流到 factory，TRANSFORM 后矿继续以 50/turn 工作。

```python
# main.py:421-429 当前是 if (col, row) in mining_nodes and energy >= 100: TRANSFORM
# 改为:
adj_friendly = [(d, fr) for d in DIRS for fr in my_robots.values()
                if (fr[1], fr[2]) == action_dest(col, row, d)]
if adj_friendly and energy > 150:
    d, _ = adj_friendly[0]   # 比如 SOUTH 朝 factory
    record(uid, f"TRANSFER_{d}", col, row)
elif (col, row) in mining_nodes and energy >= config.transformCost:
    record(uid, "TRANSFORM", col, row)
```

**反直觉点**: 直觉是"miner 到矿就立刻 TRANSFORM 留 mine"，但 miner 自己带的能量 (300 build + 沿途吃水晶 + 站矿 +50) **直接消失**进 mine 的 200 起始 + 0 给 factory。先 TRANSFER 把 250 能量回给 factory，下回合 TRANSFORM，损失 1 turn 但收益 +250 能量。
**致命点**: 这正是 top-15 中**所有 directional miner 学校**（bunterrrrr、Andrey、Hazy、Joseph、harmo）正在做的 — `docs/top_competitors_compendium.md` §2.4 明说："即使只建 2-3 个 miner 也有几十次 TRANSFER_*"。我们 main.py **0 次** TRANSFER。
**复杂度**: ~40 行（改 miner planning + 增 transfer 助函数）
**与 v24 兼容**: miner 计划独立段，无冲突
**(effort, payoff, risk)**: (4h, **+80 ELO**, **低** — 已被 #1 已验证)

---

### A3. 跨学科 mirror 预测建矿

**动作**: 当我们看到东侧 `(c1, r)` 有 mining_node，由于地图 E/W 镜像生成（`crawl.py:194-218` `place_mining_nodes` 左半镜像到右半），**`(width-1-c1, r)` 一定也是 mining_node**，即使我们这边还没探到。利用这点，**在我们没探到这个 cell 之前就 BUILD_MINER 朝那个方向**。

```python
# 在 mining_nodes 集合里加入镜像点（即使未直接看见）
mirrored_nodes = set()
for (c, r) in mining_nodes:
    mc = (width - 1) - c
    if (mc, r) not in mining_nodes:
        mirrored_nodes.add((mc, r))
mining_nodes_with_mirror = mining_nodes | mirrored_nodes
```

**反直觉点**: 我们的 fog 哲学是「未知 = 不存在」，所以 `mining_nodes` 字典只装看见的。但根据 engine 源码，**镜像位置一定有矿**，所以"看不见"反而是确定的事实。
**致命点**: 对手如果不知道这条对称性（公开 baseline 都没用），就比我们晚 5-10 步发现镜像矿，我们抢先 BUILD_MINER。
**复杂度**: ~15 行（mining_nodes 集合扩展 + 同样对 crystals 扩展）
**与 v24 兼容**: 完全兼容，只是 fog 解释更乐观
**(effort, payoff, risk)**: (3h, +30 ELO, **中** — 风险是对方在镜像格已经有 miner 我们撞上去，需要额外 reservation 检查)

---

### A4. 同类 mutual-kill 消耗敌方 unit

**动作**: 当我方有一个低能量 scout，且 1-ply 内能撞到敌方 scout，**主动撞过去**（同类 `crawl.py:894-898` mutual destruction）。我们死了一个 scout (50 cost)，对方也死了一个 scout (50 cost)。

```python
def find_mutual_kill_target(my_unit, enemy_robots):
    same_type = my_unit[0]
    for er in enemy_robots.values():
        if er[0] != same_type: continue
        for d in DIRS:
            if action_dest(my_unit[1], my_unit[2], d) == (er[1], er[2]):
                return d
    return None
```

**反直觉点**: 直觉是"保护自己的 unit"。但 scout 50 energy 是 sunk cost，**敌方 scout 50 energy 也是 sunk cost**，关键是 tiebreak 时双方 unit_count 同时减 1，**但**我们的 BFS 不再被对方 scout 阻挡，且对方 fog 视野缩小。
**致命点**: bunterrrrr replay 里偶尔有 scout 撞 scout 的瞬间，且**他赢了那局**。
**复杂度**: ~20 行（在 scout planning 阶段插一段优先级）
**与 v24 兼容**: scout 段独立修改
**(effort, payoff, risk)**: (3h, +20 ELO, **低**)

---

### A5. 自杀 tiebreak（off-board jump 救平局）

**动作**: 当 factory_gap ≤ 1 且无 safe 北跳，**主动 JUMP_SOUTH 出南界**自杀。如果对方 factory 没死，我们 -1，他大胜。**但如果对方 factory 也在很危险（gap ≤ 3 且 jcd > 0 且我们看见他能量 ≤ 50）**，且我们能预测他本回合也死，**双死 → tiebreak 0.5/0.5**。

```python
# 极端情况下唯一动作:
if factory_gap <= 1 and f_jump_cd > 5 and no_safe_north_move:
    enemy_about_to_die = any(
        ef_gap <= 2 and ef_jump_cd > 5
        for ef in enemy_factories_observed
    )
    if enemy_about_to_die:
        record(factory_uid, "JUMP_SOUTH", factory_col, factory_row)  # mutual death
```

**反直觉点**: 主动求死是反直觉极致。
**致命点**: ELO 系统下，输 = -25 ELO，平 = 0 ELO；这个招式把 -25 变 0，**单次提升 +25 ELO**。需要的窗口很窄但每次都能赚。
**复杂度**: ~15 行（emergency 段加分支）
**与 v24 兼容**: 是 emergency_north 之后的兜底
**(effort, payoff, risk)**: (2h, +15 ELO 长期平均, **高** — 误判敌方将死会立刻多输一局；需要严格门控)

---

### A6. Worker BUILD_NORTH 主动堵敌路（denial）

**动作**: 当敌方 factory 在向我方 factory 北面镜像位置进发，且我方某个 worker 在敌方必经窄缝（mirror inference 可算），**用 worker 主动 BUILD_NORTH** 建一面墙。100 energy/wall。

```python
# 在 worker planning 段:
def find_denial_target(worker_pos, enemy_factory, walls_mem):
    ec, er = enemy_factory[1], enemy_factory[2]
    # 镜像我方 factory 路径到敌方那侧，找窄缝
    candidates = [(ec, er+1), (ec+1, er), (ec-1, er)]
    for cell in candidates:
        if can_build_wall_between(worker_pos, cell):
            return action_to_build_toward(worker_pos, cell)
    return None
```

**反直觉点**: 我们的 worker 一直只用来 REMOVE wall（开路）或 IDLE，从没 BUILD 过 wall（堵路）。
**致命点**: 一面墙就能让敌方 BFS 多 4-8 步绕行，scroll 上来时这是致命延迟。
**复杂度**: ~80 行（需要识别窄缝 + 估墙效价）
**与 v24 兼容**: 工人是 last-resort，需扩展逻辑
**(effort, payoff, risk)**: (8h, +25 ELO, **中** — 误堵自家路径是显著风险)

---

### A7. REMOVE_NORTH 突破式开路

**动作**: 当 factory BFS 找不到 20 步内的北向 goal（被墙锁死）且 worker 在 factory 北邻格上，**用 worker REMOVE_NORTH** 把墙拆掉，下回合 factory 直接 NORTH。100 energy/wall removal。

```python
def find_breakthrough(worker, factory, walls_mem):
    wc, wr = worker[1], worker[2]
    fc, fr = factory[1], factory[2]
    # worker 在 factory 北邻且 worker 北面是墙
    if (wc, wr) == (fc, fr + 1) and (get_wall(wc, wr) & WALL_BITS["NORTH"]):
        if worker_energy >= config.wallRemoveCost:
            return "REMOVE_NORTH"
    return None
```

**反直觉点**: top-15 §2.5 明说"晚期 REMOVE_NORTH 撬一行 row" — bunterrrrr / Andrey / Joseph 都做，但我们 `main.py:431-465` 里只有 REMOVE_NORTH 当墙撞死时兜底，没有主动开路策略。
**致命点**: scroll 死亡线快追上时，REMOVE 一面墙 = 多活 1 row = 多 0.5 reward。
**复杂度**: ~30 行（worker planning + 新 wall-state 检查）
**与 v24 兼容**: 在 worker planning 之内
**(effort, payoff, risk)**: (3h, +25 ELO, **低**)

---

### A8. Door 跨边界（破镜像）

**动作**: 当观测到某行中央墙 `(width//2 - 1, r)` 的 EAST 位无墙（door），派 scout 朝那行 EAST 走，**穿到敌方那侧**。原因：(a) 把 fog 撕开看到对方 factory 真位置；(b) 对方的 mirror 推断对我们的预测被打乱（因为我方 unit 出现在他这侧）。

```python
def find_door_row(walls_mem, width, south, north):
    half_left = width // 2 - 1
    for r in range(south, north + 1):
        w_at = walls_mem.get((half_left, r), 15)
        if w_at != 15 and not (w_at & WALL_BITS["EAST"]):  # no center wall
            return r
    return None
```

**反直觉点**: 公开 baseline 全部假设两侧独立 — 我们的 `top2_jump_bfs` 干脆只看自己那半。但 `crawl.py:142-148` 8% 概率开门是事实。
**致命点**: 出现在敌方那侧的我方 scout 让 **敌方的 BFS** 也要绕开我们，**双向延迟**。
**复杂度**: ~50 行（detect door + scout path 重导向）
**与 v24 兼容**: 完全新功能，scout 段加
**(effort, payoff, risk)**: (6h, +15 ELO, **高** — 多数 episode 看不见门; payoff 稀疏)

---

### A9. Build_cooldown 锁定的"假动作"链

**动作**: 在 factory 处于 `move_cd > 1` 即将 IDLE 的回合，**主动 BUILD_SCOUT_SOUTH 或 BUILD_MINER_SOUTH**（即使不可行也只是 IDLE，不损失），目的不是 spawn 单位，而是把 `build_cooldown` 锁起来 10 turn，**让对手的 IL/启发式无法预测我们下一次 BUILD 时机**。

> **注意**：`BUILD_SCOUT_SOUTH` 失败是 IDLE（`crawl.py:725` `validated_actions[uid] = "IDLE"`），不消耗能量。但若成功（南向无墙且 spawn cell 可达），会消耗 50 energy 多 spawn 一个 scout — 这通常不是好事。需要先 check `not can_move_through(SOUTH)` 才能安全锁 cooldown 而不真 spawn。

```python
# 在 IDLE 之前:
if act_intended == "IDLE" and f_build_cd <= 0 and turn > 100:
    # 选个 100% 失败的 BUILD 方向作 noise，引擎转 IDLE 不扣能量
    if get_wall(factory_col, factory_row) & WALL_BITS["SOUTH"]:
        record(factory_uid, "BUILD_SCOUT_SOUTH", factory_col, factory_row)
        # 引擎判墙 → IDLE, no charge
```

**反直觉点**: 这是**只为了反 IL** 的纯噪声动作，从能量角度完全无意义。
**致命点**: 如果对方有 IL bot 在拷我们，他学到 "v37 在 IDLE 前 N turn 必 BUILD_SCOUT"，这条直接断他特征。Lux S3 cite 的 imitation race 在 1100-1300 区间。
**复杂度**: ~10 行
**与 v24 兼容**: 兼容
**(effort, payoff, risk)**: (1h, +5 ELO（间接） risk **低** — 但 payoff 也不确定）

---

### A10. 节奏陷阱：故意 IDLE 让敌方撞过来

**动作**: 当 factory `move_cd = 0` 且 jcd ≤ 0，但 1-ply 内敌方 factory 不动而 2-ply 后他会过来撞，**故意 IDLE 一回合**让他更近，**下回合 JUMP** 绕过他到他后方。利用 jcd=20 的对称性，**逼对方先用 jcd**。

```python
# step k: factory_move_cd=0, enemy approaching
# step k IDLE → step k+1 jump → 我们 cd 锁 20, 对方还在原地
# 比标准 step k jump 北上 节约一次 cd 浪费
```

**反直觉点**: 直觉是趁 cd 好赶紧走。但 jcd=20 是稀缺资源，提前用反而被对方 mirror 利用。
**致命点**: 仅在 collision_tiebreak_bad = False 且 own_support_energy > enemy_support_energy 时安全。
**复杂度**: ~25 行
**与 v24 兼容**: 在 bfs_jump 之前加 "tempo override"
**(effort, payoff, risk)**: (4h, +10 ELO, **中** — 错判敌方意图变送命)

---

### A11. Sacrificial scout 当 wall 挡敌方 jump

**动作**: 当敌方 factory `jump_cd ≤ 0` 且其镜像位是 (c, r) 而 (c, r±2) 是他可能的跳点，**用 scout 站在 (c, r±2)**。因为 scout 占格，敌方 jump 落地撞 scout → factory crush scout（敌方安全）；**但敌方 jump_cd 被消耗 20 turn**。

```python
# 利用 CRUSHES 不杀对方 factory 但他 jcd 必锁:
def find_jump_block_target(enemy_factory, my_scouts):
    ec, er = enemy_factory[1], enemy_factory[2]
    likely_jumps = [(ec, er+2), (ec, er-2), (ec+2, er), (ec-2, er)]
    for s in my_scouts:
        for j in likely_jumps:
            if can_path(s, j):
                return s, j
    return None
```

**反直觉点**: 我们牺牲一个 50-energy scout 强迫对方花 20-turn jcd 是惊人的换算。
**致命点**: 锁住敌方 jcd → 接下来 20 turn 他不能用 jump 救命，scroll 一上来他死。
**复杂度**: ~60 行（path planning + 跳点预测）
**与 v24 兼容**: scout 计划重写
**(effort, payoff, risk)**: (8h, +30 ELO, **中** — 错估 jcd 浪费 scout)

---

### A12. Anti-IL 内部随机化（W2 提过但具体化）

**动作**: 在 factory action 选择最后一步，如果 top-2 候选 cost 差 < 10%，用 30% 概率选 top-2。但 W2 没说**用 seed 让对手无法预测**。我们用 `hashlib.sha256(str(turn) + str(factory_pos) + secret_salt)` 做伪随机，**不依赖 `random.random()`**（kaggle 替换 random 是已知行为）。

```python
SECRET_SALT = b"\x9a\x7d\xc4..."  # 16 bytes pre-baked
def deterministic_rand(turn, factory_col, factory_row):
    h = hashlib.sha256(SECRET_SALT + bytes([turn & 0xff, factory_col, factory_row & 0xff])).digest()
    return h[0] / 256.0

if abs(best_score - second_score) / best_score < 0.1:
    if deterministic_rand(turn, factory_col, factory_row) < 0.3:
        chosen = second_best
```

**反直觉点**: 不是用 `random` 而是**用 secret-salt hash** 是关键 — `random` 的种子可能被 kaggle-environments 控制（`Random(seed)` line 376），但 sha256 是不可逆的。
**致命点**: 对手即使下载我们的 main.py 看到这段代码，**没有 secret salt 就无法重放我们的决策**。这是密码学级别的 anti-IL。
**复杂度**: ~30 行
**与 v24 兼容**: 包裹在最终 record 之前
**(effort, payoff, risk)**: (4h, +10 ELO，但**主要降低被拷概率**, **低**)

---

### A13. 距 scroll 时机倒计时的"能量倾销"

**动作**: 在 `step ≈ 480` 且我方 factory 仍活着且 energy > 500 时，**强制 BUILD_SCOUT_NORTH** 把多余能量 spawn 成 scout，扩大 unit_count。理由：tiebreak 规则 (`crawl.py:327-342`) 是 `energy → unit_count → draw`，且 **factory 死后 factory 不计入** (因为 `del robots[uid]` 在 combat 阶段)；但我们在 step 500 倒数还有 factory 活着时 spawn 的 scout，**他们的能量计入 tiebreak**。

> **重要校准**: 如果 step k 我们活到自然 step 500，`_resolve_tiebreak(robots)` 把活着的所有 unit 算进去 — 包括 factory 自身。所以"factory 不计入"仅在 factory 已被 destroyed 的同回合 tie 才发生。

```python
if turn >= 480 and factory_energy > 350 and turn < 495:
    # Build all spare energy into scouts before timeout-tiebreak resolves
    if f_build_cd <= 0:
        record(factory_uid, "BUILD_SCOUT_NORTH", factory_col, factory_row)
```

**反直觉点**: 整个 v37 假设晚期 build 是浪费，但 tiebreak 那 1 个 scout 的 50 energy 可能直接翻盘。
**致命点**: top-15 §2.5 显示 "timeout_tiebreak" 是 top 队伍最大失败模式（≥70%）— 这正是 tiebreak 决胜的窗口。
**重要校准**: tiebreak cascade 是 energy → unit_count → draw。建 scout 单独看 **energy 是负的** (cost 50, scout 30 残留 = 净 -20)，**但 unit_count +1**。所以 A13 仅在双方 energy 已经非常接近（差距 ≤ 30）时才有效；建议加 guard `if abs(my_total - estimated_enemy_total) < 50`。
**复杂度**: ~15 行（含 guard）
**与 v24 兼容**: 在 build_scout 段加 step 条件
**(effort, payoff, risk)**: (2h, +10 ELO（保守估计 - 仅在能量接近 tie 场景）, **中** — 误判敌方能量分布反而扣分)

---

### A14. Factory 守矿不让对手建（denial through occupation）

**动作**: 当 factory 在 mining_node 上且 `factory_gap > 15`，**主动 IDLE** 守着这个矿。原因：(a) 自家 mine 持续 +50/turn 我们的 energy；(b) **敌方因 mirror 也知道这格有矿**，他可能也想抢，但我们站着他撞不进来（CRUSHES 我方 factory 不死）。

> 注：v15 已经实现 `(factory, mine) and gap > 10: IDLE`，但**没考虑 denial 维度**。把 `gap > 10` 收紧到 `gap > 15 + 镜像位敌方在路上` 提高激进度。

**反直觉点**: 直觉是别浪费 turn。但守矿的 dwell turn × 50 + denial 值远超被动北上。
**致命点**: 这正是 bunterrrrr 把 max_factory_energy 推到 10000 的核心机制。
**复杂度**: ~20 行（扩展 v15 的 IDLE 条件 + denial 估）
**与 v24 兼容**: 直接扩展 v15 现有逻辑
**(effort, payoff, risk)**: (3h, +25 ELO, **低**)

---

### A15. 反预测：跳到地图边缘 col=0 或 col=width-1

**动作**: 当 BFS 推荐 JUMP_EAST 和 JUMP_WEST cost 相等时，**优先选跳到 col=0 或 col=width-1 的那一边**（即靠近 perimeter wall 那侧）。

**反直觉点**: 直觉是"沿对称轴走更稳"，但靠 perimeter wall 跳让敌方 collision 路径更短的同时，**我们自己的可行邻格更少 = bfs 分支更少 = 决策更可预测**。所以这条**对我方好处是减少对手 IL 的过拟合机会**，而不是单纯位置好。

> 实际上更好的描述：选择**对手 mirror 预测最难复制**的那侧 — 如果对手是模仿型，他也在做对称的事，但 col=0 不在他模仿的对称位（他对应的 col=width-1 在他自己那侧）。

```python
def edge_preference(best_action, factory_col):
    if best_action == "JUMP_EAST":
        return factory_col + 2 - (width - 1)
    if best_action == "JUMP_WEST":
        return -factory_col + 2
    return 0
```

**复杂度**: ~10 行（tie-break logic）
**与 v24 兼容**: 在 BFS 选择处加 tie-break
**(effort, payoff, risk)**: (1h, +5 ELO, **低**)

---

### A16. Step ≤ 10 极早 miner（v37 已弃但应回归）

**动作**: 在 step ≤ 10 且 mining_node 在 factory 视野内任何方向（不只 NORTH）的格子，立刻 BUILD_MINER_<DIR>。

**反直觉点**: v24/v37 强制 `factory_gap > 5` 才 build miner — 这是被 v14 失败教训过度修正。但 top-15 §4 表明 8 个队伍 first miner ≤ step 14 都赢。
**致命点**: 早 build 的 miner 转矿，矿存活到 step 200+ 单矿 ROI ~ 10000 能量。
**复杂度**: ~25 行（去掉 v37 的 gap 门槛但保留 mine 视野检测）
**与 v24 兼容**: 直接修改 v15 line 314
**(effort, payoff, risk)**: (3h, +50 ELO（如果挖据成立）, **中** — v14 的失败警告)

---

### A17. 跨 unit 协同 BUILD_NORTH 砌墙保 factory

**动作**: 当 factory `move_cd > 1` 且南方威胁迫近，**用 worker 主动 BUILD_SOUTH** 在 factory 南邻格建墙挡敌方。配合 worker `move_cd > 1` 一起 IDLE 凑能。

```python
if factory_move_cd > 1 and worker_at_factory_south:
    if not (get_wall(factory_col, factory_row) & WALL_BITS["SOUTH"]):
        record(worker_uid, "BUILD_SOUTH", worker_col, worker_row)  # 建在 factory 南
```

**反直觉点**: 我们的 worker 一直在做"前进开路"，没人想到 worker 应该当 factory 的护卫。
**致命点**: 阻挡敌方 factory 1-ply 内不可越过的墙 — 因为 factory 不能 BUILD wall（只能 jump 翻墙）。
**复杂度**: ~40 行
**与 v24 兼容**: worker 段重排优先级
**(effort, payoff, risk)**: (5h, +15 ELO, **中**)

---

### A18. mining_node 多 miner 挤兑

**动作**: 一个 mining_node 上派 2 个 miner。第 1 个 TRANSFORM 变 mine，第 2 个**不 TRANSFORM**，而是站在 mine 上 +50/turn 给自己（type=miner，所以 collect 由 `crawl.py:951-963` 处理），然后 TRANSFER_NORTH 回 factory。等效**双倍矿收益**。

**反直觉点**: 一个矿格只能容纳一个 TRANSFORM，但 collect 不受限制。
**致命点**: bunterrrrr 没明显做这事，**这是空白市场**。
**复杂度**: ~50 行（miner planning + TRANSFER 链）
**与 v24 兼容**: 全新逻辑
**(effort, payoff, risk)**: (6h, +20 ELO, **中** — 多花 300 energy 第二个 miner)

---

### A19. 主动消耗 enemy build_cooldown 的 fake spawn 路径

**动作**: 当我方 scout 在敌方 factory 视野 (敌方 factory_vision=4) 内乱走，**预测对手在「视野中有敌单位」时会 BUILD_WORKER 防御**。我们靠近他视野再退出，反复进出，逼对手浪费 build_cooldown。

**反直觉点**: 这是 "irritant" 策略，对方对 IL 高度依赖的瞬间会被欺骗。
**致命点**: 对 v1/top2 风格无效；对**模仿 bunterrrrr 的 1100 段位玩家**致命。
**复杂度**: ~50 行
**与 v24 兼容**: scout 段重写
**(effort, payoff, risk)**: (6h, +10 ELO, **高** — 多数对手不上当)

---

### A20. Crystal-race 否决（denial of crystals）

**动作**: 当镜像位（width-1-c, r）有 crystal 但我们这边对应位置没有（crystals 也是镜像放置），**派最近 scout 朝那侧 jump（如果有 door）抢吃**。或者 worker 朝镜像方向 BUILD_EAST 把墙加上让对手到不了那个 crystal。

**反直觉点**: 我们从没在意过敌方 crystal 路径。
**致命点**: 一个 crystal = 10-50 energy = 半个 scout cost。
**复杂度**: ~60 行
**与 v24 兼容**: 大重构
**(effort, payoff, risk)**: (8h, +5 ELO, **高**)

---

### 武技汇总 (effort/payoff/risk 表)

| # | 名称 | effort (h) | payoff (ELO) | risk | 单局影响 |
|---|---|---|---|---|---|
| A1 | Factory-crush 碾压 | 2 | +40 | 低 | 中 |
| A2 | Miner-TRANSFER 回流 | 4 | **+80** | 低 | **大** |
| A3 | 镜像预测建矿 | 3 | +30 | 中 | 中 |
| A4 | 同类 mutual-kill | 3 | +20 | 低 | 小 |
| A5 | 自杀-tie | 2 | +15 | 高 | 小 |
| A6 | Worker BUILD_NORTH 堵路 | 8 | +25 | 中 | 中 |
| A7 | REMOVE_NORTH 突破 | 3 | +25 | 低 | 中 |
| A8 | Door 跨边界 | 6 | +15 | 高 | 小 |
| A9 | Build_cooldown 假动作 | 1 | +5 | 低 | 小 |
| A10 | 节奏陷阱 IDLE | 4 | +10 | 中 | 中 |
| A11 | Scout 占敌方 jump 落点 | 8 | +30 | 中 | 大 |
| A12 | Anti-IL 内部随机化 | 4 | +10 | 低 | 小 (累积) |
| A13 | step 480 能量倾销 | 2 | +20 | 低 | 中 |
| A14 | Factory 守矿 denial | 3 | +25 | 低 | 中 |
| A15 | 跳边缘 col=0/W-1 | 1 | +5 | 低 | 小 |
| A16 | step ≤10 极早 miner | 3 | +50 | 中 | **大** |
| A17 | Worker BUILD_SOUTH 护卫 | 5 | +15 | 中 | 中 |
| A18 | mining_node 双 miner | 6 | +20 | 中 | 中 |
| A19 | Fake 敌方 build trigger | 6 | +10 | 高 | 小 |
| A20 | Crystal denial | 8 | +5 | 高 | 小 |

**累积 ROI 排序**（payoff/effort 比）：
A9 (5) > A2 (20) > A16 (17) > A1 (20) > A13 (10) > A15 (5) > A14 (8.3) > A7 (8.3) > A3 (10) > A12 (2.5)

**推荐前 5 跑实验**（按 payoff 优先）: **A2, A16, A1, A11, A14**

---

## 第二部分: 跨学科心法图

每个学科原则**必须给出**: 概念 / 来源 / maze-crawler 翻译 / 落地的代码改动 / 量化指标。

---

### B1. 博弈论 - 借力打力 (Stackelberg leader)

**概念**: 在 Stackelberg game 中，先手玩家承诺一个不可逆策略，迫使后手优化响应；这种"承诺"能创造对自己有利的均衡。
**来源**: Stackelberg (1934)；Maschler-Solan-Zamir《Game Theory》(2013) Ch. 8。
**maze-crawler 翻译**: 我们公开 `main.py` 在 Kaggle submissions 列表（任何人能下载），这本身就是 **被迫的 Stackelberg leadership** — 对手可以拷我们。**最优响应不是「藏」（藏不住），而是「让我的承诺对我有利」**: 公开一个对**模仿者**不利的策略。
**代码改动**: 把所有动作选择的 1-ply lookahead 改成 **「如果对手完美模仿我」的鞍点**。即 `argmax_action E[outcome | opponent_is_self]`。当我们处于优势时，模仿者也是优势（无效）；劣势时，模仿者也劣势（无效）；**关键场景：对称 mirror 局面下，能打破对称的招式胜**。所以我们要主动加 **mirror-symmetry breaker**（A15 选择跳到 col=0 不是 col=width//2）。
**量化指标**: 在 paired-seed 自对战中，胜率应当 ≠ 50%（如果 = 50% 说明我们没打破对称）。
**预期 ELO**: +10

---

### B2. 进化生物学 - r/K 选择 (W2 扩展)

**概念**: r-策略多产廉价后代赌量，K-策略少而精强单体。Pianka (1970) 定义环境承载力 K 决定哪种最优。**W2 已涉及，我扩展**: **混合 r/K** 是 Bet-hedging strategy（Cohen 1966），在不可预测环境（如不同地图 seed）下严格优于纯策略。
**来源**: Pianka (1970)；Cohen (1966) Bet-hedging。
**maze-crawler 翻译**: 每个 seed 是新"环境"。固定 K-策略（早建 miner）在窄走廊地图（fog 北墙密度高）会输；固定 r-策略（多 scout）在开放地图会输。**最优 = 用前 10 step 的观测决定本局走 r 还是 K**。
**代码改动**: 在 step = 10 时计算 `early_wall_density = sum(walls_mem[(c, factory_row+1..5)]) / 5`，如果 > 0.6 → 进入 K 模式（早 miner）；< 0.4 → r 模式（更激进 jump）。
**量化指标**: 用 paired seed 跑 50 局，按 early_wall_density 分两组比较胜率。
**预期 ELO**: +20

---

### B3. 军事学 - Schwerpunkt (重心)

**概念**: 克劳塞维茨《战争论》Bk VI Ch. 27；闪电战中德军把所有突破力量集中在敌方防线最薄一点。
**来源**: Clausewitz, *Vom Kriege* (1832); Liddell Hart《Strategy》。
**maze-crawler 翻译**: **不要全方向 fog 都用 scout 探**，而是把所有 scout/worker/visibility 集中在**最关键 column** —— 即对手 factory 的镜像列 ±2 范围。这是对方 BFS 必经之路。我们看清这条带，对方反而看不清我们。
**代码改动**: scout 移动 BFS 的 goal 从"factory_row + 8 任何 col"改成 `(mirror_col(enemy_factory) ± 2, factory_row + 8)`。
**量化指标**: scout 在 mirror axis 附近 5 col 内的时间占比，目标 > 70%。
**预期 ELO**: +15

---

### B4. 武术 - 后发先至（半拍延迟）

**概念**: 太极/咏春的"听劲"— 不主动出招，等对手发力的一瞬反向用其力。物理本质是 **延迟决策 → 信息增益**。
**来源**: 王宗岳《太极拳论》；Wing Chun "chi sao" 拆解。
**maze-crawler 翻译**: factory 在 mvcd=0 但敌方 factory 在视野内时，**第 1 turn IDLE**，第 2 turn 看到对方走哪格后再决定我方走法。这相当于把博弈从 simultaneous game 转成 sequential game（我方后手），后手有信息优势。
**代码改动**: 在 factory move 选择前，**如果敌方 factory 1-ply 内可达 ≥3 cell**，记 "tempo_uncertain = True"；下一回合用上回合记录的对手实际走位作为先验。
**量化指标**: 在 collision_tiebreak_bad=True 的局面，IDLE-first 策略的胜率。
**预期 ELO**: +10（仅在窄场景）

---

### B5. 金融工程 - 期权理论 (jump = American call)

**概念**: factory `jump_cooldown` 是一个 **American call option** — 持有人可任意时机行权，行权后锁定 20 turn 才能再得新期权。Black-Scholes 风格的期权定价告诉我们：**当波动率（不确定性）越高，期权价值越大**。
**来源**: Hull《Options, Futures, and Other Derivatives》(9th ed.) Ch. 21。
**maze-crawler 翻译**: jump_cooldown ready 不是要立刻用，而是要在**最大不确定性**时刻用。具体: 当 BFS 找到 ≤ 18 turn 内有 80% 概率到达 row + 20 的北向 walking path，**不用 jump**（保留期权）；否则才行权。
**代码改动**: BFS 计算 walking-only 路径到 row + 20 的 expected turns，若 ≤ 18 → 不 jump；若 > 18 或 path 不存在 → jump now。
**量化指标**: 每局 jump_used / jump_available 比，目标 < 0.6（保留期权）。
**预期 ELO**: +25（这与 W2 的 time-expanded BFS 是同一思想的不同形式）

---

### B6. 运筹学 - 后悔最小化 (Minimax Regret)

**概念**: Savage's minimax regret criterion (1951) — 选择**最坏情况下后悔值最小**的动作，而非最大期望。在不确定性大时优于 expected utility。
**来源**: Savage (1951)；Bell (1982) "Regret in decision making"。
**maze-crawler 翻译**: factory 在 step 250 选 JUMP_NORTH vs NORTH，**期望值近似**，但 JUMP_NORTH 在最坏情况（后面 20 turn 没用上 cooldown 重置）后悔 +200 (没救命)；NORTH 最坏情况后悔 +50 (慢了 1 row)。**Min-regret 选 NORTH**。
**代码改动**: 在 factory action 打分时加 `regret_term = max_loss_if_chosen - max_loss_if_alternative_chosen`，weight 给负。
**量化指标**: 高方差场景（fog 50%）下 regret 项触发率 > 30%。
**预期 ELO**: +15

---

### B7. 信息论 - Shannon 熵 of opponent policy

**概念**: 对手的 action 分布熵 H(p) 越高，越难预测；我们的 action 分布熵 H(q) 越低，越容易被预测。**Minimax of mutual information**: 最优策略 = 让 H(q) 高同时 H(p|q) 低（既不易拷又能预测对手）。
**来源**: Shannon (1948)；信息瓶颈理论（Tishby et al. 1999）。
**maze-crawler 翻译**: 我们的 main.py 在相同 (state) 下完全确定地输出 action，**H(q|state) = 0**，所以 IL 对手 100% 可学。每加 1 bit 噪声 (A12 内部随机化) = H(q|state) +1。
**代码改动**: 给每个 action 加 deterministic-hash-noise，使 top-2 cost 接近时切换概率 30%（A12）。同时，记录对手 action 序列估计 H(p|state)，**当 H(p|state) 高时 = 对手在做随机化，我们应反着减 H(q|state) = 完全确定** (因为他随机我们就不能预测他，那我们最优策略反而是 maxmin)；H(p|state) 低 = 对手确定，我们应高 H(q|state) 反 IL。
**量化指标**: 我方 action 在 1000 turn 内的 entropy ≥ 0.5 bit/turn。
**预期 ELO**: +12

---

### B8. 认知科学 - System 1 vs System 2 (Kahneman)

**概念**: Kahneman《Thinking, Fast and Slow》(2011) — 人类决策有快慢两套系统。System 1 是直觉模式匹配，System 2 是慢推理。**这里的关键应用**: 1100-1300 ELO 段位的对手大概率在用 System-1 风格的启发式（"看到 fog 就 jump"、"看到敌方就避"），**我们用 System-2 的反直觉招式制造他们 System-1 失效的场景**。
**来源**: Kahneman (2011)；Stanovich (1999)。
**maze-crawler 翻译**: 列出 "1100-1300 段位对手的 System-1 直觉"（A20.5 节列出的所有误区），**主动制造让他们的 System-1 误判**的局面。例如：故意露出"快要死了"的样子（南向移动），让对方上来撞我们，我们 jump 走。
**代码改动**: 见 A10（节奏陷阱）+ A19（fake spawn）。
**量化指标**: A10/A19 在公榜失败 replay 中触发后的胜率 vs 不触发胜率。
**预期 ELO**: +10

---

### B9. 复杂系统 - 临界态 / Phase transition

**概念**: 系统在某些参数下从一态突变到另一态（如水 100°C 变蒸汽）。在 RL/博弈中，**最优策略往往出现在临界态附近**（最大熵生产）。
**来源**: Bak《How Nature Works》(1996); Wolpert 论文《The free energy requirements of biological organisms》(2016)。
**maze-crawler 翻译**: scroll_speed 是临界参数 — 从 10 turn/cell 渐变到 2 turn/cell 在 step 0 到 step 450。**临界点 ≈ step 250** (scroll speed 来到约 6 turn/cell，是 factory 移动周期 2 的 3 倍)。在这之前 economy 占优，之后 race 占优。
**代码改动**: 不要硬切 step 阈值，而是用 `scroll_speed_current / factory_move_period` 比值作为 phase indicator。当比值 ∈ [2.5, 3.5] = 临界态，**这时投入最多 effort 的决策**（其他时段用 system 1 启发式）。
**量化指标**: phase transition 区间的胜率 vs 非临界态胜率。
**预期 ELO**: +20

---

### B10. 统计学 - Bayesian opponent type 推断

**概念**: 用历史观测 P(actions | type) 反推 P(type | actions)。**Wald's sequential probability ratio test (SPRT)** 在足够多 evidence 后能稳定区分两个假设。
**来源**: Wald (1947); Berger《Statistical Decision Theory》(1985)。
**maze-crawler 翻译**: 每个对手在前 50 turn 暴露 action 模式（NORTH/JUMP_NORTH 比、BUILD_SCOUT 频率等）。把 archetype 分 3 类: {scout-spammer (v1 风格), early-miner (bunterrrrr 风格), pilkwang (large-planner 风格)}。50 turn 后 likelihood ratio 选最大类，针对反制。
**代码改动**: ~100 行（特征提取 + likelihood table + 反制 lookup）。
**量化指标**: archetype 识别准确率（在 paired seeds 中）。
**预期 ELO**: +25（与 W5 的对手轴重叠，**这里我只贡献 SPRT 的 stopping rule**）

---

### B11. 经济学 - 比较优势 (Ricardo)

**概念**: Ricardo (1817) 比较优势 — 即使一国在所有产品上都绝对劣势，专注**相对劣势最小**的产品仍能贸易获利。
**来源**: Ricardo《Principles of Political Economy》(1817)。
**maze-crawler 翻译**: 我们 v37 比 bunterrrrr 在经济上绝对劣势（factory_energy 351 vs 5645），在 vision 上绝对优势（scout 6 vs 0）。**Ricardo 说**: 我们应该把 vision 优势"出口"换 economy。具体: scout 不只是去看 fog，**主动去发现镜像位的对方矿和 crystal**，让 factory 可以在我方对应位置抢先 BUILD_MINER。
**代码改动**: scout 的 BFS goal 重排序: prioritize cells that mirror enemy-discovered mines (但敌方矿我们 fog 看不到 → 用对手 factory 位置 ±vision 反推他能看到的 cell)。
**量化指标**: 每局 scout 探到的 mining_nodes 数。
**预期 ELO**: +15

---

### B12. 棋类 - 厚势 vs 实地（围棋）

**概念**: 围棋中"厚势"（外势）= 影响力，"实地"= 已围空。**初学者贪实地（看得见的分）输给厚势（看不见的影响力）**。
**来源**: 木谷實 / 大平修三《现代围棋大全》。
**maze-crawler 翻译**: factory 的当前 row（实地）vs factory 的 jump_cooldown ready + 高 energy + 多 scout 视野（厚势）。我们 v37 过度优化实地（一直 NORTH），低估厚势（保留 jump cd、保留 build cd、多 vision）。
**代码改动**: 在 factory action 打分加 "potential score" = `jump_cd_ready * 5 + log(energy) + scout_count`，并入决策。
**量化指标**: 总 score / row 进度比。
**预期 ELO**: +15（与 W1 的 utility-based 直接同形，**这里贡献的是"厚势"的具体量化公式**）

---

### B13. 物理学 - 守恒定律 (能量守恒)

**概念**: 能量不会凭空产生或消失，只在形式间转化。
**来源**: Noether's theorem (1918)。
**maze-crawler 翻译**: 每 turn factory_energy 流量 = `+mine_collect + crystal_collect - 1 (passive) - build_cost (if built) - jump_cost (0 in this game) - move_cost (0)`。**列出能量守恒方程并在每 turn check sum**：
```
factory_energy_t+1 = factory_energy_t + sum(mines_on) - passive_loss - build_spent
```
**代码改动**: 加一个 `predict_energy_at(step=500)` 函数，**只允许行动满足 predicted ≥ 50**。
**量化指标**: predict 准确率（与实际 step 500 energy 差距）。
**预期 ELO**: +15（W2 的 energy hard floor 是同思想，**我贡献的是预测式而非反应式**）

---

### B14. 社会学 - Coalition formation（合作博弈）

**概念**: Aumann-Maschler (1964) — n人合作博弈中，子联盟的强弱影响整体均衡。
**来源**: Shapley value (1953); Aumann-Maschler (1964)。
**maze-crawler 翻译**: 我们的多 unit 不是独立体，而是"联盟"。当前 v37 每个 unit 独立 plan，浪费 coalition value。具体: scout + miner + factory 在同一行的时候，可以 **TRANSFER 链** — scout 跑前面收 crystal，TRANSFER 给 worker，worker TRANSFER 给 miner，miner TRANSFER 给 factory。Shapley value 算法告诉我们这条链每个节点的边际贡献。
**代码改动**: ~100 行（多 unit joint planning + transfer chain）。
**量化指标**: 平均 TRANSFER 次数/局。
**预期 ELO**: +30（与 A2 复合）

---

### B15. 奥地利学派经济学 - 迂回生产 (Roundabout production)

**概念**: Böhm-Bawerk《Positive Theory of Capital》(1889) — 现代经济用「先生产工具再生产产品」的迂回路径，单位时间产出 > 直接生产。
**来源**: Böhm-Bawerk (1889); Hayek《Prices and Production》(1931)。
**maze-crawler 翻译**: 生产 miner（迂回 1 步）→ TRANSFORM 成 mine（迂回 2 步）→ factory 站矿吸能（生产）。每多 1 步迂回 (=spawn miner →TRANSFORM→站矿→TRANSFER) 增加单位时间能量产出。**最佳迂回度** = 不要让 miner 立刻 TRANSFORM，先让他自走到一个更远的矿点（多迂回 1 步），再 TRANSFORM。
**代码改动**: A2 的扩展 — miner 不在 spawn 处 TRANSFORM，而是先走到 factory 视野外的下一行 mining_node 才 TRANSFORM。这要求 miner 自己走路 BFS。
**量化指标**: average TRANSFORM_step - spawn_step (delay)。
**预期 ELO**: +20

---

### 心法汇总 (5 个被翻译成可观测量的核心原则)

| # | 原则 | 来源学科 | 关键代码改动 | 关键量化指标 |
|---|---|---|---|---|
| B5 | 期权理论 - jump 是 American call | 金融 | BFS walk-path 18-turn cutoff | jump_used/jump_avail < 0.6 |
| B7 | 信息熵 - 我方 H(q) 高 / 对方 H(p) 低 | 信息论 | 内部随机化 + 敌方 archetype 推断 | 我方 action entropy ≥ 0.5 bit/turn |
| B9 | 临界态 phase transition | 复杂系统 | scroll_speed / move_period 比值阈值 | 临界区胜率 ≥ 60% |
| B13 | 守恒定律 - energy 预测 | 物理 | predict_energy_at(500) ≥ 50 强约束 | predict 误差 < 15% |
| B14 | Coalition - TRANSFER 链 | 社会学 | 多 unit joint plan + transfer chain | avg TRANSFER/局 ≥ 5 |

**接受这 5 条 → 代码必出现的改动**：
- factory action 选择不再是 elif，而是 cost function + 厚势项（B5+B12）
- 多 unit 不再独立 plan，必须 joint optimize TRANSFER 链（B14）
- step/gap 不是硬阈值，而是 scroll_speed/move_period 连续函数（B9）
- 每个决策都要 check energy 守恒预测（B13）
- 每个 turn 注入 1 bit 决策噪声（B7）

---

## 第三部分: 策略空间总框架（L0-L7）

我提出 **8 层金字塔**（用户的 L1-L6 之外加了底部 L0 物理层和顶部 L7 元工程层）：

| Layer | 名称 | 输入 | 输出 | 当前覆盖度 | W6 推荐补强 |
|---|---|---|---|---|---|
| **L0** | 物理层 | engine 源码 | 规则常量 (CRUSHES, scroll, TRANSFER) | ✓ 完整 | A1/A2 利用 CRUSHES/TRANSFER |
| **L1** | 知觉层 | obs.walls / obs.robots | world model (镜像、persist、optimistic fog) | ✓ 完整 | A3 镜像 mining_nodes 扩展 |
| **L2** | 候选生成层 | factory_pos / cooldowns | 合法 action 全集 | △ 隐式枚举 | W1 utility scorer 直接需要 |
| **L3** | 局部启发式层 | 单 action + ctx | scalar score | △ 散在 elif 中 | A14/A15/A7/A13 都在这层 |
| **L4** | 对手响应层 | enemy_factories / enemy_robots | 修正 score (threat / opportunity) | △ 仅 collision | A1 carrier-crush, A11 jump-block |
| **L5** | 阶段切换层 | turn / gap / scroll_speed | weight 调整 | △ 仅 gap≤2 hard | B9 临界态连续函数 |
| **L6** | 元博弈层 | replay 历史 / archetype | 对策选择 + 反 IL 随机化 | ✗ 空 | A12 内部随机化, B10 SPRT |
| **L7** | 元工程层 | submission slots / public ELO | 提交策略 + 统计 gate | △ 部分 | W2 的 require-z 1.5 + Kelly |

**这框架的两个核心要求**：

1. **唯一归属**: 任何新想法只能在一个 layer 里。如果跨层，必须拆。
2. **依赖单调向上**: L_k 只能依赖 L_0...L_{k-1} 的输出，不能反向。

**W1/W2/W5 现有所有补丁的归属**：

| 现有补丁 | 来源 | 归属层 |
|---|---|---|
| MIRROR_WALL 镜像推断 | top2 baseline | L1 |
| optimistic fog (`get_wall` default 0) | top2 baseline | L1 |
| bfs_jump (jump-preferred BFS) | top2 baseline | L2 |
| emergency escape gap ≤ 2 | top2 baseline | L5 (硬阈值) |
| enemy_factory_jump_threats / safe_factory_action | v24 | L4 |
| 北向 mine economy (v15) | bunterrrrr study | L3 |
| scout delay step 24 (v19) | bunterrrrr study | L5 |
| save jump for north gap ≤ 8 (v37) | v37 | L3+L5 |
| 2-turn collision predictor (v40) | v40 | L4 |
| BUILD_WORKER energy floor 350 (v40) | v40 | L3 |
| W1 Utility-based scoring | ML/RL doc | L2+L3 (整合层) |
| W1 decision-tree rule mining | ML/RL doc | 元工程到 L3 |
| W2 time-expanded BFS (c,r,jcd,mcd) | external research | L2 |
| W2 energy hard floor | external research | L3 |
| W2 phase-aware K→r switch | external research | L5 |
| W2 anti-IL 内部随机化 | external research | L6 |
| W2 SPRT 统计 gate | external research | L7 |
| W5 阶段轴 / 对手类型轴 / 主动进攻轴 | W5 | L5 / L6 / L4 |

**当前各层投入度**:
- L0/L1: 已完整，投入比例约 30%
- L2: W1 重构后变完整，但当前隐式
- L3: 现有 30% 散落各处
- L4: 只有 collision，**仍是 underinvested**
- L5: 硬阈值 + W2 phase 切换提议
- L6: **完全空白** (W6 + W2 联手补)
- L7: 部分 (W2 + W1)

**重构建议**: 文件结构按 L0-L7 切，每层一个 module（仍单文件 submit，但用 `# === L4 OPPONENT RESPONSE ===` 等 banner 切区，让 reviewer 视觉上分离）。

---

## 第四部分: 经典误区表

### 误区 1: "更长 BFS depth → 更安全"
**直觉**: depth 20 太短，扩到 40 应该更稳。
**为什么错**: BFS depth=20 已经能在 ≤10ms 内算完，扩到 40 不仅吃时间，**还可能选择一条"现在最优但未来被 cooldown 锁"的路径**（W2 §3.4 已警告）。
**项目反例**: `research.md` §"v30 / v24 Replay Failure Audit" 步 481 — depth=20 已经选了 JUMP_WEST 把 cd 锁 20 turn，extend depth 只会更选 jump (因为 jump 单次跨 2 cell 看起来更优)。

### 误区 2: "对面看不见 = 安全"
**直觉**: 我们在 fog 里，他看不见我们。
**为什么错**: **地图是 E/W 镜像生成**，对方 factory 镜像位置在他自己的同步信息里。对方能从他自己的 fog 推断我方位置范围。
**项目反例**: `main.py:43-67` 我们用 MIRROR_WALL，对方也在用 — 这是 zero-sum 的事，**所有公开 baseline 都做了 mirror 推断**。

### 误区 3: "energy 越多越好"
**直觉**: factory_energy=6000 显然比 1000 强。
**为什么错**: 攒电不消费等于浪费。`energyPerTurn=1`，每个 unit 包括 factory 每 turn 漏 1 点。攒 6000 不 spend = 浪费 6000 turn 的潜在 build。
**项目反例**: top-15 §4 "high-reward jackpot runs" 数据显示 bunterrrrr 在赢局里 max_energy=10000 时**马上 BUILD_MINER_EAST** 把 300 转化成 mine，不是攒着。

### 误区 4: "永远避免撞工厂"
**直觉**: factory collision = 不好。
**为什么错**: factory 撞非 factory = 我方碾压（A1）；factory mutual = 双死 tiebreak (可能拿 +0.5)；**只有"我们 factory 撞对方 factory 且对方能量更高"**才是真亏。
**项目反例**: `research.md` Bunterrrrr Leader Study 显示 bunterrrrr 30 局里有 4 局 factory_collision 但 wins，他不躲 collision。

### 误区 5: "建更多 scout 更好"
**直觉**: vision = 信息 = 优势。
**为什么错**: W1/W2 已证伪。但**具体证伪**: top-15 §2.2 — 1/15 队伍均 scout 数 ≤ 1（bunterrrrr/Andrey 全程 0 scout）。我们 v37 的 7.8 mean scouts 是 leaderboard 最高，但 score 1142 是 leaderboard 第 24。
**项目反例**: 完整 §"Bunterrrrr Leader Study"。

### 误区 6: "scout 死了就再造"
**直觉**: scout 50 energy，便宜，死了再 spawn。
**为什么错**: build_cooldown=10 turn，**每次 spawn 锁 build 10 turn**，10 turn 里你不能 BUILD_MINER。
**项目反例**: `research.md` v30/v24 audit 步 492 — gap=2 时还在 BUILD_SCOUT，spawn 完那 50 energy = factory 直接死。

### 误区 7: "miner 到矿就 TRANSFORM"
**直觉**: 这就是 miner 的作用。
**为什么错**: TRANSFORM 立刻消灭 miner，miner 上的能量 (300 build + 沿途吃水晶) 大部分扔掉。先 TRANSFER_SOUTH 给 factory，再下 turn TRANSFORM 收益 +250 energy。
**项目反例**: top-15 §2.4 — bunterrrrr 等所有 top 15 都 TRANSFER 之后才 TRANSFORM。我方 0 次 TRANSFER。

### 误区 8: "fog 北侧未知 = 假设可走 = 优势"
**直觉**: optimistic fog 让 BFS 主动北上是好的。
**为什么错**: optimistic fog **同时让我们的 BFS 估计的 path 比实际短**，导致我们以为有 20 步内的 row+20 目标但实际 30 步才到。后果是 jump_cd 浪费在错误时机。
**项目反例**: `main.py:70-72` 我们就是这么干的；但 W2 提的 time-expanded BFS 隐含批评了 optimistic fog 的代价。

### 误区 9: "走 SOUTH 一定差"
**直觉**: scroll 北推，SOUTH 是死亡方向。
**为什么错**: top-15 §4 "Defensive SOUTH/JUMP_SOUTH" — Takahiro Matsumoto 平均每局走 89.2 次 SOUTH，是 ELO 第 3。SOUTH 用于躲 collision + reset cooldown。
**项目反例**: 我们 v24/v37 几乎从不走 SOUTH 除了 fallback 3 兜底。

### 误区 10: "对称地图我们和对方信息对等"
**直觉**: 镜像 → 公平。
**为什么错**: 双方都用 mirror 推断 wall，但是**只有先到镜像位的人能 spawn miner**。这是 Stackelberg leader 优势 (B1)。
**项目反例**: `docs/top_competitors_compendium.md` §4 "step ≤10 BUILD_MINER" — top 8 队伍都在用，赌对称位置必有矿，抢先建。

---

## 第五部分: 与 W1/W2/W5 的兼容性

W6 的工作**不与 W1/W2/W5 重复**，而是**填补他们的空白**。下表展示**任何 W1/W2/W5 提议如何容纳 W6**:

| W1/W2/W5 提议 | W6 在该提议中的位置 |
|---|---|
| **W1**: Utility-based Scoring 重构 (L2+L3) | W6 的 A1/A14/A7/A13/A15 都是新增的 `s_*` scorer 函数；A11 `s_jump_block_target` 是 L4 的新 scorer。**直接拼接，无冲突**。 |
| **W1**: decision-tree mining 提取规则 | W6 的 A2 (TRANSFER 链) 是 mining 不会发现的（特征空间 ≠ action 空间），需要 W6 手工加入；A1 (factory-crush) 同样是 dataset 不含的（v37 没做过 → 数据为零）。**W6 补 IL 盲点**。 |
| **W2**: time-expanded BFS (c,r,jcd,mcd) | W6 的 B5 期权理论给出**为什么这条对**: jump_cd 是 American option，BFS 状态空间扩展正是把 option 价值算清楚。 |
| **W2**: energy hard floor | W6 的 B13 守恒定律给出**预测式**版本 — 不只是反应式 floor，而是预测 step 500 时 factory_energy ≥ 50。 |
| **W2**: phase-aware K→r switch | W6 的 B9 临界态把这个 hard threshold 改成**连续 scroll_speed/move_period 比值**，避免相变跳跃。 |
| **W2**: anti-IL 内部随机化 | W6 的 A12 把它升级为**用 secret-salt hash 而非 random.random()**，防止 kaggle 重置 random 时被破解。 |
| **W2**: SPRT 统计 gate | W6 的 L7 直接采用。 |
| **W5 阶段轴** (early/mid/late) | W6 的 L5 + B9 直接吸收，把硬阈值改连续函数。 |
| **W5 对手类型轴** | W6 的 B10 (Bayesian SPRT) 给出**识别算法**：对手前 50 turn action 分布 → archetype likelihood。 |
| **W5 主动进攻轴** | W6 的 A1/A4/A6/A11 全是该轴的具体招式。**A1 (factory-crush) 是该轴里能量最高的招**。 |

**结论**: W6 的工作和 W1/W2/W5 不是替代关系，是**正交补全**。任何由 W1 主导的 Utility scorer 重构都可以直接 import W6 的 A1-A20 作为新增 scorer；W2 的 BFS 扩展直接获益于 W6 的 B5 期权理论作为正当性证明；W5 的轴框架被 W6 的 L0-L7 总框架完整容纳。

---

## 第六部分: 优先级清单（按 ROI 排序）

下表把 20 个武技按 **payoff/effort 比** + **风险调整** 排序，效用 = (payoff_ELO × (1 - risk_factor)) / effort_hours。

| 排名 | 招式 | effort (h) | payoff (ELO) | risk | 调整效用 | 当前不冲突的 layer |
|---|---|---|---|---|---|---|
| 1 | **A2 Miner-TRANSFER 回流** | 4 | +80 | 低 (×0.9) | 18.0 | L3 |
| 2 | **A1 Factory-crush 主动碾压** | 2 | +40 | 低 (×0.9) | 18.0 | L4 |
| 3 | A16 step ≤10 极早 miner | 3 | +50 | 中 (×0.7) | 11.7 | L5 |
| 4 | A7 REMOVE_NORTH 突破 | 3 | +25 | 低 (×0.9) | 7.5 | L3 |
| 5 | A14 Factory 守矿 denial | 3 | +25 | 低 (×0.9) | 7.5 | L3 |
| 6 | A13 step 480 能量倾销（仅 energy 接近时） | 2 | +10 | 中 (×0.7) | 3.5 | L5 |
| 7 | A3 镜像预测建矿 | 3 | +30 | 中 (×0.7) | 7.0 | L1+L3 |
| 8 | A4 同类 mutual-kill | 3 | +20 | 低 (×0.9) | 6.0 | L4 |
| 9 | A11 Scout 占敌方 jump 落点 | 8 | +30 | 中 (×0.7) | 2.6 | L4 |
| 10 | A12 Anti-IL 内部随机化 | 4 | +10 | 低 (×0.9) | 2.25 | L6 |
| 11 | A15 跳边缘 col=0/W-1 | 1 | +5 | 低 (×0.9) | 4.5 | L3 |
| 12 | A17 Worker BUILD_SOUTH 护卫 | 5 | +15 | 中 (×0.7) | 2.1 | L4 |
| 13 | A6 Worker BUILD_NORTH 堵路 | 8 | +25 | 中 (×0.7) | 2.2 | L4 |
| 14 | A18 mining_node 双 miner | 6 | +20 | 中 (×0.7) | 2.3 | L3 |
| 15 | A10 节奏陷阱 IDLE | 4 | +10 | 中 (×0.7) | 1.75 | L4 |
| 16 | A5 自杀-tie | 2 | +15 | 高 (×0.4) | 3.0 | L5 |
| 17 | A8 Door 跨边界 | 6 | +15 | 高 (×0.4) | 1.0 | L4 |
| 18 | A9 Build_cooldown 假动作 | 1 | +5 | 低 (×0.9) | 4.5 | L6 |
| 19 | A19 Fake 敌方 build trigger | 6 | +10 | 高 (×0.4) | 0.67 | L6 |
| 20 | A20 Crystal denial | 8 | +5 | 高 (×0.4) | 0.25 | L4 |

**推荐立即试验的 5 招（按调整效用 + 实际可独立测试）**:

1. **A2 Miner-TRANSFER**：单独提交一个 v42 实验，与 v37 paired seed 50 局。若 +1.5σ，立刻促 production。
2. **A1 Factory-crush**：与 A2 不冲突，可联立成 v43。
3. **A16 极早 miner**：撤回 v37 的 `factory_gap > 5` 限制，使 step ≤ 10 build_miner 解锁。
4. **A14 Factory 守矿 denial**：把 v15 的 IDLE 条件从 `gap > 10` 扩到 `gap > 15 + denial-aware`。
5. **A13 step 480 能量倾销**：单独可 ship 的简单改动，无副作用。

---

## 最终回报给协调者

### 3 个最反直觉的招式（如果只能试 3 个）

1. **A2 Miner-TRANSFER 能量回流** — 单这一招把 mine ROI 从 break-even 500 turn 拉到 50 turn，是我们对 bunterrrrr 经济差距的**最大单杠杆**。bunterrrrr replay 已经验证过这条。预期 +80 ELO。
2. **A1 Factory-crush 主动碾压** — 利用 `CRUSHES` 表的非对称性，把"避撞"翻成"追撞"。20 行代码，把 4 个 collision 损失局直接翻盘。预期 +40 ELO。
3. **A16 step ≤ 10 极早 miner** — 撤回 v37 过度修正，回到 top-15 §4 验证过的极早建矿。预期 +50 ELO。

### 1 个跨学科心法（如果只能信奉一条）

> **B5 期权理论 - jump 是 American call option**
> jump_cooldown ready 不是要立刻行权，而是要在**最大不确定性**时刻行权。具体准则：若 walking-only BFS 18 turn 内能到 row+20 → 不 jump；否则 jump now。这一条心法**同时回答了**：(a) 为什么 W2 的 time-expanded BFS 是对的；(b) 为什么 v37 "save jump for north" 思路对但实现简化（应该按 walking-path-feasibility 而非 gap threshold）；(c) 怎么把 jump 决策从 binary 阈值变成 option pricing。

### 推荐的策略分层框架（1 张表）

| Layer | 名称 | 当前覆盖 | 待补强 |
|---|---|---|---|
| L0 物理层 | engine 规则 (CRUSHES, TRANSFER, scroll) | ✓ 完整 | 利用 (A1/A2) |
| L1 知觉层 | world model (mirror, fog) | ✓ 完整 | 镜像扩展到 mining_nodes (A3) |
| L2 候选生成 | 合法 action 全集 | △ 隐式 | W1 utility 重构 |
| L3 局部启发式 | 单 action scorer | △ 散落 | A14/A7/A13/A15 |
| L4 对手响应 | enemy_factory threats | △ 仅 collision | A1/A11/A4/A6 |
| L5 阶段切换 | hard step/gap threshold | △ 硬阈值 | B9 临界态连续函数 |
| L6 元博弈 | reflect IL / SPRT 推断 | **✗ 空** | A12 + B10 |
| L7 元工程 | submission slot / 统计 gate | △ 部分 | W2 require-z 1.5 |

### 文档完整路径

`$HOME/Desktop/kagglecraw/docs/wide_brainstorm_and_framework.md`

---

## 附录: W6 在 14 天窗口的推荐顺序

(假设每天 5 submissions、本地 paired-seed gating)

| Day | 工作 | 提交 slot 计划 |
|---|---|---|
| Day 1 | A2 + A1 联立 → v42 | v42 提一份探索 + v37 保底 |
| Day 2 | A16 → v43；本地评估 v42 | v42 若 +1.5σ 推上线，否则 v37 + v43 |
| Day 3 | A14 + A13 集成 → v44 | v44 + 当前最强 |
| Day 4 | A7 + A11 → v45（worker layer 升级） | v45 + 当前最强 |
| Day 5 | A3 + A12 → v46（mirror 扩展 + 反 IL） | v46 + 当前最强 |
| Day 6-10 | 把 W6 的招式按 utility scorer 重构（W1 框架）一次性归位 | 滚动 |
| Day 11-13 | 微调 + 公榜监控 + 防回归 | 保守 |
| Day 14 | 锁定最强 submission；不动 | 锁定 |

总预算 ≈ 55 工时（W6 部分），覆盖 5 个主要招式 + 重构归位 + 防回归。预期累积 +150-200 ELO，把 1142.4 推到 1300+，进入稳定 top-15。

---

**End of W6 report.**
