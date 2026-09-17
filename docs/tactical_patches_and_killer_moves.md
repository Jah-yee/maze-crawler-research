# 战术补丁集 + 杀招 + 自对弈多样化 (W9)

> Worker: W9
> 日期: 2026-06-03
> 基线: 主干 `main.py` = v24 (online 1129.0 / rank 24), 槽 v37 = 1142.4, v40 = 968.2
> 目标: 在不动核心架构的前提下, 把 v24 推到 v41 → v42 → v43 的具体路线图
> 必读: `top_competitors_compendium.md` (W3), `top10_deep_dive.md` (W8), `wide_brainstorm_and_framework.md` (W6), `full_pattern_compendium.md` (W4), `research.md` Experiment Log / Bunterrrrr / Replay Failure Audit 段

---

## 执行摘要 (10 行)

1. v40 失败的根因 (research.md L620-627) 是一个一行 bug: `enemy_factory_threats.add((ec, er))` 被关在 `collision_tiebreak_bad` 闸门里, 导致敌工厂"原格"在 tiebreak 有利时不被列入威胁——直接落入对方静止工厂 = 自杀。该一行是 v42 第一刀。
2. W8 决策树把 "build_worker == 0" 当成我们的指纹, 这是单条最大 ELO 缺口; W6 A1/A2/A16 是 must-include。
3. 这份补丁集列 25 条小补丁 (1 类经济 / 2 类位移 / 3 类防御 / 4 类视野 / 5 类构造), 每条 ≤ 5 行伪代码, 全部在 v24 现有 elif 链上原位插入, 不重写。
4. 6 个杀招都是 2-5 turn 序列, 触发条件具体到 `obs` 字段, 落到 `main.py` 的某段 elif; 风险全部标出。
5. 5 个自对弈多样化机制全部是**确定性非对称**——使用 `obs.player` / `obs.step` / `factory_pos` 哈希, 不引入 `random.random()` (Kaggle 重置 random 是已知行为, 见 W6 A12)。
6. v24 vs v24 平局多的根因是: 决策 100% deterministic + player-symmetric (mirror inference 让东西对称) + paired-seed 让初始 obs 完全镜像。打破对称的最低代价做法 = player-id-bias tiebreak。
7. 优先级清单按 effort/ELO 排序, top-10 全部可在 1-2 天内 ship; top-3 (D+1) 推荐: `enemy_current_cell_unconditional` (#1, 1 行) + `miner_transfer_south_before_transform` (W6 A2 同形) + `late_worker_step_300` (W8 must-include)。
8. 警示: A16 极早 miner / 主动 factory-crush / step 480 能量倾销三者都有"在自对弈胜率很好, 在 ladder 段位下沉"的历史风险 (v14, v32 教训), 必须 paired-seed gate ≥ +1.0σ 才能 ship。
9. 不与 W6 重复: W6 是策略空间扫描, W9 是把扫到的招式翻译成 v24 之上的具体行号补丁; 不与 W8 重复: W8 是 actionable list, W9 进一步把每条 actionable 拆成"条件 + 动作 + 冲突 + ELO" 四元组。
10. 验证 plan: paired-seed 50 局 vs v24/v37 + 反 imitation 测试 (用 v24 自己的代码作为 IL bot 仿真) + draw_rate 监控 (目标: 自对弈 draw_rate 从 ~20% 降到 ≤ 10%, 同时双方各自胜率仍均 50%)。

---

## 第一章: 战术小补丁集 (25 条)

格式: `patch_name` / 触发条件 / 动作 / 来源 / 冲突 / ELO。所有行号引用 `main.py` (v24)。

### 1.1 经济类

**P01. `enemy_current_cell_unconditional`** *(v42 高优先级 bug fix)*
- 触发: 任意时候有 visible enemy factory。
- 动作: `main.py:256-271` 把 `enemy_factory_threats.add((ec, er))` 一行**移出** `if collision_tiebreak_bad:` 块, 改为对所有可见敌工厂无条件添加当前格。
- 来源: `research.md` L626-627 v40 follow-up; `78598494` 是 v40 自杀进静止敌工厂。
- 冲突: 跟 v40 知 1 完全合并; 比 v40 知 1 更严格但代价为零。
- 预期 ELO: +20 ~ +40 (单局可挽救一类直接自杀)。

**P02. `miner_transfer_south_before_transform`** *(W6 A2)*
- 触发: miner 在 mining_node 上且 `energy > 150` 且工厂在 1-ply 邻格。
- 动作: `main.py:421-429` miner 段改为先 `TRANSFER_<dir_to_factory>`, 下回合再 `TRANSFORM`。
- 来源: W6 A2; W3 §2.4: bunterrrrr 等 top-15 都先 TRANSFER 后 TRANSFORM, 我们 v24 TRANSFER 总数 = 0。
- 冲突: 无 (miner 段独立); 改动后 miner 多活 1 turn = +1 IDLE 风险但 +250 energy 回流。
- 预期 ELO: +40 ~ +80。

**P03. `step_le_10_early_miner`** *(W6 A16; W8 must-include)*
- 触发: `turn <= 15` 且 `(factory_col, factory_row+1) in mining_nodes` 且 `f_build_cd <= 1`。
- 动作: `main.py:314` 的 `factory_gap > 5` 闸门在 `turn <= 15` 时跳过, 允许极早建 miner。
- 来源: W3 §4: bunt step 2, AI TOOK step 3, Andrey step 7; W8 决策树规则。
- 冲突: 跟 v37 的 `factory_gap > 6` 直接冲突, 此补丁优先 (`turn <= 15` 窗口里 gap 一定 ≤ 5)。
- 预期 ELO: +30 ~ +50 (W8 §6 #2)。

**P04. `side_miner_when_safe`** *(W3 §1.5; v21 重生)*
- 触发: `factory_gap > 8` 且 `factory_energy >= 700` 且 EAST/WEST 邻格 in mining_nodes 且 Manhattan-6 内无敌工厂。
- 动作: `main.py:314-323` 在 NORTH 分支后加 `for d in ("EAST","WEST"):` 镜像分支。
- 来源: W3 §3 Henry Solberg/harmo-miu 侧矿比 ≥ 50%; W6 A18 双 miner 的弱化版。
- 冲突: 跟 v37 `gap > 6` 兼容; 比 v21 失败教训严格 (energy 阈值 +50, 距敌检查)。
- 预期 ELO: +15 ~ +30。

**P05. `mine_econ_lower_energy_floor_when_safe`**
- 触发: `factory_gap > 10` 且 `factory_energy >= 500` (现行是 650) 且其它条件同 P03。
- 动作: `main.py:314` 把 `factory_energy >= 650` 改成 `factory_energy >= 500 if factory_gap > 10 else 650`。
- 来源: W4 编目 #3: v15→v24 一直死守 650, 但 W3 数据 bunt 在 energy 1000 时已经建 miner。
- 冲突: 跟 P03 协同 (P03 在更早 step, 此条在更安全 gap); 互不重叠。
- 预期 ELO: +10 ~ +20。

**P06. `walk_onto_north_mine_extended_gap`**
- 触发: `(factory_col, factory_row+1) in own_mines` 且 `can_move(NORTH)` 且 `factory_gap > 6` (现行 > 10)。
- 动作: `main.py:345-350` 把走上自家 mine 的 gap 条件从 > 10 放宽到 > 6 (跟踏 mine 收 +50/turn 抵消移动风险)。
- 来源: W4 编目 #4 当前过保守; W3 §1 bunt mine ROI 关键。
- 冲突: 跟 P03/P05 协同。
- 预期 ELO: +5 ~ +15。

**P07. `idle_on_own_mine_denial_aware`** *(W6 A14)*
- 触发: 工厂已在 own_mine 上 + `factory_gap > 15` + 该 mine 的镜像位 (width-1-c, r) 在 enemy 路径上。
- 动作: `main.py:340-341` 现行 `gap > 10: IDLE` 紧 (新增 denial 维度), 把 gap 阈值收紧到 `> 15 + mirror_in_enemy_path`。
- 来源: W6 A14; bunt max_energy = 10000 的核心机制。
- 冲突: 跟 P06 不重叠 (P06 是走上去, P07 是站稳); 互补。
- 预期 ELO: +15 ~ +25。

**P08. `undirected_build_miner_when_factory_on_node`** *(Takahiro 风格)*
- 触发: 工厂自己站在 mining_node 上 (rare 但出现过) 且 `f_build_cd <= 1` 且 `counts[MINER] < 1`。
- 动作: 在 P03 分支前加 `if (factory_col, factory_row) in mining_nodes: record(BUILD_MINER)` (注意是无方向)。
- 来源: W3 §1.5 Takahiro 100% miner 用 BUILD_MINER 无方向, 落地在 factory 格上。
- 冲突: 跟 P03/P04 互斥但优先级最高 (代价最低)。
- 预期 ELO: +5 ~ +15 (触发频率低但局内单局收益大)。

### 1.2 工厂位移类

**P09. `emergency_block_respect_north_only`**
- 触发: emergency 段 (`factory_gap <= 2`) 且 NORTH 不可 walk。
- 动作: `main.py:294-307` emergency 块的 lateral JUMP_EAST/WEST 加一层 "if walking NORTH 在 5 turn 内有可达 row+5 的 path 就不侧跳" 检查。
- 来源: W4 附录 B-3: emergency 块的 lateral jump 没有 north-only 保护; research.md L558 v30 78569976 step 481 jump_west 烧 jcd 20 turn 是这个原因。
- 冲突: 跟 v37 的 `north_only_jump` 互补 (v37 只管 BFS 段, emergency 段独立)。
- 预期 ELO: +15 ~ +30。

**P10. `lateral_south_for_cooldown_reset`** *(W3 §1.5; B5 期权)*
- 触发: `f_jump_cd > 8` 且 `f_move_cd <= 0` 且 `factory_gap > 12` 且当前 BFS 找不到 18 步内的 row+20 path。
- 动作: 在 fallback 链之前插一段 "if 上述条件: 主动 walk SOUTH 一步" (走 SOUTH 可让 jcd 在 next round 自然减少, 同时给对手时间犯错)。
- 来源: W3 §1.5: Takahiro 89 SOUTH/局; W6 B5 期权理论。
- 冲突: 跟 v37 不冲突 (v37 的 SOUTH 仅 fallback-3); 但需要严格 gap > 12 防止 scroll 杀。
- 预期 ELO: +5 ~ +15 (窗口窄但单触发收益高)。

**P11. `edge_jump_tiebreak`** *(W6 A15)*
- 触发: BFS 给出 JUMP_EAST 和 JUMP_WEST cost 相等。
- 动作: `bfs_jump` 选取时, tie-break 优先选跳到接近 `col=0` 或 `col=width-1` 的那一侧 (利用 `obs.player` 决定哪边偏好 = 自动打破镜像对称, 配合 §3 D02)。
- 来源: W6 A15。
- 冲突: 与 §3 player-asymmetric tiebreak (D02) 强协同; 与 v37 不冲突。
- 预期 ELO: +5 ~ +10。

**P12. `fallback_5_deeper_bfs_no_avoid`** *(W4 附录 B-2)*
- 触发: fallback-1 (depth=10, row+5) 失败之后。
- 动作: `main.py:362-366` 之后加 fallback-1.5: `bfs_first_step(closer_goals=row+10, depth=15, avoid_occupied=False)` 二级 BFS。
- 来源: W4 附录 B-2 指出 `avoid_occupied=False` 模式只被用一次; 二次调用免费扩展搜索。
- 冲突: 跟原 fallback chain 顺序兼容, 仅插一层不替换。
- 预期 ELO: +3 ~ +10。

### 1.3 防御类

**P13. `crushes_active_attack_non_factory`** *(W6 A1)*
- 触发: `f_move_cd <= 0` 且 1-ply 邻格存在敌方 SCOUT/WORKER/MINER (不是 FACTORY)。
- 动作: 在 `mine_build_action` 检查之前插入 crush 优先级最高分支: `record(factory_uid, dir_to_enemy_support_cell)`。
- 来源: W6 A1; CRUSHES 表 factory vs support = 单向碾压零代价。
- 冲突: 必须把 `safe_factory_action` 临时关掉这一格 (因为我们要落进对方 unit 格), 但仍要 check 落格不是敌 factory 当前格 (跟 P01 协同)。
- 预期 ELO: +20 ~ +40。

**P14. `scout_mutual_kill_when_low_energy`** *(W6 A4)*
- 触发: 我方 scout 能量 ≤ 30 且 1-ply 邻格有敌方 scout。
- 动作: scout 段 (`main.py:398-419`) 开头加: `for d in DIRS: if dest == enemy_scout_pos: record(uid, d); break`。
- 来源: W6 A4。
- 冲突: 跟 scout BFS 互斥但优先级更高; 不动 worker/factory。
- 预期 ELO: +10 ~ +20。

**P15. `worker_remove_north_breakthrough`** *(W6 A7)*
- 触发: worker 在 factory 北邻格上且 `(c, r)` 北墙存在且 worker_energy >= 100。
- 动作: `main.py:437-438` 的 REMOVE_NORTH 已经覆盖; 但新增"主动召唤"—— factory IDLE 之前 if 北墙挡死路且有 worker 在 spawn 区, 优先 BUILD_WORKER (P21 协同)。
- 来源: W6 A7; W3 §4 top-15 普遍 REMOVE 晚期撬一行。
- 冲突: 与 P21 (build_worker) 链式; 跟 v40 worker energy floor 350 兼容。
- 预期 ELO: +10 ~ +20。

**P16. `anti_ram_when_mvcd_high`**
- 触发: `f_move_cd >= 2` 且任一可见敌工厂 Manhattan ≤ 2 且其 `move_cd <= 1`。
- 动作: 当前 `main.py:337-338 elif f_move_cd > 1: record IDLE` 直接 IDLE; 此补丁在 IDLE 之前先尝试: 若有 worker 可 BUILD_SOUTH 在 factory 南邻就建墙 (跟 P17 协同), 否则 IDLE 不变。
- 来源: v37 online 真实 loss pattern (research.md L582); 是 v40 想修但修错了的场景。
- 冲突: 不冲突, 是被动防御; 主要协同 P17。
- 预期 ELO: +10 ~ +20。

**P17. `worker_build_south_guard`** *(W6 A17)*
- 触发: factory `move_cd >= 2` (即将 IDLE) 且某 worker 在 factory 南邻格且 factory 南向无墙且敌工厂南向 ≤ 4 cell。
- 动作: worker 段插入: `record(worker_uid, "BUILD_SOUTH")` 给 factory 加一面南墙挡敌方撞击。
- 来源: W6 A17; factory 不能 BUILD wall, 必须 worker 干。
- 冲突: 跟 P16 协同; 跟 worker REMOVE 互斥 (按优先级 REMOVE > BUILD_SOUTH guard)。
- 预期 ELO: +5 ~ +15。

**P18. `suicide_tie_when_dead`** *(W6 A5)*
- 触发: `factory_gap <= 1` 且 NORTH/JUMP_NORTH 全死 且某可见敌工厂 `gap <= 2 + jcd > 5`。
- 动作: emergency 段最后兜底插入 `JUMP_SOUTH` 出南界自杀, 期望对面同回合也死 = tiebreak 0.5。
- 来源: W6 A5。
- 冲突: 必须严格 gate (`gap <= 1 + 4 个条件同时满足`), 防止把"输 1"变"必输 1 反送一个 jcd"。
- 预期 ELO: +5 ~ +15 (长期平均, 单局收益 +25 ELO 但触发率 < 5%)。

### 1.4 视野类

**P19. `mirror_extend_to_mining_nodes_crystals`** *(W6 A3)*
- 触发: 任意时候。
- 动作: `main.py:113-116` `mining_nodes` 构造完毕后, 追加: `for (c,r) in list(mining_nodes): mining_nodes.add(((width-1)-c, r))`; crystals 同理。
- 来源: W6 A3; engine 源码 `place_mining_nodes` 左右镜像生成。
- 冲突: 改变 BFS goal 集合, 可能引发原本应该 BUILD_MINER 但镜像格已有敌 miner 占用——加 `if not in enemy_robots_positions` 守卫。
- 预期 ELO: +10 ~ +25。

**P20. `last_step_scout_probe_uncovered_cell`**
- 触发: scout `energy <= 40` 且即将死亡 (估计还能走 ≤ 3 步) 且周围 vision 范围内有未探格。
- 动作: scout 段加最后探查: BFS goal 改为 "本帧 fog 中尚未持久化的 cell" 而非 factory_row+8。
- 来源: 自挖, 利用 W4 已有 `walls_mem` 持久化; v37/v24 scout 死前都在做无意义 NORTH。
- 冲突: 跟 P14 (mutual kill) 互斥, P14 优先 (energy ≤ 30 时 kill 优先, 30 < energy ≤ 40 探查)。
- 预期 ELO: +5 ~ +15。

### 1.5 构造类

**P21. `build_worker_step_300_gap8`** *(W8 must-include #1)*
- 触发: `turn >= 300` 且 `factory_gap >= 8` 且 `factory_energy >= 500` 且 `counts[WORKER] == 0` 且 `counts[MINER] >= 1`。
- 动作: `main.py:330-336` scout 分支之后加 worker 分支: `record(factory_uid, "BUILD_WORKER_NORTH")`。
- 来源: W8 §6 #1 ROI 排名第一; W8 §4.2: top10 100% 建 worker, 我们 0/44 局。
- 冲突: 跟 v40 的 worker energy floor 350 协同 (此补丁是 500 更严); 跟 Knob 1 (P01) 协同。
- 预期 ELO: +50 ~ +100 (W8 估)。

**P22. `build_miner_east_west_when_visible`** *(P04 的构造侧)*
- 触发: P04 触发场景的构造层落地, EAST/WEST 邻格 mining_node。
- 动作: `BUILD_MINER_EAST` 或 `BUILD_MINER_WEST`, 优先选择对应 `obs.player` (player 0 优先 EAST, player 1 优先 WEST, 利用 §3 D02 打破对称)。
- 来源: 同 P04 + §3。
- 冲突: 跟 P04 是同一逻辑的两面 (P04 是闸门, P22 是动作); 实施时合并即可。
- 预期 ELO: 已计入 P04。

**P23. `build_scout_step_480_energy_dump`** *(W6 A13)*
- 触发: `turn >= 480` 且 `turn < 495` 且 `factory_energy > 350` 且 `f_build_cd <= 0` 且 tiebreak 估计 `|my_total - enemy_total| < 50`。
- 动作: 强制 `BUILD_SCOUT_NORTH` 把多余能量转 unit_count。
- 来源: W6 A13 (含 important calibration: 仅 energy 接近 tie 时)。
- 冲突: 必须 gate 严格, 跟 v37 `gap > 4` 互斥时优先 gap 检查; 跟 P21 互斥时优先 P21。
- 预期 ELO: +5 ~ +15。

**P24. `build_worker_when_wall_blocks_path`**
- 触发: 工厂 BFS 全部失败 + `factory_gap <= 6` (现行 <= 4) + 北邻格有墙 + `factory_energy >= 350`。
- 动作: `main.py:392-394` 现行 BUILD_WORKER 兜底, 把 `factory_gap <= 4` 放宽到 `<= 6` 同时把 energy 阈值跟 v40 一致设 350。
- 来源: W4 附录 B-1 指出 worker 末位分支几乎死代码。
- 冲突: 跟 P21 互斥 (P21 是"主动建", 此条是"兜底建"); 优先级 P21 > P24。
- 预期 ELO: +5 ~ +15。

**P25. `build_miner_undirected_step_50`** *(Takahiro 风格扩展)*
- 触发: `turn >= 30 + turn <= 60` 且 `(factory_col, factory_row) in mining_nodes` 且 `counts[MINER] < 1`。
- 动作: P08 的窗口扩展; 此条覆盖中早期 (P08 是 always-on bug fix, P25 是策略时机)。
- 来源: W3 §3 Takahiro Hybrid 中 SCOUT-MAX 异类, 100% undirected miner。
- 冲突: 跟 P08 同; 合并实现。
- 预期 ELO: +3 ~ +10。

---

## 第二章: 杀招集 (6 个)

每招包含: 名字 / 触发上下文 / 招式序列 / 预期效果 / 实现位置 / 风险。

### K1. 断龙手 (Jump-Cooldown Steal)

- 触发: 我方 `f_jump_cd <= 0` + 可见敌工厂 Manhattan ≤ 4 + 敌方 `ejump_cd > 5` + 我方 row > 敌方 row。
- 招式:
  - turn k: 我方 `JUMP_NORTH` (利用 jcd ready) 跳 2 格越过敌方威胁带, 锁我方 jcd=20 但获得 row+2;
  - turn k+1: 敌方追北但他 jcd 已破; 我方 walk NORTH 继续推 row;
  - turn k+2~k+19: 敌方 jcd 仍未恢复, 我们已建立 ≥ 3 row 领先。
- 预期: 把"对碰 jcd 烧光"变成"对方 jcd 永远比我们慢 5 turn"。
- 实现: `main.py:294-307` emergency block 之后, BFS 之前, 新加 if 分支判断 (≤ 10 行)。
- 风险: 若 jcd 估计错 (敌方刚 jumped 但我们 obs.step delay), 我方 jcd 先烧白送。

### K2. 弃车保帅 (Scout Suicide Jump-Block)

- 触发: 可见敌工厂 `ejump_cd <= 0` + 我方有 scout 距敌方某可能跳点 ≤ 2 步 + 我方 row ≥ 敌方 row。
- 招式:
  - turn k: scout `NORTH` 走向敌方跳点 (ec, er+2);
  - turn k+1: scout 到达跳点; 敌方 JUMP 落到该格 = factory crush scout (敌方安全) 但敌方 jcd 锁 20;
  - turn k+2~k+19: 我方利用敌方 jcd 真空期 NORTH/JUMP_NORTH 拉开。
- 预期: 50 energy scout 换敌方 20 turn jcd, 是 W6 A11 的实战化版本; 单触发 +30 ELO。
- 实现: scout planning 段 (`main.py:398-419`) 加优先级最高的 "find_jump_block_target" 分支 (~30 行)。
- 风险: 敌方可能不跳, scout 白死 50 energy; 需 enemy `factory_gap` 紧 (jcd 必须用) 才触发。

### K3. 经济绞杀 (Mine-Sit Energy Strangulation)

- 触发: `turn >= 100` + `factory_energy >= 1500` + 我方在 own_mine 上 + 可见敌工厂 `final_energy_estimate <= 我方 - 1000`。
- 招式:
  - turn k~k+N: 我方 IDLE 在 mine 上 (持续 +50/turn);
  - 同时 worker `REMOVE_NORTH` 提前破墙;
  - turn k+N+1: factory NORTH 走上下一 mine (链式踩矿);
  - 敌方追 row 时已经能量耗尽 boundary_scroll 死。
- 预期: 把 v24 偶尔出现的 "高 energy 站矿" 升级为 deliberate 战术; 这是 bunt 的核心赢局机制。
- 实现: P07 (`idle_on_own_mine_denial_aware`) + P15 (worker REMOVE) 组合, 加 `enemy_energy_estimate` 助手。
- 风险: 长期 IDLE 让敌方 scout 切断我方北路 (需 scout 探到他下一个 mine 位置)。

### K4. 镜像欺骗 (Asymmetric Mirror-Break)

- 触发: paired-seed 自对弈或镜像对手 (W3 多个 archetype 都用 mirror inference) + `turn <= 50` + 我方 player == 0。
- 招式:
  - turn 0~10: player 0 优先 EAST 系动作 (jump tie-break, miner direction tie-break);
  - 同时 player 1 优先 WEST;
  - turn 10+: 两侧 fog 推断错位, 敌方 mirror inference 失效, 我方仍可推断;
  - turn 20+: 利用东西方信息不对称, 选择 mirror-broken 的 mining_node 抢建。
- 预期: 把 v24 vs v24 平局率从 ~20% 降到 < 10%, 同时单边胜率不变 (双方对称, 但镜像信息变得 player-specific 而非 deterministic)。
- 实现: §3 D01-D02 落地; ~15 行总和。
- 风险: 对手非镜像 IL (e.g. RL bot) 此招无效但也无副作用。

### K5. 碰撞陷阱 (Tempo Bait + Jump Escape)

- 触发: `f_move_cd > 1` 即将 IDLE + 敌工厂 Manhattan ≤ 3 + `f_jump_cd <= 2` (将 ready)。
- 招式:
  - turn k: IDLE (诱使敌方走过来撞);
  - turn k+1: 敌方走到我方相邻格 (期待 ram);
  - turn k+2: 我方 `JUMP_NORTH` (此时 jcd ready) 跳 2 格离开;
  - 敌方下回合发现扑空, 但他的 mvcd 已用, jcd 也用过 = 双烧。
- 预期: 单触发 +30 ELO; 替代 v37 "无脑被撞死" 的 collision loss pattern。
- 实现: `main.py:337-338` 的 `elif f_move_cd > 1` 分支内, 加 "tempo_bait" 标记, 下回合优先使用 JUMP_NORTH。
- 风险: 敌方可能不上钩, IDLE 白浪费 1 turn (但反正本来也要 IDLE)。

### K6. 三步绞 (TRANSFORM + TRANSFER + Step)

- 触发: 工厂北邻 mining_node + `f_build_cd <= 1` + `factory_energy >= 800` + `turn <= 50`。
- 招式:
  - turn k: `BUILD_MINER_NORTH` (在 mine 格 spawn miner, 300 energy 投入);
  - turn k+1: miner `TRANSFER_SOUTH` 把残余 200 energy 倒回 factory (P02);
  - turn k+2: miner `TRANSFORM` 变 mine (200 energy 锁进矿);
  - turn k+3: factory `NORTH` 踩上去 (+50/turn 流入开始);
  - turn k+4~final: factory 持续 +50/turn, 净收益 ≈ 50 × (500 - k) - 100 ≈ 20000 energy at end of game。
- 预期: 这是 bunt 的核心赢局机制 (W3 §1)。完整三步绞 ROI 远超 W4 现行 "一步 build + 一步 transform + 站着 IDLE" 的简化版。
- 实现: P02 (miner TRANSFER) + P03 (early miner) + P06 (walk onto mine) 三个补丁合并自动产生此序列, 不需要额外代码。
- 风险: 中间任一步被打断 (敌方撞 miner / 工厂 mvcd 卡住) 整套链条断, 但 v24 现行的 "建 miner + TRANSFORM 立刻" 也有同样断链风险。

---

## 第三章: 自对弈多样化 / 反 mirror 平局 (5+ 机制)

### 3.1 为什么 v24 vs v24 会同归于尽?

**Deterministic 决策步骤**:
- `main.py:294-307` emergency 段: 给定相同 obs 输出唯一动作 (NORTH 优先, EAST 优先于 WEST);
- `bfs_jump` BFS 顺序: `DIRS = ("NORTH","EAST","WEST","SOUTH")` 固定迭代顺序, tie 永远偏 NORTH/EAST;
- `mine_build_action` 只看 NORTH 方向单分支;
- `safe_factory_action` 给定相同 threats 输出相同 bool;
- `factory_uid` 选取: `for uid in my_robots: if FACTORY` 取第一个匹配的, 在 dict iteration 上有 player-symmetric 同序。

**Player-symmetric 决策**:
- `MIRROR_WALL` 推断让东西 fog 立刻对称;
- 两方在 paired-seed 下初始 obs 是完全镜像 (因 W3 §1.5 engine 镜像生成 mining_nodes / crystals / walls);
- 双方 `factory_col` 也镜像 (col 0 vs col width-1), `factory_row` 相等;
- 故 player 0 BFS 找到的 NORTH-EAST 路径, player 1 也立刻找到 NORTH-WEST 镜像路径;
- 时序完全同步: 同 turn build, 同 turn jump, 同 turn 进 emergency。

**自对弈表现**: paired-seed 评估时大量 `simultaneous_tiebreak` (双方同 turn 同样动作 → 同时刻死亡 / 同时刻 boundary_scroll), 在 `replay_summary.csv` 显示为 draw。research.md `v37 vs v24 100 paired seeds: v37 44, v24 36, draws 20` 即 20% draw rate, 是异常高的。

### 3.2 打破对称的代价与收益

**代价**:
- 引入噪声可能在已经"该赢"的局面里选次优动作, 单条小补丁可能 -3~5 ELO;
- 哈希噪声让 paired-seed 评估不再 100% reproducible, 增加评估方差;
- 跟 W6 A12 警告一致: 误用 `random.random()` 会被 Kaggle 重置, 必须用 hash-based。

**收益**:
- 反 IL: 公开 `main.py` 后, 对手即使复制代码也无法 reproduce 我方动作 (因为 secret salt);
- 自对弈信息量提升: 同一局 50 paired seeds 的胜率方差从 ~5% 降到 ~15% (可看出更细差异);
- 避免 deterministic loop: 当前 v24 vs v24 在某些 seed 下 100% 重复同样的 boundary_scroll;
- W8 决策树指纹"v24 是 us"主要是 build_worker=0 + scout_per_minute>0.29, 其次是 deterministic action 序列。

**结论**: 收益远大于代价, **建议全套 D01-D05 一起 ship**, 因为单独引入容易被随机噪声掩盖。

### 3.3 具体多样化机制 (5+ 个)

**D01. Player-asymmetric BFS tiebreak**
- 实现位置: `bfs_first_step` (L126) 和 `bfs_jump` (L156) 的 `DIRS` 迭代顺序。
- 改动: `DIRS_P0 = ("NORTH","EAST","WEST","SOUTH")`, `DIRS_P1 = ("NORTH","WEST","EAST","SOUTH")`, 根据 `obs.player` 选用。
- 随机度: 0% (完全确定性), 但 player-asymmetric。
- ELO 影响: 自对弈 draw rate ↓ ~10%, ladder 单边胜率几乎不变 (单边对手不分 player 0/1 相同概率)。
- 反 imitation: 强 (IL 必须把 obs.player 当 feature 才能拷)。

**D02. Player-asymmetric build direction tie-break**
- 实现位置: P04/P22 的 EAST/WEST 选择; P11 的 edge jump tie-break。
- 改动: `prefer_east = (obs.player == 0)`, 跨所有 EAST/WEST 二选场景统一应用。
- 随机度: 0%。
- ELO 影响: 同 D01 但作用面更窄 (仅侧向构造)。
- 反 imitation: 强。

**D03. Hash-based perturbation on tied utility**
- 实现位置: 任何 utility scorer 给出 top-2 cost 差 < 10% 时 (未来 W1 utility 重构后); 当前 v24 没有 utility, 可先用在 fallback chain 顺序上。
- 改动: `import hashlib; SALT = b"\x9a\x7d\xc4\x33\x88\x21\x55\x77"; h = hashlib.sha256(SALT + bytes([turn % 256, factory_col % 256, factory_row % 256, obs.player])).digest()[0]; if h < 26: swap_top2()` (10% 概率)。
- 随机度: ~3-5% 决策被改写。
- ELO 影响: ladder 中性 (~ -2 ~ +2), 自对弈 draw rate ↓ ~5%。
- 反 imitation: 极强 (W6 A12 升级版, secret salt 不可逆)。

**D04. Phase-conditional jitter rate**
- 实现位置: D03 的扩展, 不同阶段不同 perturbation 率。
- 改动: `jitter_rate = 0.0 if turn < 50 else 0.05 if turn < 300 else 0.01`。理由: early 期 deterministic 经济最重要不能扰乱, mid 期最多扰乱避 IL, late 期再降回低 (避免高 stakes 误判)。
- 随机度: 跨 game 平均 ~3%。
- ELO 影响: 比 D03 更稳。
- 反 imitation: 高 (IL 必须建模 turn 区间)。

**D05. Seed-based opening preference**
- 实现位置: turn == 0 时计算 `match_seed = sha256(SALT + obs.player.to_bytes(1,'big') + factory_col.to_bytes(1,'big'))[0]`; `_memory["opening_bias"] = "aggressive" if match_seed < 128 else "balanced"`。
- 改动: opening_bias 影响 P03 (极早 miner) 是否激活, P10 (lateral SOUTH) 是否允许。aggressive 下 P03 在 step ≤ 10 立刻激活, balanced 下沿用 v24 行为。
- 随机度: 每场仅一次决策, 但影响整场。
- ELO 影响: 不确定 (取决于哪个 opening 更适合该 seed); 但 ladder 长期跑平均 50/50 没坏处。
- 反 imitation: 强 (IL 必须建模"该局 bias")。

**D06. Top-N argmax random selection (W6 A12 加强版)**
- 实现位置: factory action 的最终选择, 在 BFS 给出 step 之后。
- 改动: 计算备选动作集 (NORTH walk, JUMP_NORTH, BUILD_MINER), 按 BFS heuristic 给打分, top-2 内差 < 15% 时按 hash 30% 概率选 second。
- 随机度: ~5%。
- ELO 影响: 跟 D03 重叠但作用层更高。
- 反 imitation: 高。

### 3.4 每个机制的对反 imitation 贡献

| 机制 | 决策变化率 | 自对弈 ELO 影响 | 反 IL 贡献 |
|---|---|---|---|
| D01 | 0% (deterministic by player) | 中性 | 强 |
| D02 | 0% (同) | 中性 | 强 |
| D03 | 3-5% | -2 ~ +2 | 极强 |
| D04 | 平均 3% | -1 ~ +3 | 高 |
| D05 | 每场 1 次决策 | -3 ~ +5 | 强 |
| D06 | 5% | -2 ~ +3 | 高 |

### 3.5 如何 paired-seed 验证"自对弈来回更多"

**度量定义**:
- `draw_rate`: paired-seed 50 局里 draw / 50 (目标: 从 ~20% 降到 ≤ 10%);
- `unique_action_seqs`: 50 局里每局 first-100-turn 的工厂 action 序列哈希, 计算 unique 数 / 50 (目标: 从 1-3 提到 ≥ 10);
- `mean_turns_to_divergence`: paired-seed (A vs A) 里, 第一次双方动作不一致的 turn (目标: 从 ~50 降到 ≤ 20);
- `simultaneous_tiebreak_rate`: 失败模式分布中此项占 draw 比 (目标: 从 ~80% 降到 ≤ 50%)。

**测试 protocol**:
- 跑 50 paired seeds: agent_X vs agent_X (本版本对本版本);
- 跑 50 paired seeds: agent_X vs agent_v24 (本版本 vs 基线);
- 报告 4 个度量 + 单边 win-loss-draw。
- 通过标准: draw_rate ≤ 10% + unique_action_seqs ≥ 10 + 单边 vs v24 至少不负 (paired 25/25/5)。

**反例警告**: 单纯加 `random.random()` 会让 draw_rate 降但单边胜率随机化 → ladder 上下沉。必须用 deterministic hash + obs.player + secret salt, 才能在保持单边 ELO 的同时降 draw。

---

## 第四章: 优先级清单 (按 effort / ELO 排序)

每条标 effort (S = ≤ 30 分钟, M = 2-4h, L = 6h+), 预期 ELO, 类型。

| # | 名称 | effort | ELO | 类型 |
|---|---|---|---|---|
| 1 | P01 enemy_current_cell_unconditional | S | +20~+40 | bugfix |
| 2 | P21 build_worker_step_300_gap8 | S | +50~+100 | 构造 |
| 3 | P02 miner_transfer_south_before_transform | M | +40~+80 | 经济 |
| 4 | P03 step_le_10_early_miner | S | +30~+50 | 经济 |
| 5 | D01+D02 player-asymmetric tiebreak | S | +10~+20 | 多样化 |
| 6 | P13 crushes_active_attack_non_factory | M | +20~+40 | 防御 |
| 7 | P09 emergency_block_respect_north_only | S | +15~+30 | 位移 |
| 8 | P04+P22 side_miner_when_safe | M | +15~+30 | 经济 |
| 9 | P19 mirror_extend_to_mining_nodes | S | +10~+25 | 视野 |
| 10 | P07 idle_on_own_mine_denial_aware | S | +15~+25 | 经济 |
| 11 | P15 worker_remove_north_breakthrough | M | +10~+20 | 防御 |
| 12 | K2 弃车保帅 scout jump-block | L | +20~+30 | 杀招 |
| 13 | K6 三步绞 (= P02+P03+P06 合体) | M | +30~+50 | 杀招 |
| 14 | P14 scout_mutual_kill | S | +10~+20 | 防御 |
| 15 | D03+D04 hash-based perturbation | M | +5~+15 | 多样化 |
| 16 | P06 walk_onto_north_mine_extended_gap | S | +5~+15 | 经济 |
| 17 | P05 mine_econ_lower_energy_floor | S | +10~+20 | 经济 |
| 18 | P10 lateral_south_for_cooldown_reset | M | +5~+15 | 位移 |
| 19 | P17 worker_build_south_guard | M | +5~+15 | 防御 |
| 20 | P11 edge_jump_tiebreak | S | +5~+10 | 位移 |
| 21 | P16 anti_ram_when_mvcd_high | M | +10~+20 | 防御 |
| 22 | K5 碰撞陷阱 (= P16+tempo bait) | M | +15~+30 | 杀招 |
| 23 | P12 fallback_5_deeper_bfs | S | +3~+10 | 位移 |
| 24 | P20 last_step_scout_probe | M | +5~+15 | 视野 |
| 25 | D05 seed-based opening preference | M | -3~+5 | 多样化 |
| 26 | P23 build_scout_step_480_energy_dump | S | +5~+15 | 构造 |
| 27 | K1 断龙手 jump-cd steal | L | +15~+30 | 杀招 |
| 28 | P08+P25 undirected miner | S | +5~+15 | 经济 |
| 29 | P18 suicide_tie_when_dead | S | +5~+15 | 防御 |
| 30 | P24 build_worker_when_wall_blocks | S | +5~+15 | 构造 |

---

## 第五章: 明天 D+1 推荐 (基于 W7 patch-over-refactor 原则)

**推荐 3 条**:

1. **P01 `enemy_current_cell_unconditional`** (effort 5 min, ELO +20~+40)。**理由**: 这是 research.md L626-627 已经识别的一行 bug, 是 v40 失败的根因; 改一行 (把 `enemy_factory_threats.add((ec, er))` 从 `if collision_tiebreak_bad:` 块里提出来) 即可消除 "走进静止敌工厂" 类自杀。是任何 v42 必带的底线修。

2. **P21 `build_worker_step_300_gap8`** (effort 30 min, ELO +50~+100)。**理由**: W8 §6 排名第一的 ROI 改动, 直接修我们"0 worker outlier"指纹。Top10 全员 ≥ 0.64 worker/ep, 我们 0/44 局。仅加一个 elif 分支在 `main.py:330-336` scout 之后, BUILD_WORKER_NORTH 即可。跟 v40 worker energy floor 350 协同 (此条加 500 更严, 避开 v40 同源风险)。

3. **P02 `miner_transfer_south_before_transform`** (effort 2h, ELO +40~+80)。**理由**: W6 A2 + W3 §2.4 重复确认的"我们 transfer 总数 = 0"差距。把 miner 段 `main.py:421-429` 改为先 TRANSFER_SOUTH 再下回合 TRANSFORM, 单 mine 经济 ROI ×2。配合 P03 (P03 是 D+2 候选)会自动形成 K6 三步绞。

**为什么不挑 P03 极早 miner / P13 factory crush**:
- P03 触碰 v37 已有的 gap > 6 闸门, 跟 v24 主干竞争, 风险较高 (v14 教训); 留到 D+2 paired-seed 50 局严测。
- P13 (W6 A1) 需要重排 factory 优先级链, 跟 P01/P21 同时改容易交叉污染信号; 单独 D+2 加。

**D+1 之后的滚动 (D+2 ~ D+5)**:
- D+2: P03 + P04 (经济激进化), paired-seed 50 局 gate;
- D+3: D01+D02 (player-asymmetric tiebreak), 测自对弈 draw_rate;
- D+4: P13 + K5 (factory crush + 碰撞陷阱);
- D+5: D03 + D04 (hash perturbation), 反 IL gate。

---

## 第六章: 给协调者的回报

### 3 个最 ROI 高的小补丁 (1 行/条)

1. **P01 `enemy_current_cell_unconditional`**——把 `enemy_factory_threats.add((ec, er))` 提出 `if collision_tiebreak_bad:` 块, 5 分钟改一行修 v40 灾难性自杀, +20~+40 ELO。
2. **P21 `build_worker_step_300_gap8`**——`turn>=300 + gap>=8 + energy>=500 + 0 worker + ≥1 miner` 时 BUILD_WORKER_NORTH, 30 分钟修我们"0 worker outlier", W8 估 +50~+100 ELO。
3. **P02 `miner_transfer_south_before_transform`**——miner 在 mine 上且 factory 邻近时先 TRANSFER_SOUTH 再下回合 TRANSFORM, 2 小时改 miner 段, 单矿 ROI 翻倍, +40~+80 ELO。

### 1 个最锋利的杀招 (3 句话)

**K6 三步绞 (TRANSFORM + TRANSFER + 工厂踩矿)**: 工厂在 turn ≤ 50 北邻 mining_node 时 `BUILD_MINER_NORTH` → miner 下回合 `TRANSFER_SOUTH` 把 250 energy 倒回 factory → miner 下下回合 `TRANSFORM` 变 mine → factory NORTH 踩上去开始 +50/turn 流入。这是 bunterrrrr 把 max_factory_energy 推到 10000 的核心机制, 也是我们对 bunt 经济差距 (2616 vs 7067) 的最大单杠杆。实现层面只需 P02 + P03 + P06 三条补丁合并自动产生, 不需要写 "killer combo" 专门代码。

### 1 个最值得试的自对弈多样化机制

**D01 + D02 player-asymmetric tiebreak**: 把 `DIRS` 迭代顺序按 `obs.player` 分两版 (p0 偏 EAST, p1 偏 WEST), 同步把侧向 build/jump 的 tie-break 也按 player 分。**0% 随机度, 100% deterministic**, 但打破了 v24 vs v24 的镜像对称 (二者本来 100% 走同样动作)。预期自对弈 draw_rate 从 ~20% 降到 ≤ 10%, ladder 单边胜率不受影响 (对手不分 player 0/1 相同概率), 且强反 IL (IL 必须 obs.player as feature 才能拷)。30 分钟可 ship, 风险极低。

### 文档路径

`$HOME/Desktop/kagglecraw/docs/tactical_patches_and_killer_moves.md`

---

**End of W9 report.**
