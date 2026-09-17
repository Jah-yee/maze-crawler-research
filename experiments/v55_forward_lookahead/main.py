"""
v55 Maze Crawler Agent: 1-ply forward simulation PoC (W-Forward).

Replaces v37's factory **movement** decision (the elif chain + jump-BFS) with a
1-ply lightweight self-simulation that scores each legal factory action by a
5-term cost function and picks argmin.

Cost terms (W2 recommendation, weights [1.0, 100.0, 0.5, 0.05, 5.0]):
  c1 north_progress      = -(new_row - factory_row)
  c2 collision_prob      = 1 if dest in enemy_factory_threats (or jump_threats)
  c3 cooldown_lock_cost  = factoryMovePeriod for walks, factoryJumpCooldown for
                           jumps, 0 for IDLE; build branches skip cost (we keep
                           v37's build heuristics as cross-turn strategy)
  c4 energy_change       = -delta_energy (only own_mine-fill counted, +50)
  bonus mine_dwell       = 1 if dest in own_mines

total_cost = 1.0*c1 + 100.0*c2 + 0.5*c3 + 0.05*c4 - 5.0*bonus_mine_dwell

Per task: real `kaggle_environments.step` is rejected because the agent does
not own the hidden global state (globalWalls outside fog, scroll RNG seed,
enemy intent). Lightweight self-sim covers the deterministic factory delta in
under 1ms total / turn — verified by `instrument_timing` (Step 5).

What is **kept** from v37 verbatim: BFS helpers, can_move/can_jump, wall
memory/mirroring, threat detection (enemy_factory_threats /
enemy_factory_jump_threats), scout / worker / miner planners, build heuristics
(early miner, late scout, desperate worker fallback).

What is **replaced**: the entire factory movement elif chain — emergency
JUMP_NORTH at gap<=2, mine-dwell IDLE, BFS-jump pathfinding, lateral
desperation jumps. Now: enumerate 9 legal candidates, cost each, argmin.

Risk acknowledged in executor log: 5-term cost has no scroll-survival
predictor. At gap<=2, IDLE (cost 0) ties or beats JUMP_NORTH (cost 8), so the
agent may IDLE itself to death. Strict-spec PoC; data should reveal whether
the cost terms are sufficient.
"""
import os
import time
from collections import deque

FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}
SCOUT_DELAY_STEP = 24

# Factory move/jump cooldown values (env defaults, hard-coded since obs has no
# config access). factoryMovePeriod=2, factoryJumpCooldown=20.
FACTORY_MOVE_PERIOD = 2
FACTORY_JUMP_COOLDOWN = 20

# Cost weights (W2 default, locked in for first PoC pass).
W_NORTH = 1.0
W_COLLISION = 100.0
W_CD_LOCK = 0.5
W_ENERGY = 0.05
W_MINE = 5.0

# Tie-break ordering: when two candidates produce identical cost, we prefer
# the earlier-listed one. North-pushing actions come first.
CANDIDATE_ORDER = (
    "NORTH", "JUMP_NORTH",
    "EAST", "WEST",
    "JUMP_EAST", "JUMP_WEST",
    "IDLE",
    "SOUTH", "JUMP_SOUTH",
)

# Optional turn-timing instrumentation (Step 5). Activated by env var
# V55_TIMING_LOG; otherwise zero overhead.
_TIMING_LOG = os.environ.get("V55_TIMING_LOG", "").strip()

# Precompute mirror wall lookup: E<->W swap, N and S unchanged
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

    # ========== PERSISTENT WALL MEMORY (v37 verbatim) ==========
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

    # ========== BFS: STANDARD (v37 verbatim, used by scouts/workers) ==========
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

    # ========== FIND FACTORY (v37 verbatim) ==========
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

    # ========== 1-PLY FORWARD SIM: factory action enumeration ==========
    def enumerate_legal_factory_actions():
        """Return the legal subset of CANDIDATE_ORDER for the current factory.

        Legality (basic survival, not strategy):
        - Walks need can_move + factory move CD ready (<=1 observed -> ticks to 0).
        - Jumps need can_jump + jump CD ready (<=0 observed) + move CD ready
          (<=0; env requires both ==0 post-tick; observed move_cd==0 means
          it was already 0 before tick, can still jump). To match v37 we use
          jump_cd<=0 AND move_cd<=0; this is conservative but safe.
        - Walking off south (dest_row<south) excluded (off-board death).
        - Walking onto own non-factory unit excluded (factory crushes friendly,
          wasted unit).
        - Jumping off the active window excluded (factory dies).
        - IDLE always legal.
        """
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
        """Score act with the 5-term cost. Lower is better."""
        if act == "IDLE":
            new_c, new_r = factory_col, factory_row
            cd_lock = 0
        elif act in OFFSETS:
            dc, dr = OFFSETS[act]
            new_c, new_r = factory_col + dc, factory_row + dr
            cd_lock = FACTORY_MOVE_PERIOD
        else:  # JUMP_<DIR>
            d = act.split("_")[1]
            dc, dr = OFFSETS[d]
            new_c, new_r = factory_col + 2 * dc, factory_row + 2 * dr
            cd_lock = FACTORY_JUMP_COOLDOWN

        c1 = -(new_r - factory_row)

        c2 = 0.0
        if (new_c, new_r) in enemy_factory_threats:
            c2 = 1.0
        if act.startswith("JUMP_") and (new_c, new_r) in enemy_factory_jump_threats:
            c2 = 1.0

        c3 = cd_lock

        delta = 50 if (new_c, new_r) in own_mines else 0
        c4 = -float(delta)

        bonus = 1 if (new_c, new_r) in own_mines else 0

        return W_NORTH * c1 + W_COLLISION * c2 + W_CD_LOCK * c3 + W_ENERGY * c4 - W_MINE * bonus

    # ========== FACTORY DECISION ==========
    # We keep v37's build heuristics (cross-turn strategy = "helper") and only
    # replace the *movement* selection with cost-based 1-ply argmin. When no
    # build trigger fires, we enter the cost-based selector.

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
            # ----- 1-PLY COST-BASED MOVEMENT SELECTION -----
            candidates = enumerate_legal_factory_actions()
            if not candidates:
                # No legal action at all (extremely rare; e.g. surrounded). Try
                # desperate last-resort jump if jump CD ready, else IDLE.
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
                # Last-resort worker spawn if cost picks IDLE while gap critical
                # and no other safety net (mirrors v37's last fallback). Only
                # when cost-based pick is IDLE, gap<=4, and we have spare energy.
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

    # ========== SCOUT PLANNING (v37 verbatim) ==========
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

    # ========== MINER PLANNING (v37 verbatim) ==========
    miners = [(uid, d) for uid, d in my_robots.items() if d[0] == MINER]
    for uid, data in miners:
        col, row = data[1], data[2]
        energy = data[3]
        if (col, row) in mining_nodes and energy >= 100:
            record(uid, "TRANSFORM", col, row)
        else:
            record(uid, "IDLE", col, row)

    # ========== WORKER PLANNING (v37 verbatim) ==========
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

    # ========== DEFAULT ==========
    for uid in my_robots:
        if uid not in actions:
            actions[uid] = "IDLE"

    return actions


def agent(obs, config):
    """Public entry point. Wraps `_agent_inner` for exception safety + optional
    per-turn timing logging (set V55_TIMING_LOG=path to enable).

    NOTE: kaggle_environments' agent loader picks the LAST callable defined in
    the module, so this function MUST be defined after `_agent_inner`.
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
