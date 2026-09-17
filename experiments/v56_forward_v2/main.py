"""
v56 Maze Crawler Agent: 1-ply forward simulation v2 (W-Forward-v2).

Same 1-ply forward-sim scaffolding as v55 (W-Forward), but the cost function
is reformulated to fix the three concrete failure modes diagnosed in
`reports/executor_log_forward_20260603.md`:

1. **JUMP was strictly dominated by IDLE** because W_CD_LOCK * 20 = 10 vs
   W_NORTH * 2 = 2 with v55's [1.0, 100.0, 0.5, 0.05, 5.0] weights, so on
   every no-collision tile the cost function picked IDLE forever and the
   factory was scrolled to death.

2. **No scroll-survival term**: the agent did not know that letting the gap
   collapse to 0 was catastrophic, so IDLE looked free even at gap=2.

3. **cd_lock_cost was linear in cd**, treating "20 turns of jump lock" as
   ten times worse than "2 turns of walk lock" unconditionally. In reality
   the cd lock only hurts you in proportion to how likely you are to
   actually need a jump in the next ~20 turns.

Fixes (6-term cost, lower is better):
  c1 death_in_K_turns  hard 10000 if predicted next-turn gap <= 1
  c2 north_progress    -(new_row - factory_row)
  c3 collision_prob    1 if dest in enemy_factory_threats / jump_threats
  c4 cd_lock_cost      cd_lock * p_need_jump(new_gap)
                       p_need_jump = 1.0 if gap<4, 0.5 if <8, 0.2 if <12, 0.1
  c5 energy_change     -delta_energy (only own_mine fill: +50)
  c6 mine_dwell_bonus  1 if dest in own_mines (subtracted)

total = W_DEATH*c1 + W_NORTH*c2 + W_COLLISION*c3 + W_CD_LOCK*c4
        + W_ENERGY*c5 - W_MINE*c6

Defaults: [10000, 5.0, 100.0, 0.05, 0.05, 5.0].

Weights are also overridable from env vars V56_W_DEATH / V56_W_NORTH / ...
for grid search without rewriting the file.

Scroll prediction: the agent cannot see env's hidden `scrollCounter`, so we
infer it. On turn 0 it starts at config.scrollStartInterval (default 10).
Each subsequent turn, if obs.southBound increased relative to the previous
turn (i.e., a scroll happened during the env step), the counter was reset
to get_scroll_interval(turn-1); otherwise it decremented by 1. We then
predict south_bound after this turn's env step as `south + (1 if
est_counter <= 1 else 0)`.

Kept from v55 (which kept from v37): BFS, can_move/can_jump, wall memory,
mirror walls, threat detection, scout/worker/miner planning, build
heuristics (early miner, late scout, last-resort worker).
"""
import os
import time
from collections import deque

FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}
SCOUT_DELAY_STEP = 24

# Env defaults — obs has no config access, hard-code.
FACTORY_MOVE_PERIOD = 2
FACTORY_JUMP_COOLDOWN = 20
SCROLL_START_INTERVAL = 10
SCROLL_END_INTERVAL = 2
SCROLL_RAMP_STEPS = 450


def get_scroll_interval(step):
    """Mirror of crawl.py get_scroll_interval(). Returns turns between scrolls."""
    if step >= SCROLL_RAMP_STEPS:
        return SCROLL_END_INTERVAL
    progress = step / SCROLL_RAMP_STEPS
    interval = SCROLL_START_INTERVAL - (SCROLL_START_INTERVAL - SCROLL_END_INTERVAL) * progress
    return max(SCROLL_END_INTERVAL, round(interval))


def p_need_jump(gap):
    """Probability we'll need a jump within the next ~20 turns, given current gap.

    Heuristic: lower gap => more likely we need jump for emergency escape =>
    locking jump cd is more costly. High gap => rarely need jump => cheap to lock.
    """
    if gap < 4:
        return 1.0
    if gap < 8:
        return 0.5
    if gap < 12:
        return 0.2
    return 0.1


# Cost weights (env-overridable for grid search).
W_DEATH = float(os.environ.get("V56_W_DEATH", "10000"))
# W_NORTH now scales "BFS-distance reduction toward target_row" (not raw row delta).
# This lets the cost see paths that go EAST -> NORTH instead of getting stuck
# IDLE behind walls. Jumps that land on the shortest path get full credit; jumps
# that land off-path get partial credit (or none, if landing increases dist).
W_NORTH = float(os.environ.get("V56_W_NORTH", "5.0"))
W_COLLISION = float(os.environ.get("V56_W_COLLISION", "100"))
W_CD_LOCK = float(os.environ.get("V56_W_CD_LOCK", "0.05"))
W_ENERGY = float(os.environ.get("V56_W_ENERGY", "0.05"))
W_MINE = float(os.environ.get("V56_W_MINE", "5.0"))
# How far north we plan toward. Larger = more lookahead but more BFS cost.
NORTH_BFS_TARGET_OFFSET = int(os.environ.get("V56_NORTH_TARGET", "5"))
NORTH_BFS_MAX_DEPTH = int(os.environ.get("V56_BFS_DEPTH", "12"))
# Death predicate threshold on predicted next-turn gap (spec default 1).
DEATH_GAP_THRESHOLD = int(os.environ.get("V56_DEATH_THR", "1"))
# Penalty when a cell is unreachable within max_depth.
UNREACHABLE_DIST = 50

# Tie-break order: north-pushing actions first.
CANDIDATE_ORDER = (
    "NORTH", "JUMP_NORTH",
    "EAST", "WEST",
    "JUMP_EAST", "JUMP_WEST",
    "IDLE",
    "SOUTH", "JUMP_SOUTH",
)

# Optional turn-timing instrumentation (Step 6).
_TIMING_LOG = os.environ.get("V56_TIMING_LOG", "").strip()
# Optional action distribution dump (Step 5 debug).
_ACTION_LOG = os.environ.get("V56_ACTION_LOG", "").strip()

MIRROR_WALL = [0] * 16
for _v in range(16):
    _m = (_v & 1) | (_v & 4)
    if _v & 2: _m |= 8
    if _v & 8: _m |= 2
    MIRROR_WALL[_v] = _m

_memory = {}


def _agent_inner(obs, config):
    global _memory
    actions = {}
    width = config.width
    south = obs.southBound
    north = obs.northBound
    player = obs.player
    turn = getattr(obs, "step", 0)

    # ========== PERSISTENT MEMORY (v37 walls + new: scroll counter) ==========
    if turn == 0:
        _memory = {}
    if "walls" not in _memory:
        _memory["walls"] = {}
    walls_mem = _memory["walls"]

    for i, w in enumerate(obs.walls):
        if w == -1:
            continue
        r = south + i // width
        c = i % width
        walls_mem[(c, r)] = w
        mc = (width - 1) - c
        mw = MIRROR_WALL[w]
        if (mc, r) not in walls_mem:
            walls_mem[(mc, r)] = mw

    if len(walls_mem) > 2000:
        cutoff = south - 5
        walls_mem = {k: v for k, v in walls_mem.items() if k[1] >= cutoff}
        _memory["walls"] = walls_mem

    # ----- Scroll-counter inference -----
    # est_counter = counter value at the start of THIS turn's env step (before
    # the env decrements it). If est_counter <= 1, scroll triggers this turn.
    last_south = _memory.get("last_south", south)
    est_counter = _memory.get("est_counter", SCROLL_START_INTERVAL)
    if turn == 0:
        est_counter = SCROLL_START_INTERVAL
    else:
        if south > last_south:
            # Scroll happened during turn-1's env step => counter was reset to
            # get_scroll_interval(turn-1). At start of this turn it equals that.
            est_counter = get_scroll_interval(turn - 1)
        else:
            est_counter = max(1, est_counter - 1)
    _memory["last_south"] = south
    _memory["est_counter"] = est_counter

    pred_south_next = south + 1 if est_counter <= 1 else south

    # ========== HELPER FUNCTIONS (v37 verbatim) ==========
    def get_wall(c, r):
        return walls_mem.get((c, r), 0)

    def can_move(c, r, d):
        dc, dr = OFFSETS[d]
        nc, nr = c + dc, r + dr
        if not (0 <= nc < width and south <= nr <= north):
            return False
        return not (get_wall(c, r) & WALL_BITS[d])

    def can_jump(c, r, d):
        dc, dr = OFFSETS[d]
        nc, nr = c + 2 * dc, r + 2 * dr
        if not (0 <= nc < width and south <= nr <= north):
            return False
        return get_wall(nc, nr) != 15

    def action_dest(c, r, act):
        if act.startswith("JUMP_"):
            d = act.split("_")[1]
            dc, dr = OFFSETS[d]
            return c + 2 * dc, r + 2 * dr
        if act in OFFSETS:
            dc, dr = OFFSETS[act]
            return c + dc, r + dr
        return c, r

    # ========== ROBOT CLASSIFICATION (v37 verbatim) ==========
    my_robots = {uid: d for uid, d in obs.robots.items() if d[4] == player}
    enemy_robots = {uid: d for uid, d in obs.robots.items() if d[4] != player}
    enemy_factories = [d for d in enemy_robots.values() if d[0] == FACTORY]
    my_positions = {(d[1], d[2]): uid for uid, d in my_robots.items()}
    reserved = set()
    counts = {rt: sum(1 for d in my_robots.values() if d[0] == rt) for rt in range(4)}

    crystals = {}
    for k, v in obs.crystals.items():
        parts = k.split(",")
        crystals[(int(parts[0]), int(parts[1]))] = v

    mining_nodes = set()
    for k in getattr(obs, "miningNodes", {}):
        parts = k.split(",")
        mining_nodes.add((int(parts[0]), int(parts[1])))

    own_mines = {}
    for k, v in getattr(obs, "mines", {}).items():
        parts = k.split(",")
        pos = (int(parts[0]), int(parts[1]))
        if len(v) >= 3 and v[2] == player:
            own_mines[pos] = v

    # ========== BFS (v37 verbatim) ==========
    def bfs_first_step(start, goals, depth=20, avoid_occupied=True):
        if not goals:
            return None
        goal_set = set(goals)
        if start in goal_set:
            return "IDLE"
        q = deque([(start, None, 0)])
        seen = {start}
        while q:
            (c, r), first_d, dist = q.popleft()
            if (c, r) in goal_set and dist > 0:
                return first_d
            if dist >= depth:
                continue
            for d in DIRS:
                if not can_move(c, r, d):
                    continue
                nc, nr = c + OFFSETS[d][0], r + OFFSETS[d][1]
                if (nc, nr) in seen:
                    continue
                if avoid_occupied and (nc, nr) in reserved:
                    continue
                if avoid_occupied and (nc, nr) in my_positions and (nc, nr) != start:
                    continue
                seen.add((nc, nr))
                q.append(((nc, nr), first_d or d, dist + 1))
        return None

    # ========== ACTION RECORDING (v37 verbatim) ==========
    def record(uid, act, col, row):
        actions[uid] = act
        if act.startswith("JUMP_"):
            d = act.split("_")[1]
            dc, dr = OFFSETS[d]
            reserved.add((col + 2 * dc, row + 2 * dr))
        elif act in OFFSETS:
            dc, dr = OFFSETS[act]
            reserved.add((col + dc, row + dr))
        elif act.startswith("BUILD_"):
            parts = act.split("_")
            d = parts[2] if len(parts) >= 3 and parts[2] in OFFSETS else "NORTH"
            dc, dr = OFFSETS[d]
            reserved.add((col + dc, row + dr))
        else:
            reserved.add((col, row))

    # ========== FIND FACTORY ==========
    factory_uid = None
    factory_col, factory_row = 0, 0
    for uid, d in my_robots.items():
        if d[0] == FACTORY:
            factory_uid = uid
            factory_col, factory_row = d[1], d[2]
            break

    if not factory_uid:
        return actions

    factory_energy = my_robots[factory_uid][3]
    factory_gap = factory_row - south

    fdata = my_robots[factory_uid]
    f_move_cd = fdata[5] if len(fdata) > 5 else 0
    f_jump_cd = fdata[6] if len(fdata) > 6 else 0
    f_build_cd = fdata[7] if len(fdata) > 7 else 0

    # ========== THREAT MAP (v37 verbatim) ==========
    own_support_energy = sum(d[3] for d in my_robots.values() if d[0] != FACTORY)
    own_support_count = sum(1 for d in my_robots.values() if d[0] != FACTORY)
    visible_enemy_support_energy = sum(d[3] for d in enemy_robots.values() if d[0] != FACTORY)
    visible_enemy_support_count = sum(1 for d in enemy_robots.values() if d[0] != FACTORY)
    collision_tiebreak_bad = (
        factory_gap > 3
        and visible_enemy_support_count > 0
        and (
            own_support_energy + 15 < visible_enemy_support_energy
            or (
                own_support_energy <= visible_enemy_support_energy + 15
                and own_support_count < visible_enemy_support_count
            )
        )
    )

    enemy_factory_threats = set()
    enemy_factory_jump_threats = set()
    if collision_tiebreak_bad:
        for enemy in enemy_factories:
            ec, er = enemy[1], enemy[2]
            emove_cd = enemy[5] if len(enemy) > 5 else 0
            ejump_cd = enemy[6] if len(enemy) > 6 else 0
            enemy_factory_threats.add((ec, er))
            if emove_cd <= 1:
                for d in DIRS:
                    if can_move(ec, er, d):
                        enemy_factory_threats.add(action_dest(ec, er, d))
            if ejump_cd <= 0:
                for d in DIRS:
                    if can_jump(ec, er, d):
                        enemy_factory_threats.add(action_dest(ec, er, f"JUMP_{d}"))
    if factory_gap > 3:
        for enemy in enemy_factories:
            ec, er = enemy[1], enemy[2]
            if abs(ec - factory_col) + abs(er - factory_row) > 4:
                continue
            emove_cd = enemy[5] if len(enemy) > 5 else 0
            enemy_factory_jump_threats.add((ec, er))
            if emove_cd <= 1:
                for d in DIRS:
                    if can_move(ec, er, d):
                        enemy_factory_jump_threats.add(action_dest(ec, er, d))

    # ========== BFS DIST TO NORTH TARGET (1-ply feature) ==========
    # Multi-source BFS from cells at target_row, walking edges. Each candidate
    # action's destination gets a `dist_to_target` look-up. This is the
    # "feature" that converts pure 1-ply scoring into wall-aware 1-ply scoring
    # without doing 2-ply tree search over actions.
    target_row = min(north, factory_row + NORTH_BFS_TARGET_OFFSET)

    def build_north_dist():
        dist = {}
        q = deque()
        if south <= target_row <= north:
            for c in range(width):
                dist[(c, target_row)] = 0
                q.append((c, target_row, 0))
        while q:
            c, r, d = q.popleft()
            if d >= NORTH_BFS_MAX_DEPTH:
                continue
            wbits = get_wall(c, r)
            for dir_name in DIRS:
                if wbits & WALL_BITS[dir_name]:
                    continue
                dc, dr = OFFSETS[dir_name]
                nc, nr = c + dc, r + dr
                if not (0 <= nc < width and south <= nr <= north):
                    continue
                if (nc, nr) in dist:
                    continue
                dist[(nc, nr)] = d + 1
                q.append((nc, nr, d + 1))
        return dist

    north_dist = build_north_dist()
    dist_at_factory = north_dist.get((factory_col, factory_row), UNREACHABLE_DIST)

    def dist_at(c, r):
        if not (0 <= c < width and south <= r <= north):
            return UNREACHABLE_DIST
        return north_dist.get((c, r), UNREACHABLE_DIST)

    # ========== 1-PLY FORWARD SIM ==========
    def enumerate_legal_factory_actions():
        out = []
        walk_ok = f_move_cd <= 1
        jump_ok = f_jump_cd <= 0 and f_move_cd <= 0
        for act in CANDIDATE_ORDER:
            if act == "IDLE":
                out.append(act)
                continue
            if act in OFFSETS:
                if not walk_ok:
                    continue
                if not can_move(factory_col, factory_row, act):
                    continue
                dest = action_dest(factory_col, factory_row, act)
                if dest[1] < south:
                    continue
                if dest in my_positions and my_positions[dest] != factory_uid:
                    continue
                out.append(act)
            elif act.startswith("JUMP_"):
                if not jump_ok:
                    continue
                d = act.split("_")[1]
                if not can_jump(factory_col, factory_row, d):
                    continue
                dest = action_dest(factory_col, factory_row, act)
                if not (0 <= dest[0] < width and south <= dest[1] <= north):
                    continue
                if dest in my_positions and my_positions[dest] != factory_uid:
                    continue
                out.append(act)
        return out

    def cost_after_1ply(act):
        if act == "IDLE":
            new_c, new_r = factory_col, factory_row
            cd_lock = 0
        elif act in OFFSETS:
            dc, dr = OFFSETS[act]
            new_c, new_r = factory_col + dc, factory_row + dr
            cd_lock = FACTORY_MOVE_PERIOD
        else:
            d = act.split("_")[1]
            dc, dr = OFFSETS[d]
            new_c, new_r = factory_col + 2 * dc, factory_row + 2 * dr
            cd_lock = FACTORY_JUMP_COOLDOWN

        # c1: death predicate (predicted next-turn gap collapses).
        # Death threshold is env-overridable: spec says <=1, but at high
        # scroll rates the agent needs a fatter safety buffer.
        new_gap_pred = new_r - pred_south_next
        c1 = 1.0 if new_gap_pred <= DEATH_GAP_THRESHOLD else 0.0

        # c2: north-distance reduction toward target_row (BFS-informed).
        # Positive value = action moved us closer to NORTH band, lower cost.
        # For IDLE, dist_at_dest == dist_at_factory, so c2 = 0.
        # For NORTH walk on shortest path: dist_reduction = 1.
        # For JUMP_NORTH landing on shortest path: dist_reduction = 2.
        # For EAST walk that opens new NORTH path: dist_reduction = 1
        #   (this is how cost beats IDLE when NORTH-wall blocks the cell).
        # For unreachable dest: dist_reduction is large negative (bad).
        dist_at_dest = dist_at(new_c, new_r)
        dist_reduction = dist_at_factory - dist_at_dest
        c2 = -float(dist_reduction)

        # c3: collision predicate
        c3 = 0.0
        if (new_c, new_r) in enemy_factory_threats:
            c3 = 1.0
        if act.startswith("JUMP_") and (new_c, new_r) in enemy_factory_jump_threats:
            c3 = 1.0

        # c4: cd lock scaled by need probability (use NEW gap so jumps that
        # put us in safe territory are cheap to lock; jumps from low gap that
        # keep us low are still expensive).
        c4 = cd_lock * p_need_jump(new_gap_pred)

        # c5: energy change (mine fill = +50)
        delta = 50 if (new_c, new_r) in own_mines else 0
        c5 = -float(delta)

        # c6: mine dwell bonus (subtracted -> negative cost contribution)
        c6 = 1.0 if (new_c, new_r) in own_mines else 0.0

        return (
            W_DEATH * c1 + W_NORTH * c2 + W_COLLISION * c3
            + W_CD_LOCK * c4 + W_ENERGY * c5 - W_MINE * c6
        )

    # ========== FACTORY DECISION ==========
    # Keep v37 build heuristics intact (early miner, late scout). When no
    # build triggers, fall through to cost-based movement.
    if factory_uid not in actions:
        spawn = (factory_col, factory_row + 1)
        mine_build_action = None
        if f_build_cd <= 1 and factory_energy >= 650 and factory_gap > 6 and counts[MINER] < 1:
            for d in ("NORTH",):
                dc, dr = OFFSETS[d]
                mpos = (factory_col + dc, factory_row + dr)
                if mpos not in mining_nodes or mpos in my_positions:
                    continue
                if not can_move(factory_col, factory_row, d):
                    continue
                mine_build_action = f"BUILD_MINER_{d}"
                break

        spawn_ok = (
            f_build_cd <= 1
            and spawn not in my_positions
            and factory_row + 1 <= north
            and not (get_wall(factory_col, factory_row) & WALL_BITS["NORTH"])
        )

        if mine_build_action:
            record(factory_uid, mine_build_action, factory_col, factory_row)
            counts[MINER] += 1
        elif (
            turn >= SCOUT_DELAY_STEP
            and spawn_ok
            and counts[SCOUT] < 1
            and factory_energy >= 50
            and factory_gap > 4
        ):
            record(factory_uid, "BUILD_SCOUT", factory_col, factory_row)
            counts[SCOUT] += 1
        else:
            candidates = enumerate_legal_factory_actions()
            if not candidates:
                step = "IDLE"
                if f_jump_cd <= 0 and f_move_cd <= 0:
                    for d in ("NORTH", "EAST", "WEST", "SOUTH"):
                        if can_jump(factory_col, factory_row, d):
                            dest = action_dest(factory_col, factory_row, f"JUMP_{d}")
                            if 0 <= dest[0] < width and south <= dest[1] <= north:
                                step = f"JUMP_{d}"
                                break
                record(factory_uid, step, factory_col, factory_row)
            else:
                scored = [(act, cost_after_1ply(act)) for act in candidates]
                best_act, _best_cost = min(scored, key=lambda x: x[1])
                # Last-resort worker spawn (mirrors v37) when cost picks IDLE
                # while gap critical and we still have spare energy.
                if (
                    best_act == "IDLE"
                    and spawn_ok
                    and counts[WORKER] < 1
                    and factory_energy >= 200
                    and factory_gap <= 4
                ):
                    record(factory_uid, "BUILD_WORKER", factory_col, factory_row)
                    counts[WORKER] += 1
                else:
                    record(factory_uid, best_act, factory_col, factory_row)

    # ========== SCOUT (v37 verbatim) ==========
    scouts = [(uid, d) for uid, d in my_robots.items() if d[0] == SCOUT]
    for uid, data in scouts:
        col, row = data[1], data[2]
        move_cd = data[5] if len(data) > 5 else 0
        if move_cd > 1:
            record(uid, "IDLE", col, row)
            continue
        scout_goals = [(tc, min(north, factory_row + 8)) for tc in range(width)]
        step = bfs_first_step((col, row), scout_goals, depth=12)
        if not step or step == "IDLE":
            for d in ("NORTH", "EAST", "WEST"):
                if can_move(col, row, d):
                    nc, nr = col + OFFSETS[d][0], row + OFFSETS[d][1]
                    if (nc, nr) not in reserved and (nc, nr) not in my_positions:
                        step = d
                        break
        if step and step != "IDLE":
            record(uid, step, col, row)
        else:
            record(uid, "IDLE", col, row)

    # ========== MINER (v37 verbatim) ==========
    miners = [(uid, d) for uid, d in my_robots.items() if d[0] == MINER]
    for uid, data in miners:
        col, row = data[1], data[2]
        energy = data[3]
        if (col, row) in mining_nodes and energy >= 100:
            record(uid, "TRANSFORM", col, row)
        else:
            record(uid, "IDLE", col, row)

    # ========== WORKER (v37 verbatim) ==========
    workers = [(uid, d) for uid, d in my_robots.items() if d[0] == WORKER]
    for uid, data in workers:
        col, row = data[1], data[2]
        energy = data[3]
        move_cd = data[5] if len(data) > 5 else 0
        if (get_wall(col, row) & WALL_BITS["NORTH"]) and energy >= 100:
            record(uid, "REMOVE_NORTH", col, row)
            continue
        if move_cd > 1:
            record(uid, "IDLE", col, row)
            continue
        worker_gap = row - south
        if worker_gap <= 4:
            target_goals = [(factory_col, min(north, factory_row + 5))]
        else:
            nearby_crystals = [
                c for c in crystals if abs(c[0] - col) + abs(c[1] - row) <= 8
            ]
            if nearby_crystals:
                target_goals = sorted(nearby_crystals, key=lambda t: abs(t[0] - col) + abs(t[1] - row))[:3]
            else:
                target_goals = [(factory_col, min(north, factory_row + 5))]
        step = bfs_first_step((col, row), target_goals, depth=10)
        if not step or step == "IDLE":
            for d in ("NORTH", "EAST", "WEST"):
                if can_move(col, row, d):
                    nc, nr = col + OFFSETS[d][0], row + OFFSETS[d][1]
                    if (nc, nr) not in reserved and (nc, nr) not in my_positions:
                        step = d
                        break
        if step and step != "IDLE":
            record(uid, step, col, row)
        else:
            record(uid, "IDLE", col, row)

    for uid in my_robots:
        if uid not in actions:
            actions[uid] = "IDLE"

    if _ACTION_LOG and factory_uid in actions:
        try:
            with open(_ACTION_LOG, "a") as f:
                f.write(
                    f"{turn}\t{actions[factory_uid]}\tgap={factory_gap}\t"
                    f"est_cnt={est_counter}\tmcd={f_move_cd}\tjcd={f_jump_cd}\n"
                )
        except Exception:
            pass

    return actions


def agent(obs, config):
    """Public entry point. Wraps _agent_inner for exception safety + optional
    per-turn timing logging (set V56_TIMING_LOG=path to enable).

    kaggle_environments loads the LAST callable defined in the module — keep
    `agent` after `_agent_inner`.
    """
    if _TIMING_LOG:
        t0 = time.perf_counter()
        try:
            actions = _agent_inner(obs, config)
        except Exception:
            actions = {uid: "IDLE" for uid in obs.robots if obs.robots[uid][4] == obs.player}
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        try:
            with open(_TIMING_LOG, "a") as f:
                f.write(f"{getattr(obs, 'step', -1)}\t{elapsed_ms:.3f}\n")
        except Exception:
            pass
        return actions
    try:
        return _agent_inner(obs, config)
    except Exception:
        return {uid: "IDLE" for uid in obs.robots if obs.robots[uid][4] == obs.player}
