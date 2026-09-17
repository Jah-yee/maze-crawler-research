"""
v59 Phase-Switch Architecture (bunterrrrr explicit phase switch paradigm).

Derives from v58_v50_r1_hash (v50 SCORERS + Knob 1 fix + anti-mirror hash).
The key change vs v58 is replacing the four-phase system with a three-phase
explicit mode switch that directly encodes bunterrrrr's observed strategy:

  Phase 0 - MINE_SPRINT  (step < 30, no scout, mine any direction)
  Phase 1 - CONVEYOR     (hybrid north BFS + moderate mining)
  Phase 2 - SPRINT       (no BUILD_*, forced north, skip mine idle)

Phase transitions are smooth, using energy/miner/scroll state as triggers.

Design doc: docs/research.md §"Late-Game Learning From bunterrrrr"
"""
from collections import deque
from enum import IntEnum

# ============================================================================
# W10 - Philosophy encoded as constants
# ============================================================================
# Derivation principle #1 (Survival floor): gap <= 2 emergency escape.
# Derivation principle #2 (Early compound): ANY-direction mining in Phase 0.
# Derivation principle #3 (Smooth phase switch): transitions use energy,
#   miner count, and scroll speed, not just step thresholds.
# Derivation principle #4 (Sprint): abandoned economy, forced north.

# ----- thresholds (inherited from v37 / v50 / v58) -----
SCOUT_DELAY_STEP = 24       # v19/v37: don't BUILD_SCOUT before step 24
EMERGENCY_GAP = 2           # gap <= 2 triggers emergency escape (v37)
LOW_GAP_NORTH_ONLY = 8      # gap <= 8: bfs_jump restricted to JUMP_NORTH (v37)
SCOUT_GAP_GATE = 4          # gap <= 4: skip BUILD_SCOUT (v37)
MINE_GAP_GATE = 6           # gap <= 6: skip BUILD_MINER_NORTH (v37)
MINE_ENERGY_FLOOR = 650     # min energy to BUILD_MINER (v37)
SCOUT_ENERGY_FLOOR = 50     # min energy to BUILD_SCOUT (v37)
WORKER_ENERGY_FLOOR = 200   # min energy to BUILD_WORKER last resort (v37)
WORKER_GAP_GATE = 4         # only build worker when stuck near south (v37)
IDLE_ON_MINE_GAP = 10       # gap > 10 + on own mine: park to recharge (v37)

# ----- phase transition thresholds -----
PHASE0_MAX_STEP = 30        # step < 30 is MINE_SPRINT territory
PHASE0_ENERGY_EXIT = 1500   # leave Phase 0 earlier if miner + energy > this
PHASE1_MAX_STEP = 250       # enter SPRINT when step >= this
PHASE1_GAP_EXIT = 6         # enter SPRINT when gap <= this
SCROLL_SPEED_HIGH = 4       # scroll interval <= 4 = scroll is fast

# ----- priority bands (encode v37's elif ordering as additive scores) -----
# Higher = picked first. Each band is well-separated so a band always
# dominates the next one; scorers within a band are intentionally exclusive.
PRI_EMERGENCY_N = 10_000_000
PRI_EMERGENCY_EW = 9_500_000
PRI_MINE_BUILD = 9_000_000
PRI_SCOUT_BUILD = 8_000_000
PRI_IDLE_CD = 7_000_000
PRI_IDLE_ON_MINE = 6_000_000
PRI_WALK_OWN_MINE = 5_500_000
PRI_MOVE_MAIN = 5_000_000
PRI_MOVE_CLOSER = 4_500_000
PRI_MOVE_ANY_NORTH = 4_000_000
PRI_MOVE_SOUTH = 3_500_000
PRI_MOVE_DESPERATION = 3_000_000
PRI_BUILD_WORKER = 2_000_000
PRI_IDLE_FINAL = 1_000_000

NO_PROPOSAL = ("IDLE", float("-inf"))  # sentinel: scorer abstains


# ============================================================================
# Three-phase system
# ============================================================================
class Phase(IntEnum):
    MINE_SPRINT = 0   # step < 30, no scout, mine any direction
    CONVEYOR = 1      # hybrid north BFS + moderate mining
    SPRINT = 2        # no BUILD_*, forced north, skip mine idle


def scroll_interval(step: int) -> float:
    """Linear interpolation of scroll interval from 10 to 2 over 450 steps."""
    return max(2.0, 10.0 - (step / 450.0) * 8.0)


def current_phase(step: int, factory_gap: int, miner_count: int, factory_energy: int) -> Phase:
    """Smooth three-phase transition.

    Phase 0 -> 1: step >= 30 OR (miner exists AND energy > 1500)
    Phase 1 -> 2: step >= 250 OR gap <= 6 OR scroll speed high
    """
    si = scroll_interval(step)
    # Phase 0 check
    in_mine_sprint = step < PHASE0_MAX_STEP and not (miner_count > 0 and factory_energy > PHASE0_ENERGY_EXIT)
    if in_mine_sprint:
        return Phase.MINE_SPRINT
    # Phase 2 check
    if step >= PHASE1_MAX_STEP or factory_gap <= PHASE1_GAP_EXIT or si <= SCROLL_SPEED_HIGH:
        return Phase.SPRINT
    return Phase.CONVEYOR


# ============================================================================
# Constants copied from v37 / v58
# ============================================================================
FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
DIRS_P0 = ("NORTH", "EAST", "WEST", "SOUTH")
DIRS_P1 = ("NORTH", "WEST", "EAST", "SOUTH")
HASH_SALT = b"\x9a\x7d\xc4\x33\x88\x21\x55\x77"
PERTURB_THRESHOLD = 77   # 77/256 ≈ 30.1% of turns swap lateral order
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}

MIRROR_WALL = [0] * 16
for _v in range(16):
    _m = (_v & 1) | (_v & 4)
    if _v & 2:
        _m |= 8
    if _v & 8:
        _m |= 2
    MIRROR_WALL[_v] = _m

_memory = {}


def agent(obs, config):
    """Main entry point - wrapped for exception safety."""
    global _memory
    try:
        return _agent_inner(obs, config)
    except Exception:
        return {uid: "IDLE" for uid in obs.robots if obs.robots[uid][4] == obs.player}


def _agent_inner(obs, config):
    global _memory
    actions = {}
    width = config.width
    south = obs.southBound
    north = obs.northBound
    player = obs.player
    turn = getattr(obs, "step", 0)

    # ------------------------------------------------------------------
    # Anti-mirror direction ordering (D01/D02 + D03 hash perturbation)
    # ------------------------------------------------------------------
    base_dir_order = DIRS_P0 if player == 0 else DIRS_P1
    lateral_order = ("EAST", "WEST") if player == 0 else ("WEST", "EAST")
    bfs_dirs = base_dir_order

    # ------------------------------------------------------------------
    # Persistent wall memory (verbatim from v37)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Geometry helpers (verbatim from v37)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Robot classification (verbatim from v37)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # BFS helpers (verbatim from v37)
    # ------------------------------------------------------------------
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
            for d in bfs_dirs:
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

    def bfs_jump(start, goals, jump_cd, depth=20, north_only_jump=False):
        if not goals:
            return None
        goal_set = set(goals)
        q = deque([(start, None, 0, min(jump_cd, 20))])
        seen = {(start[0], start[1], jump_cd <= 0)}
        jump_dirs = ("NORTH",) if north_only_jump else bfs_dirs
        while q:
            (c, r), first_d, dist, jcd = q.popleft()
            if (c, r) in goal_set and dist > 0:
                return first_d
            if dist >= depth:
                continue
            if jcd <= 0:
                for d in jump_dirs:
                    if not can_jump(c, r, d):
                        continue
                    dc, dr = OFFSETS[d]
                    nc, nr = c + 2 * dc, r + 2 * dr
                    key = (nc, nr, False)
                    if key in seen:
                        continue
                    seen.add(key)
                    q.append(((nc, nr), first_d or f"JUMP_{d}", dist + 1, 20))
            for d in bfs_dirs:
                if not can_move(c, r, d):
                    continue
                nc, nr = c + OFFSETS[d][0], r + OFFSETS[d][1]
                njcd = max(0, jcd - 1)
                key = (nc, nr, njcd <= 0)
                if key in seen:
                    continue
                seen.add(key)
                q.append(((nc, nr), first_d or d, dist + 1, njcd))
        return None

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

    # ------------------------------------------------------------------
    # Find factory (verbatim from v37)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Threat tables (verbatim from v37 / v58 Knob 1 fix)
    # ------------------------------------------------------------------
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
    for enemy in enemy_factories:
        enemy_factory_threats.add((enemy[1], enemy[2]))
    if collision_tiebreak_bad:
        for enemy in enemy_factories:
            ec, er = enemy[1], enemy[2]
            emove_cd = enemy[5] if len(enemy) > 5 else 0
            ejump_cd = enemy[6] if len(enemy) > 6 else 0
            if emove_cd <= 2:  # Knob 1: 2-turn predictor (was <= 1)
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

    def safe_factory_action(act):
        dest = action_dest(factory_col, factory_row, act)
        if enemy_factory_threats and dest in enemy_factory_threats:
            return False
        if act.startswith("JUMP_") and dest in enemy_factory_jump_threats:
            return False
        return True

    # ==================================================================
    # FACTORY SCORERS
    # ==================================================================
    spawn_pos = (factory_col, factory_row + 1)
    spawn_ok = (
        f_build_cd <= 1
        and spawn_pos not in my_positions
        and factory_row + 1 <= north
        and not (get_wall(factory_col, factory_row) & WALL_BITS["NORTH"])
    )

    ctx = {
        "obs": obs,
        "config": config,
        "phase": current_phase(turn, factory_gap, counts[MINER], factory_energy),
        "turn": turn,
        "south": south,
        "north": north,
        "width": width,
        "factory_uid": factory_uid,
        "factory_col": factory_col,
        "factory_row": factory_row,
        "factory_gap": factory_gap,
        "factory_energy": factory_energy,
        "f_move_cd": f_move_cd,
        "f_jump_cd": f_jump_cd,
        "f_build_cd": f_build_cd,
        "counts": counts,
        "spawn_ok": spawn_ok,
        "mining_nodes": mining_nodes,
        "own_mines": own_mines,
        "my_positions": my_positions,
        "scroll_interval": scroll_interval(turn),
        # helpers
        "can_move": can_move,
        "can_jump": can_jump,
        "get_wall": get_wall,
        "safe_factory_action": safe_factory_action,
        "bfs_jump": bfs_jump,
        "bfs_first_step": bfs_first_step,
    }

    def score_emergency_escape(ctx):
        gap = ctx["factory_gap"]
        if not (gap <= EMERGENCY_GAP and ctx["south"] > 0):
            return NO_PROPOSAL
        if ctx["f_jump_cd"] > 0:
            return NO_PROPOSAL
        col, row = ctx["factory_col"], ctx["factory_row"]
        uid = ctx["factory_uid"]
        my_pos = ctx["my_positions"]

        if ctx["can_jump"](col, row, "NORTH") and ctx["safe_factory_action"]("JUMP_NORTH"):
            nc, nr = col, row + 2
            if (nc, nr) not in my_pos or my_pos.get((nc, nr)) == uid:
                return ("JUMP_NORTH", PRI_EMERGENCY_N)
            return NO_PROPOSAL

        for d in ("EAST", "WEST"):
            act = f"JUMP_{d}"
            if ctx["can_jump"](col, row, d) and ctx["safe_factory_action"](act):
                dc, dr = OFFSETS[d]
                nc, nr = col + 2 * dc, row + 2 * dr
                if (nc, nr) not in my_pos or my_pos.get((nc, nr)) == uid:
                    return (act, PRI_EMERGENCY_EW)
        return NO_PROPOSAL

    def score_mine_econ_build(ctx):
        """Phase-aware miner building.

        Phase 0 (MINE_SPRINT): BUILD_MINER in ANY direction when adjacent node.
        Phase 1 (CONVEYOR):    north-only miner with gap/count gates.
        Phase 2 (SPRINT):      no miner building.
        """
        phase = ctx["phase"]
        if phase == Phase.SPRINT:
            return NO_PROPOSAL
        if not (
            ctx["f_build_cd"] <= 1
            and ctx["factory_energy"] >= MINE_ENERGY_FLOOR
        ):
            return NO_PROPOSAL
        col, row = ctx["factory_col"], ctx["factory_row"]

        if phase == Phase.MINE_SPRINT:
            for d in DIRS:
                dc, dr = OFFSETS[d]
                mpos = (col + dc, row + dr)
                if mpos in ctx["mining_nodes"] and mpos not in ctx["my_positions"]:
                    if ctx["can_move"](col, row, d):
                        return (f"BUILD_MINER_{d}", PRI_MINE_BUILD)
            return NO_PROPOSAL

        if ctx["factory_gap"] > MINE_GAP_GATE and ctx["counts"][MINER] < 1:
            dc, dr = OFFSETS["NORTH"]
            mpos = (col + dc, row + dr)
            if mpos in ctx["mining_nodes"] and mpos not in ctx["my_positions"]:
                if ctx["can_move"](col, row, "NORTH"):
                    return ("BUILD_MINER_NORTH", PRI_MINE_BUILD)
        return NO_PROPOSAL

    def score_scout_build(ctx):
        """Phase-aware scout building.

        Phase 0 (MINE_SPRINT) and Phase 2 (SPRINT): no scout building.
        Phase 1 (CONVEYOR): scout allowed with existing gates.
        """
        phase = ctx["phase"]
        if phase in (Phase.MINE_SPRINT, Phase.SPRINT):
            return NO_PROPOSAL
        if not (
            ctx["turn"] >= SCOUT_DELAY_STEP
            and ctx["spawn_ok"]
            and ctx["counts"][SCOUT] < 1
            and ctx["factory_energy"] >= SCOUT_ENERGY_FLOOR
            and ctx["factory_gap"] > SCOUT_GAP_GATE
        ):
            return NO_PROPOSAL
        return ("BUILD_SCOUT", PRI_SCOUT_BUILD)

    def score_idle_cooldown(ctx):
        if ctx["f_move_cd"] > 1:
            return ("IDLE", PRI_IDLE_CD)
        return NO_PROPOSAL

    def score_idle_on_mine(ctx):
        """Skip mine-collection IDLE in Phase 2 (SPRINT)."""
        if ctx["phase"] == Phase.SPRINT:
            return NO_PROPOSAL
        pos = (ctx["factory_col"], ctx["factory_row"])
        if pos in ctx["own_mines"] and ctx["factory_gap"] > IDLE_ON_MINE_GAP:
            return ("IDLE", PRI_IDLE_ON_MINE)
        return NO_PROPOSAL

    def score_walk_to_own_mine(ctx):
        """Skip mine walk in Phase 2 (SPRINT)."""
        if ctx["phase"] == Phase.SPRINT:
            return NO_PROPOSAL
        col, row = ctx["factory_col"], ctx["factory_row"]
        d = "NORTH"
        dc, dr = OFFSETS[d]
        mpos = (col + dc, row + dr)
        if (
            mpos in ctx["own_mines"]
            and ctx["can_move"](col, row, d)
            and ctx["safe_factory_action"](d)
        ):
            return (d, PRI_WALK_OWN_MINE)
        return NO_PROPOSAL

    def score_factory_move(ctx):
        """Phase-aware factory movement.

        Phase 0 (MINE_SPRINT): north-only BFS with jump save, prefer IDLE over lateral.
        Phase 1 (CONVEYOR):    standard hybrid BFS (as v58).
        Phase 2 (SPRINT):      forced north (JUMP_NORTH > NORTH > desperation).
        """
        col, row = ctx["factory_col"], ctx["factory_row"]
        gap = ctx["factory_gap"]
        north_bd = ctx["north"]
        width_ = ctx["width"]
        phase = ctx["phase"]

        # --- Phase 2: SPRINT - forced north, no lateral wandering ---
        if phase == Phase.SPRINT:
            if ctx["f_jump_cd"] <= 0:
                act = "JUMP_NORTH"
                if ctx["can_jump"](col, row, "NORTH") and ctx["safe_factory_action"](act):
                    return (act, PRI_MOVE_MAIN)
            if ctx["can_move"](col, row, "NORTH") and ctx["safe_factory_action"]("NORTH"):
                return ("NORTH", PRI_MOVE_ANY_NORTH)
            for d in ("EAST", "WEST"):
                if ctx["can_move"](col, row, d) and ctx["safe_factory_action"](d):
                    return (d, PRI_MOVE_DESPERATION)
            return NO_PROPOSAL

        # --- Phase 0: MINE_SPRINT - north-only BFS, save jumps ---
        north_only = (phase == Phase.MINE_SPRINT) or (gap <= LOW_GAP_NORTH_ONLY)

        target_row = min(north_bd, row + 20)
        factory_goals = [(tc, target_row) for tc in range(width_)]
        step = ctx["bfs_jump"](
            (col, row), factory_goals, ctx["f_jump_cd"],
            depth=20, north_only_jump=north_only,
        )
        if step and not ctx["safe_factory_action"](step):
            step = None
        if step and step != "IDLE":
            return (step, PRI_MOVE_MAIN)

        closer_goals = [(tc, min(north_bd, row + 5)) for tc in range(width_)]
        step = ctx["bfs_first_step"]((col, row), closer_goals, depth=10, avoid_occupied=False)
        if step and not ctx["safe_factory_action"](step):
            step = None
        if step and step != "IDLE":
            return (step, PRI_MOVE_CLOSER)

        # --- Phase 0: only NORTH, no lateral ---
        if phase == Phase.MINE_SPRINT:
            if ctx["can_move"](col, row, "NORTH") and ctx["safe_factory_action"]("NORTH"):
                return ("NORTH", PRI_MOVE_ANY_NORTH)
            return NO_PROPOSAL

        # --- Phase 1: normal fallback chain ---
        for d in ("NORTH", "EAST", "WEST"):
            if ctx["can_move"](col, row, d) and ctx["safe_factory_action"](d):
                return (d, PRI_MOVE_ANY_NORTH)

        if gap <= 3 and ctx["can_move"](col, row, "SOUTH") and ctx["safe_factory_action"]("SOUTH"):
            return ("SOUTH", PRI_MOVE_SOUTH)

        if gap <= 3 and ctx["f_jump_cd"] <= 0:
            for d in ("EAST", "WEST", "SOUTH"):
                act = f"JUMP_{d}"
                if ctx["can_jump"](col, row, d) and ctx["safe_factory_action"](act):
                    return (act, PRI_MOVE_DESPERATION)

        return NO_PROPOSAL

    def score_build_worker(ctx):
        if ctx["phase"] == Phase.SPRINT:
            return NO_PROPOSAL
        if not (
            ctx["spawn_ok"]
            and ctx["counts"][WORKER] < 1
            and ctx["factory_energy"] >= WORKER_ENERGY_FLOOR
            and ctx["factory_gap"] <= WORKER_GAP_GATE
        ):
            return NO_PROPOSAL
        return ("BUILD_WORKER", PRI_BUILD_WORKER)

    def score_fallback_idle(ctx):
        return ("IDLE", PRI_IDLE_FINAL)

    SCORERS = [
        score_emergency_escape,
        score_mine_econ_build,
        score_scout_build,
        score_idle_cooldown,
        score_idle_on_mine,
        score_walk_to_own_mine,
        score_factory_move,
        score_build_worker,
        score_fallback_idle,
    ]

    def pick_factory_action(ctx):
        best_act, best_score = "IDLE", float("-inf")
        for scorer in SCORERS:
            act, score = scorer(ctx)
            if score > best_score:
                best_act, best_score = act, score
        return best_act

    factory_act = pick_factory_action(ctx)
    record(factory_uid, factory_act, factory_col, factory_row)
    if factory_act.startswith("BUILD_MINER_"):
        counts[MINER] += 1
    elif factory_act == "BUILD_SCOUT":
        counts[SCOUT] += 1
    elif factory_act == "BUILD_WORKER":
        counts[WORKER] += 1

    # ==================================================================
    # SCOUT / MINER / WORKER planning (verbatim from v37)
    # ==================================================================
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

    miners = [(uid, d) for uid, d in my_robots.items() if d[0] == MINER]
    for uid, data in miners:
        col, row = data[1], data[2]
        energy = data[3]
        if (col, row) in mining_nodes and energy >= 100:
            record(uid, "TRANSFORM", col, row)
        else:
            record(uid, "IDLE", col, row)

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
                target_goals = sorted(
                    nearby_crystals, key=lambda t: abs(t[0] - col) + abs(t[1] - row)
                )[:3]
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

    return actions
