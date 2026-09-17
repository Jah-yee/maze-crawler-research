"""
v58_v50_r1_hash: v50 utility scoring + P01 Knob1 fix + R1 TRANSFER_NORTH + anti-IL hash.

Built on v50_utility_arch (parity PASS vs v37, z=-0.09). Three behavioral
additions vs v50:

1. P01 (correctness): enemy factory's current cell is ALWAYS an unsafe
   destination, not only when collision_tiebreak_bad is True. Fixes replay
   78598494-style factory-ramming losses.

2. R1 TRANSFER_NORTH (W-Tree L02/L08): when no miner exists and north
   neighbour has a support with energy 280-600, donate energy via TRANSFER.
   Added as a scorer between mine_build and scout_build in priority.

3. Anti-IL hash perturbation (v49 style): player-asymmetric DIRS + ~30%
   deterministic hash-driven lateral-order swap on safe turns (gap>6).
"""
import hashlib
from collections import deque
from enum import IntEnum

# ============================================================================
# W10 - Philosophy encoded as constants
# ============================================================================
# Derivation principle #1 (Survival floor): any action that puts the factory
#   on track to die before step 500 is vetoed. Implemented as gap <= 2
#   emergency escape and as the "save jump for north" gate when gap <= 8.
# Derivation principle #2 (Early compound): mining_node next to factory in
#   the first ~30 steps beats scout/worker. Implemented as score_mine_econ.
# Derivation principle #3 (Save option): jump_cd is an option; we don't burn
#   it for lateral progress when gap <= 8. Implemented as north_only_jump
#   in bfs_jump and as the gap <= 8 branch in score_factory_move.
# Derivation principle #4 (Final-kick): when step >= 400, the only valid
#   primary goal is north. Implemented by Phase.FINAL_KICK shrinking move
#   candidates inside score_factory_move's fallback chain.

# ----- thresholds (lifted from v37 / W2 / W6) -----
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
FINAL_KICK_STEP = 400       # step >= 400: enter FINAL_KICK phase

# ----- priority bands (encode v37's elif ordering as additive scores) -----
# Higher = picked first. Each band is well-separated so a band always
# dominates the next one; scorers within a band are intentionally exclusive.
PRI_EMERGENCY_N = 10_000_000
PRI_EMERGENCY_EW = 9_500_000
PRI_MINE_BUILD = 9_000_000
PRI_TRANSFER_NORTH = 8_500_000
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
# Phase axis (per docs/phase_axis_design.md Q4, simplified)
# ============================================================================
class Phase(IntEnum):
    MINE_SPRINT = 1   # step < 30
    CONVEYOR = 2      # mid game, gap > 8
    PRESSURE = 3      # mid-late, gap <= 8 or step >= 200
    FINAL_KICK = 4    # step >= 400 or gap <= 4


def current_phase(step: int, factory_gap: int) -> Phase:
    """Map (step, factory_gap) to a coarse phase label.

    Note: v37 doesn't read the phase label anywhere; in v50 it is a context
    feature available to every scorer. Behaviorally the v50 scorers do NOT
    branch on phase (otherwise parity with v37 would break). Phase exists as
    a hook for future patches that want a clean "what regime am I in" probe.
    """
    if step >= FINAL_KICK_STEP or factory_gap <= EMERGENCY_GAP + 2:
        return Phase.FINAL_KICK
    if step >= 200 or factory_gap <= LOW_GAP_NORTH_ONLY:
        return Phase.PRESSURE
    if step >= 30:
        return Phase.CONVEYOR
    return Phase.MINE_SPRINT


# ============================================================================
# Constants copied verbatim from v37
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
    # D03: hash perturbation for anti-IL (D06 style, ~30% of safe turns)
    # ------------------------------------------------------------------
    if factory_gap > 6:
        _h = hashlib.sha256(
            HASH_SALT
            + bytes([turn % 256, factory_col % 256, factory_row % 256, player & 0xFF])
        ).digest()[0]
        if _h < PERTURB_THRESHOLD:
            lateral_order = lateral_order[::-1]
            bfs_dirs = ("NORTH",) + lateral_order + ("SOUTH",)

    # ------------------------------------------------------------------
    # Threat tables (verbatim from v37)
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

    def safe_factory_action(act):
        dest = action_dest(factory_col, factory_row, act)
        if enemy_factory_threats and dest in enemy_factory_threats:
            return False
        if act.startswith("JUMP_") and dest in enemy_factory_jump_threats:
            return False
        return True

    # ==================================================================
    # FACTORY SCORERS (the actual refactor)
    # ==================================================================
    # Each scorer reads `ctx` and returns a single (action, score) tuple.
    # The winner is argmax over all proposals. The priority bands below
    # match v37's elif precedence so behavior stays 1:1.
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
        "phase": current_phase(turn, factory_gap),
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
        # helpers
        "can_move": can_move,
        "can_jump": can_jump,
        "get_wall": get_wall,
        "safe_factory_action": safe_factory_action,
        "bfs_jump": bfs_jump,
        "bfs_first_step": bfs_first_step,
    }

    def score_emergency_escape(ctx):
        """W10 #1 Survival floor: gap <= 2 -> JUMP_NORTH first, then JUMP_E/W.

        Mirrors v37's first emergency block. The elif inside v37 is encoded as
        a priority gap (PRI_EMERGENCY_N > PRI_EMERGENCY_EW), so JUMP_NORTH
        always wins when feasible; JUMP_E/W only wins when JUMP_NORTH is not
        feasible (cooldown / wall / unsafe / position blocked).
        """
        gap = ctx["factory_gap"]
        if not (gap <= EMERGENCY_GAP and ctx["south"] > 0):
            return NO_PROPOSAL
        if ctx["f_jump_cd"] > 0:
            return NO_PROPOSAL
        col, row = ctx["factory_col"], ctx["factory_row"]
        uid = ctx["factory_uid"]
        my_pos = ctx["my_positions"]

        # JUMP_NORTH branch. Mirrors v37 exactly: the outer `if can_jump AND
        # safe` short-circuits the elif chain even when the inner position
        # check fails, so we abstain entirely (no JUMP_E/W fallback) when
        # the north outer condition holds.
        if ctx["can_jump"](col, row, "NORTH") and ctx["safe_factory_action"]("JUMP_NORTH"):
            nc, nr = col, row + 2
            if (nc, nr) not in my_pos or my_pos.get((nc, nr)) == uid:
                return ("JUMP_NORTH", PRI_EMERGENCY_N)
            return NO_PROPOSAL

        # JUMP_EAST / JUMP_WEST fallback (v37 elif - only entered when the
        # north outer if was False, i.e. NOT can_jump_NORTH OR NOT safe).
        for d in ("EAST", "WEST"):
            act = f"JUMP_{d}"
            if ctx["can_jump"](col, row, d) and ctx["safe_factory_action"](act):
                dc, dr = OFFSETS[d]
                nc, nr = col + 2 * dc, row + 2 * dr
                if (nc, nr) not in my_pos or my_pos.get((nc, nr)) == uid:
                    return (act, PRI_EMERGENCY_EW)
        return NO_PROPOSAL

    def score_mine_econ_build(ctx):
        """W10 #2 Early compound: build a north-adjacent miner when energy /
        gap / build_cd all permit. Direct port of v37's mine_build_action.
        """
        if not (
            ctx["f_build_cd"] <= 1
            and ctx["factory_energy"] >= MINE_ENERGY_FLOOR
            and ctx["factory_gap"] > MINE_GAP_GATE
            and ctx["counts"][MINER] < 1
        ):
            return NO_PROPOSAL
        col, row = ctx["factory_col"], ctx["factory_row"]
        d = "NORTH"
        dc, dr = OFFSETS[d]
        mpos = (col + dc, row + dr)
        if mpos not in ctx["mining_nodes"] or mpos in ctx["my_positions"]:
            return NO_PROPOSAL
        if not ctx["can_move"](col, row, d):
            return NO_PROPOSAL
        return (f"BUILD_MINER_{d}", PRI_MINE_BUILD)

    def score_transfer_north_r1(ctx):
        """R1 (W-Tree L02/L08): TRANSFER_NORTH to a fresh adj-north support unit.
        Fires only when no miner exists, factory is move-ready, and the north
        neighbour holds a friendly non-factory with energy in [280, 600].
        Priority: above scout build, below miner build.
        """
        if not (
            ctx["f_move_cd"] <= 1
            and ctx["counts"][MINER] == 0
            and ctx["factory_row"] + 1 <= ctx["north"]
            and not (ctx["get_wall"](ctx["factory_col"], ctx["factory_row"]) & WALL_BITS["NORTH"])
        ):
            return NO_PROPOSAL
        target_uid = ctx["my_positions"].get((ctx["factory_col"], ctx["factory_row"] + 1))
        if target_uid is not None and target_uid != ctx["factory_uid"]:
            target_energy = ctx["obs"].robots[target_uid][3] if target_uid in ctx["obs"].robots else 0
            if 280 <= target_energy <= 600:
                return ("TRANSFER_NORTH", PRI_TRANSFER_NORTH)
        return NO_PROPOSAL

    def score_scout_build(ctx):
        """Scout build (v37 gating, kept identical for parity).

        Note: even though docs/unifying_philosophy.md ranks scout below mine
        on the compounding axis (#2), v37 already encodes the right order via
        elif (mine first, then scout); we just translate that to bands.
        """
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
        """v37: if f_move_cd > 1 and no build/emergency fits, IDLE."""
        if ctx["f_move_cd"] > 1:
            return ("IDLE", PRI_IDLE_CD)
        return NO_PROPOSAL

    def score_idle_on_mine(ctx):
        """W10 #2: sitting on own mine while gap > 10 = passive compounding.
        Direct port of v37's "if (col,row) in own_mines and gap > 10: IDLE".
        """
        pos = (ctx["factory_col"], ctx["factory_row"])
        if pos in ctx["own_mines"] and ctx["factory_gap"] > IDLE_ON_MINE_GAP:
            return ("IDLE", PRI_IDLE_ON_MINE)
        return NO_PROPOSAL

    def score_walk_to_own_mine(ctx):
        """v37: walk NORTH one step if north-neighbour is own mine + safe.
        Triggered only when above IDLE_ON_MINE branch did NOT lock IDLE,
        which is implicit because PRI_WALK_OWN_MINE < PRI_IDLE_ON_MINE.
        """
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
        """W10 #3 Save option + #4 Final-kick: jump-preferred BFS toward
        row+20, with the v37 fallback ladder collapsed into a single scorer.

        Each fallback level emits a lower-priority proposal; the highest
        non-NO_PROPOSAL one wins. This is exactly equivalent to v37's
        sequential "if step then break" pattern, with the band gap making
        the elif order explicit and auditable.
        """
        col, row = ctx["factory_col"], ctx["factory_row"]
        gap = ctx["factory_gap"]
        north_bd = ctx["north"]
        width_ = ctx["width"]

        # Main path: jump-preferred BFS to row+20.
        target_row = min(north_bd, row + 20)
        factory_goals = [(tc, target_row) for tc in range(width_)]
        step = ctx["bfs_jump"](
            (col, row), factory_goals, ctx["f_jump_cd"],
            depth=20, north_only_jump=(gap <= LOW_GAP_NORTH_ONLY),
        )
        if step and not ctx["safe_factory_action"](step):
            step = None
        if step and step != "IDLE":
            return (step, PRI_MOVE_MAIN)

        # Fallback 1: closer target with plain BFS.
        closer_goals = [(tc, min(north_bd, row + 5)) for tc in range(width_)]
        step = ctx["bfs_first_step"]((col, row), closer_goals, depth=10, avoid_occupied=False)
        if step and not ctx["safe_factory_action"](step):
            step = None
        if step and step != "IDLE":
            return (step, PRI_MOVE_CLOSER)

        # Fallback 2: any northward walk.
        for d in ("NORTH", "EAST", "WEST"):
            if ctx["can_move"](col, row, d) and ctx["safe_factory_action"](d):
                return (d, PRI_MOVE_ANY_NORTH)

        # Fallback 3: walk SOUTH to escape dead-end (only if gap <= 3).
        if gap <= 3 and ctx["can_move"](col, row, "SOUTH") and ctx["safe_factory_action"]("SOUTH"):
            return ("SOUTH", PRI_MOVE_SOUTH)

        # Fallback 4: desperation jump any direction (only if gap <= 3).
        if gap <= 3 and ctx["f_jump_cd"] <= 0:
            for d in ("EAST", "WEST", "SOUTH"):
                act = f"JUMP_{d}"
                if ctx["can_jump"](col, row, d) and ctx["safe_factory_action"](act):
                    return (act, PRI_MOVE_DESPERATION)

        return NO_PROPOSAL

    def score_build_worker(ctx):
        """v37 last-resort: BUILD_WORKER only when path-finding is hopeless
        AND we're close to dying. This scorer must lose to any successful
        factory_move proposal; the band gap (PRI_MOVE_* > PRI_BUILD_WORKER)
        ensures that without an explicit "if bfs_next_step is None" check.
        """
        if not (
            ctx["spawn_ok"]
            and ctx["counts"][WORKER] < 1
            and ctx["factory_energy"] >= WORKER_ENERGY_FLOOR
            and ctx["factory_gap"] <= WORKER_GAP_GATE
        ):
            return NO_PROPOSAL
        return ("BUILD_WORKER", PRI_BUILD_WORKER)

    def score_fallback_idle(ctx):
        """Bottom-of-stack IDLE, always proposes so argmax never empty."""
        return ("IDLE", PRI_IDLE_FINAL)

    SCORERS = [
        score_emergency_escape,
        score_mine_econ_build,
        score_transfer_north_r1,
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
    # SCOUT / MINER / WORKER planning (verbatim from v37, NOT refactored).
    # The brief says these elif chains are short and stable; the PoC's
    # contract is to refactor only the factory decision.
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
