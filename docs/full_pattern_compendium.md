# 项目内代码总册 (full_pattern_compendium)

本文件只编目 `main.py` (v24) 与 `experiments/v2..v40` 中**已经写出来的代码**: 技巧、helper、决策链, 不做游戏规则推演, 不重复 `top_competitors_compendium.md` / `ml_rl_and_refactor.md`。截止 2026-06-03。

---

## 第一章 技巧编目 (30 条)

代号说明: A=active 当前主干在用, P=partially active 部分版本在用, X=abandoned 已经评估为劣。括号里的对子是 paired-seed 数据 (vN vs base / draws), 来源 `docs/research.md`。

### 1.1 经济类

1. **Mine economy `BUILD_MINER_NORTH` (v14→v15)** [A]
   工厂在北邻 mining_node 上直接 spawn 一个 miner, 让 miner 立即 `TRANSFORM` 成 mine。v15 vs v1 60 局 `54/42/24`。

2. **North-only mine 限制 (v15)** [A]
   v14 任意方向建 miner 在 v15 收紧为只 NORTH; v14 vs v9 `40/47/13` 太贪心, v15 vs v9 `44/42/14`。

3. **Mine build gate (v15→v24→v37)** [A]
   `build_cd<=1 ∧ factory_energy>=650 ∧ factory_gap>5 ∧ counts[MINER]<1`。v37 把 gap 阈值收到 `>6`。仅 1 个 miner 是因为 miner 不会移动。

4. **Walk onto own_mine (v15)** [A]
   若 `(factory_col, factory_row+1) in own_mines` 且可 NORTH, 工厂走上去吃 50/turn。`main.py:346-350`。

5. **Idle on own_mine when gap>10 (v15)** [A]
   工厂已经站在自己的 mine 上且 `gap>10` 时录 IDLE, 拿被动 50/turn 不动。

6. **Side miner (idle-only) (v21)** [X]
   只在 `f_move_cd>0 ∧ energy 高 ∧ gap 大` 时 EAST/WEST 建 miner。v21 vs v19 `28/17/5` 但 vs v9 `21/22/7` 不稳。

7. **Side collect 门槛收紧 (v22)** [X]
   v21 基础上 side-collect 仅在 `gap 更大 ∧ energy<900`。vs v19 `21/22/7`, 反而把 v19 head-to-head 退掉。

8. **SCOUT_DELAY_STEP = 24 (v17→v19)** [A]
   前 24 步禁建 scout, 用于 bunterrrrr 风格 mine window。`SCOUT_DELAY_STEP=24`; v19 vs v1 `62/39/19`, vs v9 `55/33/12`。

9. **Late scout energy reserve (v11)** [X]
   `step>=300 ⇒ 150 energy`, `>=400 ⇒ 250`。v11 vs v9 `38/32/30` 局部正, 但被 v19 取代。

10. **BUILD_SCOUT gap gate (v37)** [A in v37, not v24]
    `factory_gap > 4` 才允许 scout, 避免临死前花 50 能量。v37 vs v24 100 局 `44/36/20`。

11. **BUILD_MINER gap gate (v37)** [A in v37, not v24]
    miner 同 scout 也加 `gap > 6` 闸门。v39 单独保留这一项 vs v24 `38/40/22` → 仅它一个不够。

12. **Conditional BUILD_SCOUT (v40)** [X]
    在 v37 的 `gap>4` 基础上, 再放行 "无敌方工厂在 Manhattan 6 以内" 的安全空挡。online `968.2` 不及格。

13. **BUILD_WORKER energy floor 350 (v40)** [X]
    工人 spawn 净耗 400 能量, v40 把阈值从 `>=200` 抬到 `>=350` 防 energy=0 死亡。online 数据未支持。

### 1.2 位移类

14. **Jump-preferred BFS (v1)** [A]
    `bfs_jump` 在 jcd≤0 时先扩展 JUMP_*, 后扩展 WALK; 单步 2 cell 价值翻倍。整个项目的核心位移技巧。

15. **North-only jump (v37, late game)** [A in v37]
    `north_only_jump=True` 当 `factory_gap<=8`, 只在 BFS 里扩展 JUMP_NORTH, 把 20-turn cooldown 攒给紧急。v37 + 这一项是 v24→v37 涨分主因。

16. **Emergency JUMP_NORTH at gap≤2 (v1)** [A]
    `factory_gap<=2 ∧ south>0` 时优先 JUMP_NORTH, 失败再 JUMP_EAST/WEST; main.py 整段最 top-priority 分支。

17. **Emergency NORTH walk insert (v35)** [X]
    在 JUMP_NORTH 之后, JUMP_EAST/WEST 之前, 插入一个 `can_move(NORTH)` 分支; 配合 `safe_or_critical` 在 gap≤1 时允许碰撞。

18. **Fallback chain: closer-target BFS (v1)** [A]
    Fallback 1: `bfs_first_step` 目标 `row+5`, `avoid_occupied=False`, 不绕开自方 reserved/positions, 突破自堵。

19. **Fallback chain: any northward move (v1)** [A]
    Fallback 2: 顺序 NORTH/EAST/WEST 试 `can_move` + `safe_factory_action`, 拿第一个能走的。

20. **South-walk fallback (v1)** [A]
    Fallback 3: `gap<=3` 且全部 NEW 不通时, 允许 SOUTH 一步换走位。极少触发 (gap=3 且 N/E/W 全堵 + S 通)。

21. **Desperation lateral jump (v1)** [A]
    Fallback 4: `gap<=3 ∧ jcd<=0` 时按 EAST/WEST/SOUTH 顺序硬跳。烧 20-turn cooldown 换一回合。

22. **Weighted-north search (v3)** [X]
    用堆替换 BFS, 奖励北向, 罚 SOUTH。30 局 `23/26/11`, 净负, 被弃。

### 1.3 防御类

23. **Visible enemy-factory broad avoid (v6)** [X]
    禁所有走入 visible 敌工厂相邻格的动作。60 局 vs v1 `44/44/32`, online 不稳, 被收窄成 v9。

24. **Conditional collision tiebreak (v7→v9)** [A]
    `collision_tiebreak_bad` 复合条件: `gap>3 ∧ enemy support>0 ∧ (能量差或人数差不利)`; 只在不利时启用敌工厂占位。

25. **South-boundary gap guard (v9)** [A]
    `factory_gap<=3` 直接跳过整套 collision avoidance, 让逃命优先级压过对碰。

26. **Jump-only enemy factory guard (v24)** [A]
    新增 `enemy_factory_jump_threats`, 距离 `Manhattan<=4 ∧ gap>3` 内, **只**把它们应用到 `JUMP_*` 落点。修复 78529554 替线 JUMP_EAST 错落。

27. **Lateral jump guard (v26)** [X]
    在 v15 基础上, 给 `JUMP_EAST/WEST/SOUTH` 加禁。online `723.9` 显著差, 被弃。

28. **2-turn collision predictor (v40)** [X]
    `emove_cd<=2` (原 `<=1`) 也扩展敌工厂威胁。online `968.2`, 78598494 还是被 IDLE 的敌工厂当前格撞死, 见 v42 修复笔记。

29. **Adjacent-enemy-factory escape (v32)** [X]
    `escape_adjacent_enemy_factory()`: IDLE 不安全时主动选有北向收益的安全方向逃。局部表现负, 未上线。

30. **Reciprocal wall propagation (v2)** [X]
    `(c,r)` 有北墙时给 `(c,r+1)` 加南墙。20→50 局 paired 中性偏负, 弃。

### 1.4 视野 / 记忆 / 杂项

(已合入主干, 不重复编号上限)

- **Mirror-wall E↔W (v1)** [A]: `MIRROR_WALL` 表 + `(mc,r) = (width-1-c, r)` 镜像写入 `walls_mem`, 假设 maze 左右对称。
- **Optimistic fog (v1)** [A]: `get_wall` 未知 cell 返回 0, 让 BFS 大胆穿雾。
- **Persistent walls dict + purge (v1)** [A]: `_memory["walls"]` 跨 turn 保留, >2000 cells 时清理 `south-5` 以下。
- **Enemy support memory (v13)** [X]: 记住消失的敌方支援能量上限。被 v24 jump-only guard 取代。
- **Bunter phase explore (v34)** [X]: 探索式相位切换, 未通过 paired 测试。

---

## 第二章 关键函数 / 数据结构参考 (基于 main.py = v24)

### 2.1 顶层入口

- `agent(obs, config)` (L25): 暴露给 Kaggle 的入口, 包了 try/except, 异常时把所有 my_robot 设为 IDLE。
- `_agent_inner(obs, config)` (L34): 真正的决策主函数, ~440 行单函数。

### 2.2 常量与查表

- `FACTORY, SCOUT, WORKER, MINER = 0,1,2,3` (L8): obs.robots 的 type-id。
- `DIRS = ("NORTH","EAST","WEST","SOUTH")` (L9): 四方向迭代顺序, 注意 SOUTH 排在最后, 影响 fallback 偏好。
- `OFFSETS` (L10): dir → (dc, dr); NORTH 是 `(0, +1)` 即 row 增大代表北。
- `WALL_BITS` (L11): dir → bit (N=1, E=2, S=4, W=8); 与 `obs.walls[i]` 直接位与。
- `MIRROR_WALL[16]` (L15-20): import 期预算, `MIRROR_WALL[w]` = 把 E/W bit swap 后的墙编码, 给镜像继承用。
- `SCOUT_DELAY_STEP = 24` (L12): 前 24 步禁建 scout。

### 2.3 Helper 函数 (全是 `_agent_inner` 内部闭包)

- `get_wall(c, r)` (L70): `walls_mem.get((c,r), 0)`, 未知 = 0 (乐观)。被 `can_move`, `can_jump`, worker REMOVE_NORTH 判定调用。
- `can_move(c, r, d)` (L74): 边界 + 墙位检查, 不查占位; BFS 与所有 fallback 都用它。
- `can_jump(c, r, d)` (L81): 2 格落点边界 + 落点不是 `15` (全封死) 检查; emergency / desperation / `bfs_jump` 都调用。
- `action_dest(c, r, act)` (L89): 把 act 字符串解码成 (col, row) 落点; threat 集合扩展、`safe_factory_action`、`record` 都用。
- `bfs_first_step(start, goals, depth, avoid_occupied)` (L126): 普通 BFS 返回首步 dir; 用于 scout、worker、factory fallback-1。`avoid_occupied=False` 时不绕 reserved/my_positions。
- `bfs_jump(start, goals, jump_cd, depth)` (L156): jump-preferred BFS, 工厂主寻路。v37 多了 `north_only_jump` 参数。
- `record(uid, act, col, row)` (L202): 写 `actions[uid]` 并把落点登记进 `reserved`; act 是 BUILD_* 时按 "_X" 解析方向, 默认 NORTH。
- `safe_factory_action(act)` (L284): 落点不在 `enemy_factory_threats`, 且 JUMP_* 落点不在 `enemy_factory_jump_threats`。仅供工厂调用。

### 2.4 跨 turn 状态

- `_memory["walls"]: dict[(c,r) -> int]` (L48): 持久墙记忆, 跨 turn 累积; turn==0 重置整个 `_memory`。

### 2.5 每 turn 衍生量

- `my_robots / enemy_robots / enemy_factories` (L100-102): 按 player 拆分; `data[0]=type, [1]=col, [2]=row, [3]=energy, [4]=player, [5]=move_cd, [6]=jump_cd, [7]=build_cd`。
- `my_positions: dict[(c,r)→uid]` (L103): 自方占位, 用于 reserve 冲突 + emergency 跳点 occupancy check。
- `reserved: set[(c,r)]` (L104): 本 turn 已被某个 my_robot 计划占用的格; `record` 写入, BFS 读取。
- `counts[FACTORY/SCOUT/WORKER/MINER]` (L105): 单纯计数, gate BUILD_* 的次数。
- `crystals: dict[(c,r)→energy]` (L108-111): 仅 worker 寻路用; 不建 worker 时它整张表都没人查。
- `mining_nodes: set[(c,r)]` (L113-116): BUILD_MINER 的目标点集合。
- `own_mines: dict[(c,r)→data]` (L118-123): 已属于自己的矿; "walk onto own mine" 与 "idle on mine" 两个分支用。
- `factory_uid / factory_col / factory_row / factory_energy / factory_gap` (L221-233): 工厂的关键标量, gap = row - south。
- `f_move_cd / f_jump_cd / f_build_cd` (L236-238): 工厂三个 cooldown, 决定 emergency 与 fallback。
- `own_support_*` / `visible_enemy_support_*` (L240-243): support 单位的能量与数量聚合, 供 `collision_tiebreak_bad`。
- `collision_tiebreak_bad: bool` (L244-254): 完整复合条件, `enemy_factory_threats` 仅在此 True 时填充。
- `enemy_factory_threats` (L256, L258-271): 危险落点集合; 含敌工厂当前格 + 其单步 move + 其单步 jump 落点。
- `enemy_factory_jump_threats` (L257, L272-282): JUMP-only 限制集合, 与 `gap>3 ∧ Manhattan≤4` 联动。

---

## 第三章 决策链伪代码 (4 张图)

### 3.1 工厂主决策链 (`main.py:294-396`)

```text
if factory_gap <= 2 and south > 0:                          # emergency
    if jcd<=0 and can_jump(NORTH) and safe: record JUMP_NORTH
    elif jcd<=0:
        for d in (EAST, WEST):                              # lateral panic
            if can_jump and safe: record JUMP_d; break

if factory_uid not in actions:
    if build_cd<=1 and energy>=650 and gap>5 and miners<1:  # mine econ
        if north node free and can_move(NORTH):
            record BUILD_MINER_NORTH
    elif turn>=24 and spawn_ok and scouts<1 and energy>=50: # delayed scout
        record BUILD_SCOUT                                  # v37+ also gap>4
    elif f_move_cd > 1: record IDLE                         # move cooldown
    else:
        if on own_mine and gap>10: record IDLE              # mine sitter
        elif north own_mine and can_move: record NORTH      # collect step
        else:
            step = bfs_jump(target=row+20, depth=20)         # main path
            if step and not safe(step): step = None
            if not step: step = bfs_first_step(row+5, depth=10, no avoid)
            if not step: step = first safe NORTH/EAST/WEST
            if not step and gap<=3 and can SOUTH: step = SOUTH
            if not step and gap<=3 and jcd<=0:               # desperation
                step = first JUMP_EAST/WEST/SOUTH safe
            if step: record(step)
            elif spawn_ok and workers<1 and energy>=200 and gap<=4:
                record BUILD_WORKER                          # last resort
            else: record IDLE
```

### 3.2 Scout 决策链 (`main.py:398-419`)

```text
for each my scout:
    if move_cd > 1: record IDLE; continue
    goals = [(c, min(north, factory_row+8)) for c in range(width)]
    step = bfs_first_step(goals, depth=12)
    if not step or step == IDLE:                            # bfs failed
        for d in (NORTH, EAST, WEST):
            if can_move(d) and dest not in reserved/my_positions:
                step = d; break
    record(step if step and step != IDLE else IDLE)
```

### 3.3 Miner 决策链 (`main.py:421-429`)

```text
for each my miner:
    if (col,row) in mining_nodes and energy >= 100:
        record TRANSFORM                                    # build a mine
    else:
        record IDLE                                         # never moves
```

注: miner 不会移动, 因此 `BUILD_MINER_NORTH` 必须直接落在 mining_node 上, 否则就死在原地。

### 3.4 Worker 决策链 (`main.py:431-465`)

```text
for each my worker:
    if north wall present and energy >= 100:
        record REMOVE_NORTH; continue                       # break wall
    if move_cd > 1: record IDLE; continue
    worker_gap = row - south
    if worker_gap <= 4:
        target = [(factory_col, factory_row+5)]             # return to factory
    else:
        nearby = crystals within Manhattan 8
        target = sorted by distance, top 3 (or factory if empty)
    step = bfs_first_step(target, depth=10)
    if not step or step == IDLE:
        step = first NORTH/EAST/WEST not blocked
    record(step if step and step != IDLE else IDLE)
```

---

## 附录 A: 版本快速 changelog

```text
v1   public top2 jump-preferred BFS, mirror walls, emergency escape         (root v1)
v2   reciprocal wall propagation                                            X
v3   weighted best-first replaces BFS                                       X
v4   one-scout cap                                                          X
v5   max-5 scout cap                                                        X
v6   visible enemy-factory broad avoid                                      X (online 895)
v7   conditional collision-tiebreak avoid                                   base
v8   own-unit safe factory                                                  X
v9   v7 + south-boundary gap guard                                          A (online 1016)
v10  v6 + gap guard                                                         X
v11  late scout energy reserve (50/150/250 by step)                         X
v12  gap scout gate                                                         X (skipped)
v13  enemy support memory                                                   X
v14  adjacent mine economy (any-direction BUILD_MINER)                      X (greedy)
v15  north-only mine economy                                                A
v16  no-scout + north mine                                                  X (vision lost)
v17  scout delay 32                                                         partial
v18  scout delay 20                                                         partial
v19  scout delay 24 + north mine (= delay24 baseline)                       A (alt)
v20  scout delay 28                                                         X
v21  idle-only side mine                                                    X
v22  conservative side collect                                              X
v23  near enemy-factory broad avoid                                         X
v24  jump-only enemy factory guard (= current main.py)                      A (online 1133-1236)
v25  v15 + jump guard                                                       parallel
v26  lateral jump guard (E/W/S)                                             X (online 723)
v27  contact guard                                                          X
v28  resubmit v24                                                           A
v30  resubmit v24 (mainline slot)                                           A
v31  resubmit v19                                                           A (alt slot)
v32  late scroll + adjacent-factory escape                                  X
v33  targeted late patch                                                    X (research only)
v34  bunter phase explore                                                   X
v35  emergency NORTH-walk insert + critical override                        partial
v36  save-jump-for-north (broad)                                            X
v37  late save-jump + no-scout/miner at low gap                             A (online 1142)
v38  resubmit v24 as safety slot                                            A
v39  build-gate alone (no jump restriction)                                 X (proves v37 jump knob is the source)
v40  2-turn collision predictor + conditional scout + worker energy floor   X (online 968)
v41  resubmit v24 refloor                                                   A
```

---

## 附录 B: 编目中观察到的 3 个被忽视的小机会

1. **`BUILD_WORKER` 末位分支几乎死代码**: `main.py:392-394` 的 worker 兜底只在 BFS 全部失败 + `gap<=4` + `workers<1` + `energy>=200` 同时满足时触发。v37 + 主干在线样本 (>30 episodes) 里几乎没看到工人生成, 而该 elif 落地后 worker 的 `REMOVE_NORTH` 才是它唯一的实际作用。也就是说: **整个 worker class 的 BFS / 水晶寻路 / 返厂逻辑 (`main.py:431-465`) 在生产中几乎从未跑过**。`crystals` 字典也因此长期是空跑数据。

2. **`bfs_first_step` 在工厂寻路里只被当 fallback-1 用一次**: 它的 `avoid_occupied=False` 模式专门设计来突破"自方堵塞"。但工厂 fallback-1 之后还有 fallback-2/3/4 全是手写 dir 序列, 没有再调一次 `avoid_occupied=False` 的更深 BFS (e.g. depth=20 target=row+10)。换句话说: 一次"绕开自方走更远"的二级 BFS 现在没人调用, 这是个低成本的扩展位。

3. **emergency 块里的 JUMP_EAST/WEST 没有 north-only 保护**: 第 15 条技巧 (north_only_jump) 只作用于 `bfs_jump` 内部, **不**作用于 `factory_gap<=2` 的 emergency 块 (L299-307)。这意味着 v37 在 gap≤2 时仍会因为 NORTH 被堵就侧跳, 把 20-turn cooldown 烧光; v36 想全局禁止侧跳被弃, 但**emergency 块本身从未被任何 north-only 改动覆盖过**, 这是一个独立可测试的窄改动点。

---

## 附录 C: `docs/research.md` 中一项过时描述

`docs/research.md` 第 11 行写: "Root `main.py` is the current v1 baseline, copied from the strongest public package found". 这是文件最早写下时的事实。但同一份文档后面的 `Current Best Versions` 段 (L506-519) 已经说 "`main.py` is intentionally kept equal to `experiments/v24_jump_enemy_factory_avoid/main.py`", 而我读完的当前 `main.py` 也确实是 v24 (delay24 scout + jump-only guard, `SCOUT_DELAY_STEP=24` 常量在第 12 行)。新读者按 §Current Status 第 11 行去理解 "main.py = v1" 会被严重误导。同章节的 "factory pathfinding speed dominates economy" (L30) 也已被 `top_competitors_compendium` 第 1 章直接推翻 (economy 才是 rank 24→15 的主要 gap), 可一并修订。
