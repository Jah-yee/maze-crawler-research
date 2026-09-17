"""
Top 2 Maze Crawler Agent â€” Jump-Preferred BFS (LB 1223)
Key ideas: jump-preferred BFS, mirror vision, optimistic fog, emergency escape
"""
from collections import deque

FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}

# Precompute mirror wall lookup: E<->W swap, N and S unchanged
MIRROR_WALL = [0] * 16
for _v in range(16):
    _m = (_v & 1) | (_v & 4)
    if _v & 2: _m |= 8
    if _v & 8: _m |= 2
    MIRROR_WALL[_v] = _m

_memory = {}


def agent(obs, config):
    """Main entry point â€” wrapped for exception safety."""
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

    # ========== PERSISTENT WALL MEMORY ==========
    # Walls persist across turns. We also infer mirrored walls (E/W symmetry).
    if getattr(obs, "step", 0) == 0:
        _memory = {}
    if "walls" not in _memory:
        _memory["walls"] = {}
    if "scout_built" not in _memory:
        _memory["scout_built"] = False
    walls_mem = _memory["walls"]

    for i, w in enumerate(obs.walls):
        if w == -1:
            continue
        r = south + i // width
        c = i % width
        walls_mem[(c, r)] = w
        # Mirror: col' = (width - 1) - col, swap E<->W bits
        mc = (width - 1) - c
        mw = MIRROR_WALL[w]
        if (mc, r) not in walls_mem:
            walls_mem[(mc, r)] = mw

    # Purge old cells to save memory
    if len(walls_mem) > 2000:
        cutoff = south - 5
        walls_mem = {k: v for k, v in walls_mem.items() if k[1] >= cutoff}
        _memory["walls"] = walls_mem

    # ========== HELPER FUNCTIONS ==========
    def get_wall(c, r):
        """Get wall bits. Unknown cells = 0 (optimistic: assume passable)."""
        return walls_mem.get((c, r), 0)

    def can_move(c, r, d):
        dc, dr = OFFSETS[d]
        nc, nr = c + dc, r + dr
        if not (0 <= nc < width and south <= nr <= north):
            return False
        return not (get_wall(c, r) & WALL_BITS[d])

    def can_jump(c, r, d):
        """Can factory jump in direction d? Lands 2 cells away over wall."""
        dc, dr = OFFSETS[d]
        nc, nr = c + 2 * dc, r + 2 * dr
        if not (0 <= nc < width and south <= nr <= north):
            return False
        return get_wall(nc, nr) != 15  # don't land in fully walled cell

    # ========== ROBOT CLASSIFICATION ==========
    my_robots = {uid: d for uid, d in obs.robots.items() if d[4] == player}
    my_positions = {(d[1], d[2]): uid for uid, d in my_robots.items()}
    reserved = set()
    counts = {rt: sum(1 for d in my_robots.values() if d[0] == rt) for rt in range(4)}

    # Crystal locations (for worker pathing)
    crystals = {}
    for k, v in obs.crystals.items():
        parts = k.split(",")
        crystals[(int(parts[0]), int(parts[1]))] = v

    # ========== BFS: STANDARD (no jumps) ==========
    def bfs_first_step(start, goals, depth=20, avoid_occupied=True):
        """BFS returning first action to reach any goal cell."""
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

    # ========== BFS: JUMP-PREFERRED (factory only) ==========
    def bfs_jump(start, goals, jump_cd, depth=20):
        """
        BFS with jump state tracking.
        KEY INSIGHT: Explores jumps BEFORE walks when cooldown is ready,
        because a jump covers 2 cells in 1 turn (vs walking = 1 cell/turn).
        """
        if not goals:
            return None
        goal_set = set(goals)
        q = deque([(start, None, 0, min(jump_cd, 20))])
        seen = {(start[0], start[1], jump_cd <= 0)}
        while q:
            (c, r), first_d, dist, jcd = q.popleft()
            if (c, r) in goal_set and dist > 0:
                return first_d
            if dist >= depth:
                continue

            # JUMP moves explored first when cooldown ready
            if jcd <= 0:
                for d in DIRS:
                    if not can_jump(c, r, d):
                        continue
                    dc, dr = OFFSETS[d]
                    nc, nr = c + 2 * dc, r + 2 * dr
                    key = (nc, nr, False)
                    if key in seen:
                        continue
                    seen.add(key)
                    q.append(((nc, nr), first_d or f"JUMP_{d}", dist + 1, 20))

            # Normal walking moves
            for d in DIRS:
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

    # ========== ACTION RECORDING ==========
    def record(uid, act, col, row):
        """Record action and reserve destination cell."""
        actions[uid] = act
        if act.startswith("JUMP_"):
            d = act.split("_")[1]
            dc, dr = OFFSETS[d]
            reserved.add((col + 2 * dc, row + 2 * dr))
        elif act in OFFSETS:
            dc, dr = OFFSETS[act]
            reserved.add((col + dc, row + dr))
        elif "BUILD" in act:
            reserved.add((col, row + 1))  # spawn is always north
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
        return actions  # factory dead, GG

    factory_energy = my_robots[factory_uid][3]
    factory_gap = factory_row - south  # rows above death

    fdata = my_robots[factory_uid]
    f_move_cd = fdata[5] if len(fdata) > 5 else 0
    f_jump_cd = fdata[6] if len(fdata) > 6 else 0
    f_build_cd = fdata[7] if len(fdata) > 7 else 0

    # ========== FACTORY PLANNING (MOST IMPORTANT!) ==========
    # Emergency: â‰¤ 2 rows from south bound = imminent death
    if factory_gap <= 2 and south > 0:
        if f_jump_cd <= 0 and can_jump(factory_col, factory_row, "NORTH"):
            nc, nr = factory_col, factory_row + 2
            if (nc, nr) not in my_positions or my_positions.get((nc, nr)) == factory_uid:
                record(factory_uid, "JUMP_NORTH", factory_col, factory_row)
        elif f_jump_cd <= 0:
            for d in ("EAST", "WEST"):
                if can_jump(factory_col, factory_row, d):
                    dc, dr = OFFSETS[d]
                    nc, nr = factory_col + 2 * dc, factory_row + 2 * dr
                    if (nc, nr) not in my_positions or my_positions.get((nc, nr)) == factory_uid:
                        record(factory_uid, f"JUMP_{d}", factory_col, factory_row)
                        break

    if factory_uid not in actions:
        # Build exactly 1 scout for vision (cheap at 50 energy)
        spawn = (factory_col, factory_row + 1)
        spawn_ok = (
            f_build_cd <= 1
            and spawn not in my_positions
            and factory_row + 1 <= north
            and not (get_wall(factory_col, factory_row) & WALL_BITS["NORTH"])
        )
        if spawn_ok and not _memory["scout_built"] and counts[SCOUT] < 1 and factory_energy >= 50:
            record(factory_uid, "BUILD_SCOUT", factory_col, factory_row)
            _memory["scout_built"] = True
            counts[SCOUT] += 1
        elif f_move_cd > 1:
            record(factory_uid, "IDLE", factory_col, factory_row)
        else:
            # Main pathfinding: BFS toward row + 20 using jump-preferred search
            target_row = min(north, factory_row + 20)
            factory_goals = [(tc, target_row) for tc in range(width)]
            step = bfs_jump((factory_col, factory_row), factory_goals, f_jump_cd, depth=20)

            # Fallback 1: closer target with standard BFS
            if not step:
                closer_goals = [(tc, min(north, factory_row + 5)) for tc in range(width)]
                step = bfs_first_step((factory_col, factory_row), closer_goals, depth=10, avoid_occupied=False)

            # Fallback 2: try any northward direction
            if not step:
                for d in ("NORTH", "EAST", "WEST"):
                    if can_move(factory_col, factory_row, d):
                        step = d
                        break

            # Fallback 3: walk SOUTH to escape dead-end (counterintuitive but life-saving)
            if not step and factory_gap <= 3:
                if can_move(factory_col, factory_row, "SOUTH"):
                    step = "SOUTH"

            # Fallback 4: desperation jump any direction
            if not step and f_jump_cd <= 0 and factory_gap <= 3:
                for d in ("EAST", "WEST", "SOUTH"):
                    if can_jump(factory_col, factory_row, d):
                        step = f"JUMP_{d}"
                        break

            if step and step != "IDLE":
                record(factory_uid, step, factory_col, factory_row)
            else:
                # Absolute last resort: build worker to break wall ahead
                if spawn_ok and counts[WORKER] < 1 and factory_energy >= 200 and factory_gap <= 4:
                    record(factory_uid, "BUILD_WORKER", factory_col, factory_row)
                    counts[WORKER] += 1
                else:
                    record(factory_uid, "IDLE", factory_col, factory_row)

    # ========== SCOUT PLANNING ==========
    scouts = [(uid, d) for uid, d in my_robots.items() if d[0] == SCOUT]
    for uid, data in scouts:
        col, row = data[1], data[2]
        move_cd = data[5] if len(data) > 5 else 0
        if move_cd > 1:
            record(uid, "IDLE", col, row)
            continue
        # Scout runs ahead of factory for vision
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

    # ========== WORKER PLANNING (only spawned as last resort) ==========
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
