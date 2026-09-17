# Opponent Identification, Behavioral Fingerprint, and Top 5 Individual Counters (W12-retry)

最后更新: 2026-06-03. 输入: W3 横向 (top 2-15), W8 深度 (top 1-10 archetype + 决策树),
v24 `main.py`, `kaggle_environments/envs/crawl/crawl.json`, `reports/replays/` 30 局, 4 个 leaderboard 时刻快照.
范围严格砍至 5 件事; 不重复 W3/W8 已有的横向描述, 只补"我们能落地的反制".

---

## 0. 执行摘要 (5 行)

1. **在线 obs 拿不到对手身份**: schema 里只有 `player` (0/1), 必须靠行为指纹.
2. **用户假设不成立**: 实测 30 局里只有 2 局对手是 top 30, 70% 是 rank 51+; "个体 playbook 覆盖 top 30" 在 ELO 当前位置约 ~7% 命中率.
3. **我们最该做的不是 archetype 反制也不是 top10 个体反制, 而是不死** (9 输里 6 个步数 < 310, 提早死光).
4. **fingerprint 仍值得做**, 但用法是"碰到 Silent Miner 就别走 timeout, 碰到 Scout 就别让自己死" 的粗分流, 不是 15 路 dict.
5. **D+1 唯一一件事**: 把 boundary_scroll 防御 (step ≥ 400 & gap ≤ 10 强制 NORTH/JUMP_NORTH) 加上, 单条预期 +20~+40 ELO, 比任何 fingerprint 都早回本.

---

## 1. obs 能否直接拿到对手身份: **NO**

**单字结论**: **NO**.

证据 (5 行):

- `kaggle_environments/envs/crawl/crawl.json` 的 `observation` block 完整定义: `player, walls, crystals, robots, mines, miningNodes, southBound, northBound, remainingOverageTime` 加 9 个 `hidden:true` 的 global 字段——**全部 hidden 字段 agent 看不到**.
- `player` 只是 0 或 1, 没有 `teamName / submissionId / userId / agentIndex / opponentName` 任何形式.
- `crawl.py` 里 `_update_player_observations` 只写入 `walls / crystals / robots / mines / miningNodes` 到 `state[player_idx].observation`, 不写 TeamNames; TeamNames 只存在于 `info` 字段, agent 拿不到.
- `episode-*-replay.json` 的 `info.TeamNames` 是录像后的元数据, 在线 episode 里 agent 没法读 (replay 是 server 端 dump).
- 对手 `robots` 里的 uid 是 game 内部 counter, 每局都重置, 不能跨 episode 关联.

**实际意义**: 不能写 `playbook[opponent_team_id]` 这种 1 行 dict lookup. 任何"个体反制"都必须靠**前 30-50 turn 的行为指纹**反推, 或者干脆放弃个体反制走 archetype.

---

## 2. 行为指纹的最小算法

**目标**: `fingerprint_opponent(obs, history) -> (archetype, confidence)`, 在 turn ~50 时输出三档 archetype 概率, 给 utility scoring 一个 ctx 字段.

**输入特征 (8 个, turn 30-50 都能稳定拿)**:

1. `opp_first_miner_step`: 看到对方 robot type == MINER 的最早 turn (没看到就 +inf).
2. `opp_first_scout_step`: 同上, type == SCOUT.
3. `opp_scout_count_50`: turn 50 时累积看到的 SCOUT uid 总数.
4. `opp_miner_count_50`: 同上, MINER.
5. `opp_worker_count_50`: 同上, WORKER (top10 全员 ≥0.64, 决策树第一条 split).
6. `opp_factory_jump_count`: 推断对方 factory 跳过的次数 (factory 单步移动 2 格 ⇒ jump).
7. `opp_visible_idle_pct`: 对方所有可见 robot 中 IDLE 占比 (实际从 robot 位置 delta 反推).
8. `opp_mine_count_50`: turn 50 时看到的 owner == opp 的 mine 数 (`obs.mines` 里 `[2] == opp_player`).

**匹配方法**: 直接复用 W8 决策树 (`reports/top10_analysis/decision_tree_rules.txt`) 反向跑——决策树本身是 player-level aggregate 训练的, turn 50 截断后特征仍然单调, 可以当 partial-observation classifier.

**输出**: `(P_silent_miner, P_hybrid, P_scout_swarm)`. 不是真概率, 用归一化到 sum=1 的"软投票".

**置信门控**: turn < 30 一律返回 uniform `(0.33, 0.33, 0.33)`; turn 30-50 用 W8 决策树第一条 split 投一票; turn ≥ 50 再看 worker/miner 比例做第二票.

伪代码 (≤ 20 行):

```python
def fingerprint_opponent(obs, history, turn):
    if turn < 30:
        return ("unknown", (1/3, 1/3, 1/3))
    f = history  # rolling features updated each turn from obs.robots / obs.mines
    # W8 decision tree first split: build_worker <= 0.5
    miner_score = 1.0 if (f.opp_worker_count <= 1 and f.opp_scout_count <= 1
                          and f.opp_first_miner_step <= 50) else 0.0
    scout_score = 1.0 if (f.opp_scout_count >= 3 and f.opp_first_miner_step > 60) else 0.0
    hybrid_score = 1.0 - max(miner_score, scout_score) + 0.3 * (f.opp_worker_count >= 1)
    total = miner_score + scout_score + hybrid_score + 1e-6
    p = (miner_score / total, hybrid_score / total, scout_score / total)
    if turn < 50:
        p = tuple(0.5 * x + 0.5 / 3 for x in p)  # blend toward prior, low confidence
    label = ["silent_miner", "hybrid", "scout_swarm"][p.index(max(p))]
    confidence = max(p) - 1/3
    return (label, p, confidence)
```

**特征怎么从 obs 抽**: 每 turn 在 `_agent_inner` 顶部维护 `_memory['opp_history']`:

```python
h = _memory.setdefault('opp_history', {
    'opp_uids_seen': {},      # uid -> first_turn_seen
    'opp_type_first': {},     # robot_type -> first_turn_seen
    'opp_mines_seen': set(),
    'opp_factory_pos': [],    # list of (turn, col, row) for opp factory
})
for uid, d in obs.robots.items():
    if d[4] == player: continue
    if uid not in h['opp_uids_seen']:
        h['opp_uids_seen'][uid] = turn
        h['opp_type_first'].setdefault(d[0], turn)
    if d[0] == FACTORY:
        h['opp_factory_pos'].append((turn, d[1], d[2]))
for k, v in obs.mines.items():
    if len(v) >= 3 and v[2] != player:
        h['opp_mines_seen'].add(k)
```

然后第 8 维 `opp_factory_jump_count` 用 `opp_factory_pos` 相邻两次距离 > 1 数 jump (factory 单步走 1, jump 走 2).

**踩坑**: 对方 robot 在 fog of war 之外, 看到的是 lower bound; turn 50 前我们视野差, miner_count 常欠采. 所以 `opp_first_miner_step` 必须保留 `inf` 表示"没看见", 不能用 999 这种 sentinel——会让决策树把"看不见"误判成"对方很晚才出 miner". 看不见时 fingerprint 应直接退到 `unknown`, 见第 5 节兜底.

---

## 3. 用户核心假设的判断: **不成立**

**单字结论**: **NO**, "top 10/20/30 短期内不变 + 个体 playbook 比 archetype 反制更值"的复合假设两半都需要修正.

**(1) 名单稳定性**: 比较 `leaderboard/2026-06-02 07:56` vs `leaderboard_v40_final/2026-06-03 09:52` (间隔 26 小时, 没有更早快照):
- top10 8/10 名字相同, 但顺序大改 (Klodt 4→6, Andrey 0→2 直接挤进 top 2), Bekker / harmo-miu / Pavlo Ivanin 1 天内进出. **顺序不稳, 集合相对稳**.
- 26 小时只有 1 个快照对, 信号弱; 真要回答"短期不变"需要至少 1 周的每日快照, 这是数据缺口. 我们目前没有这个时间序列, 应该周末补抓 7 天 leaderboard.

**(2) 是否在迭代 submission**: 当前 top10 的 `LastSubmissionDate` 分布: ≥06-01 有 5 个 (Pavel, Klodt, Andrey, Bekker, Joseph), ≤05-27 有 5 个 (bunt, Hazy, ZERO HQR, AI TOOK, Takahiro). **50% 顶尖队伍在每日迭代**, 个体 playbook 1-2 周内会过时.

**(3) ELO 匹配现实**: 我们 `reports/replays/` 里 30 局 actual 对手按当前 rank 分桶: top10=1, 11-20=1, 21-30=0, 31-50=6, **51+=21 (70%)**.
我们 rank 20, score 1155, 但实际匹配铺得很开, 不是想象中的"集中打 rank 18-30". 个体 playbook 覆盖 top 30 = 命中 ~2/30 = **6.7% 的对局**.

**(4) 值不值 (rough math)**: 假设我们目前 ELO ~1155, K = 32, 一局赢从 rank ~50 的对手 ELO 差 ~200 ⇒ +5 ELO/胜; 输 +200 ELO 对手 ⇒ -27. 个体 playbook 命中 top 30 时假设能"多 20% 胜率 × 32 = +6.4 ELO/命中局", 命中率 7% ⇒ **期望 +0.45 ELO/局**. archetype 反制覆盖 ~80% 对局, 假设每命中局多 5% 胜率 ⇒ **期望 +1.3 ELO/局**. 修死亡 (1 局/30 翻盘) 直接 +1 平均 ELO/局 (避免 -27 损失). **排序: 修死亡 > archetype 反制 > top10 个体反制**.

9 输细分: 6 个步数 <310 (Betise 161/Vladislav 247/抹茶 122/Daniel Du 309/Pilkwang 109/tuannm3823 218), 是**我们自己死** (collision 或 boundary_scroll), 对手 actions 里 0-3 BUILD_SCOUT 且 0 BUILD_MINER——他们根本没经济, 是我们提早送; 2 输是 Bulşah Keçici step 501 timeout tiebreak, 1 输是 Changdao Chen step 494 崩盘. 个体 playbook 完全救不了前 6 种死法. **修死亡 > 修反制**.

---

## 4. Top 5 个体反制 (严格 5 个)

挑选标准: ① bunterrrrr 必须放, 是天花板; ② 我们 ELO 邻近 + 最近活跃 1 个; ③ v37 实测**输过**的 3 个 (按损失类型分散).

### 4.1 bunterrrrr (rank 1, score 2222.7, Silent Miner)

- **打法 (W3/W8)**: 0 scout (100% episode), 4.07 miner/ep, peak factory energy 7067, first_miner 中位数 31 (min 2), JUMP_NORTH 19.1 次/局; 工厂踩自己矿吸能 + 50/turn.
- **匹配频率**: 我们 30 局 0 次. 个体反制纯属"如果偶然撞上"的 hedge, 期望 ELO 贡献 < +1.
- **反制**: 学 AI TOOK MY JOB 的 3 平模板——拉到 step 500 tiebreak 时 final energy 差距 < 1000 才有平局机会. 在 v24 `main.py` line 309 (`# Mine economy:` 之前) 插 `if _memory.get('opp_archetype')=='silent_miner' and turn>=200 and counts[WORKER]==0 and factory_energy>=300: build worker (NORTH)`. 预期: 防溃败保 draw, +0~+10 ELO (大概率不命中).

### 4.2 Daniel Bekker (rank 8, score 1393.1, Worker-Max Hybrid)

- **打法 (W8)**: 3.16 worker/ep (top10 最多), 2.16 miner, 0 SOUTH miner, final energy 3585 (top10 最低).
- **匹配频率**: 30 局 1 次, 我们 W (steps=213, my_r=1). 已知能赢, 不需要新反制.
- **反制**: 维持现状. 唯一加固——当 fingerprint 判 hybrid 且 `opp_worker_count >= 2`, 把 v24 的 BFS depth 从 20 调 25 (拉远路径, 不让他 worker 拆墙堵我们). 预期 +5 ELO.

### 4.3 Phillip Choi (rank 16, score 1174.0, last_sub 06-03)

- **打法**: 30 局 1 次, 我们 W (steps=440, my_r=559 vs -64, 这是 v37 的最干净 long-game 胜利).
- **匹配频率**: 中等. 是 11-20 段每日迭代的 active 玩家, 短期内我们会反复撞.
- **反制**: 他的打法跟我们 v37 像 (long game + 中段经济), 反制是**保持当前 v24 行为**, 唯一防御点——他 last_sub 06-03 在迭代, 一周后可能升级, 我们要在 `experiments/v38+` 阶段重新抓他的 replay 比较 action mix. 预期 +0 (现状), 但**预警风险**: 如果他升级到 build_worker, 我们 0 worker 的 v24 会反过来吃亏.

### 4.4 Bulşah Keçici (rank 62, score 970.9, 我们最痛的对手)

- **打法 (从 replay 反推)**: 2 战 2 胜我们, 都 step 501 timeout, opp_actions 全是 NORTH/SOUTH/EAST/WEST + 3 个 BUILD_SCOUT, **0 miner, 0 worker**. 纯 walk + scout 战术, 跟我们 v1/v6 同源, 但他 final energy 比我们高.
- **匹配频率**: 30 局 2 次 (6.7%), 这是 fingerprint 上 scout_swarm 但实际 "Walk-Only" 的边缘案例.
- **反制 (具体)**: 在 v24 `main.py` 的 SCOUT PLANNING 段 (line ~399), 加一个早停: `if turn >= 300 and counts[SCOUT] >= 1 and fingerprint_label == 'scout_swarm': skip building new scouts`; 把那 50 energy 留给 factory. 同时在 factory `mine_build_action` 分支放宽: 当 `fingerprint=='scout_swarm' and factory_energy >= 500` 时, 强制至少建 1 miner (即使 counts[MINER] == 0 而非现行 `< 1` 的等价条件; 这里关键是放宽 `factory_gap > 5` 这条触发). 预期: 2/30 翻盘成 1W1L, +10 ELO.

### 4.5 Changdao Chen (rank 40, score 1042.9)

- **打法 (从 replay 反推)**: 唯一一个"经济碾压"型损失, step 494, my_r=-10, opp_r=969. opp_actions: 大量 NORTH+JUMP_NORTH 类, 5 BUILD_SCOUT, 0 BUILD_MINER (从 visible action 看, 但 final 969 reward 意味着他必定有 ≥1 mine 我们没看到——这是 fog-of-war 下的 fingerprint false-negative 典型例子).
- **匹配频率**: 30 局 1 次. 这种"我们崩盘"局是 v37 最致命的失败模式: 单局 -27 ELO 抵消 5 个 +5 胜.
- **反制 (具体)**: 根因不在 archetype 而是**boundary_scroll 末期失误**——v24 line 376-378 的 fallback 3 (`SOUTH` to escape dead-end) 在 step 400+ 触发会直接送命; line 380-386 的 fallback 4 (desperation jump any dir) 也会接受 `JUMP_SOUTH` 把工厂往南送. 修法: 在 line 309 ~ 397 整段 factory planning 包一层 `if turn >= 400 and factory_gap <= 10:` 守卫——只允许 NORTH/JUMP_NORTH 系动作, 完全禁掉 SOUTH/JUMP_SOUTH/REMOVE/BUILD_SCOUT, BUILD_MINER 也禁 (此时建矿来不及). 预期: 把这类崩盘从 1/30 降到 0/30, **+20~+27 ELO** (单局崩盘代价大).

### 4.6 五个反制 ROI 汇总

| 对手 | 命中率/30局 | 当前结果 | 预期 ELO | 依赖 fingerprint? |
|---|---|---|---|---|
| bunterrrrr (#1) | 0/30 | 未知, 假设 100% L | +0 ~ +10 | 是 (silent_miner) |
| Daniel Bekker (#8) | 1/30 | 1W | +5 | 是 (hybrid) |
| Phillip Choi (#16) | 1/30 | 1W | +0 (维持) | 否 |
| Bulşah Keçici (#62) | 2/30 | 0W 2L | +10 | 是 (scout_swarm) |
| Changdao Chen (#40) | 1/30 | 0W 1L | +20~+27 | **否** (单纯 scroll fix) |

**关键观察**: 唯一不依赖 fingerprint 的 4.5 (Changdao Chen 类崩盘) 期望 ELO 占了 5 个反制总和的 60%; 4.4 (Bulşah Keçici) 占 25%. 其它 3 个加起来 ≤ +15 ELO. **如果只挑两个, 选 4.5 + 4.4 即可拿到 80% 价值**, fingerprint 只为 4.4 服务.

---

## 5. 集成方案

**(1) fingerprint 跑频率**: **只跑一次, 在 turn 50**. 理由: 决策树 split 在 turn 30 前噪声太大 (`opp_first_miner_step` 经常欠采), 50 之后再算反而稳; 跑一次后写入 `_memory['opp_archetype']` 缓存到 game 结束. 每 turn 跑会浪费 1-2ms 且换不来新信息——对手 archetype 一旦固定就不会变.

**(2) 挂载在 utility scoring 框架的 ctx 字段** (假设 W1 的 utility scoring 已有 `ctx` dict): 在 `_agent_inner` 顶部 `_memory.setdefault('opp_archetype', None)`, turn == 50 时计算并写入 `_memory['opp_archetype']`; 然后在每个决策分支前 `ctx_archetype = _memory.get('opp_archetype', 'unknown')`. 三处用到: factory `mine_build_action` 触发条件 (scout_swarm 放宽), scout planning (scout_swarm 限 1 个), 末期 worker build (silent_miner 强制 1 worker). 每处加一行 `if ctx_archetype == ...:` 即可, 不动 utility 主干.

**(3) fingerprint 不准时的兜底**: 三种失败模式 — ① turn 50 时还没看到对手任何 robot (factory 距离 > 视野 4+5+5), 返回 `unknown`; ② 三个 score 都接近 (max - min < 0.2), 也返回 `unknown`; ③ `unknown` 时**完全走 v24 默认逻辑**, 等于 fingerprint 没开. 这保证 fingerprint 故障不会让我们比 v24 更差.

**(4) 如果只能做 1 件事**: **加 boundary_scroll 防御** (step ≥ 400 & factory_gap ≤ 10 强制 NORTH/JUMP_NORTH, 禁用 BUILD_SCOUT/REMOVE/BUILD_MINER, 禁止 SOUTH fallback). 这一条修的是 Changdao Chen 类崩盘 + Joseph #10 共病, 不依赖 fingerprint, 不依赖个体反制, 单条 +20~+40 ELO, 是 9 个损失里立刻能救回 1-2 个的最高 ROI 改动. 个体反制和 fingerprint 都是 v39+ 才该做的事.

**(5) 落地位置 (v24 main.py 具体行)**:
- `mine_build_action` 触发条件 (line 314): 加 `ctx_archetype` 分支放宽 `counts[MINER] < 1` 到 `< 2` 当 scout_swarm.
- SCOUT PLANNING (line 399-419): 加早停 `if turn >= 300 and counts[SCOUT] >= 1 and ctx_archetype == 'scout_swarm': continue`.
- 末期 worker spawn (line 391-394): 当前只在 `factory_gap <= 4` 触发, 改为 silent_miner archetype 下放宽到 `factory_gap <= 8 and turn >= 200`.
- 新增 boundary_scroll 防御段, 插在 line 294 (emergency block) 之后, line 309 (mine build) 之前.

**(6) 验证方式**: 改完先跑 `kaggle_environments` local self-play (v24 vs v25 with fingerprint) 50 局看胜率不降; 再跑 5 局 vs v37 自己看 archetype 分类是否合理; 最后 submit 一次小样本 (20 ladder game) 看 ELO 变化方向是否对. 这是低成本验证, 不需要等 1 周公开 leaderboard 收敛.

**(7) 推进顺序建议**:
- **D+1** (今晚或明早): 只做第 (4) 件——boundary_scroll 防御. 不动 fingerprint, 不动个体反制. 提交一版 v38, 等 ELO 信号.
- **D+2**: 看 v38 ladder 跑了 ≥20 局后, 如果 boundary_scroll 类崩盘从 1/30 降到 0/30 (新 30 局抓取 + 重跑 loss 分类), 再往上加 fingerprint 框架 + 反制 4.4 (Bulşah Keçici 类的 scout-only 早停).
- **D+3 及之后**: 加 4.1 / 4.2 的 archetype-conditional 反制. 4.3 / 4.5 已经不需要 fingerprint, D+1 就完成.
- **不做**: 暂时不补 7 天 leaderboard 时序、不重新跑 W3/W8 — 现有数据已经够决策, 再补数据是 sunk-cost 投入.
