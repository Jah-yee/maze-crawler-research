
"""
v62_2ply_tuned: v62 with adjusted cost weights (W_NORTH=20, W_COLLISION=50, 2PLY=10).

Original v62 (z=-2.60 at 40g vs v37) had:
- W_NORTH=5 too weak (factory didn't push north aggressively enough)
- W_COLLISION=100 too collision-averse (wasted turns avoiding enemies)
- 2PLY_DEPTH=8 too shallow (didn't see far enough ahead)

Tuned:
- W_NORTH=20 (4x more aggressive northward)
- W_COLLISION=50 (halved, accept some collision risk)
- BFS_2PLY_DEPTH=10 (deeper lookahead)
"""
import os
from collections import deque

FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}
SCOUT_DELAY_STEP = 24

FACTORY_MOVE_PERIOD = 2
FACTORY_JUMP_COOLDOWN = 20
SCROLL_START_INTERVAL = 10
SCROLL_END_INTERVAL = 2
SCROLL_RAMP_STEPS = 450


def get_scroll_interval(step):
    if step >= SCROLL_RAMP_STEPS:
        return SCROLL_END_INTERVAL
    progress = step / SCROLL_RAMP_STEPS
    interval = SCROLL_START_INTERVAL - (SCROLL_START_INTERVAL - SCROLL_END_INTERVAL) * progress
    return max(SCROLL_END_INTERVAL, round(interval))


def p_need_jump(gap):
    if gap < 4:
        return 1.0
    if gap < 8:
        return 0.5
    if gap < 12:
        return 0.2
    return 0.1


W_DEATH = float(os.environ.get("V62_W_DEATH", "10000"))
W_NORTH = float(os.environ.get("V62_W_NORTH", "20.0"))
W_COLLISION = float(os.environ.get("V62_W_COLLISION", "50"))
W_CD_LOCK = float(os.environ.get("V62_W_CD_LOCK", "0.05"))
W_ENERGY = float(os.environ.get("V62_W_ENERGY", "0.05"))
W_MINE = float(os.environ.get("V62_W_MINE", "5.0"))
NORTH_BFS_TARGET_OFFSET = int(os.environ.get("V62_NORTH_TARGET", "5"))
NORTH_BFS_MAX_DEPTH = int(os.environ.get("V62_NORTH_DEPTH", "12"))
BFS_2PLY_DEPTH = int(os.environ.get("V62_2PLY_DEPTH", "10"))
DEATH_GAP_THRESHOLD = int(os.environ.get("V62_DEATH_THR", "1"))
UNREACHABLE_DIST = 50
GOAL_OFFSET = NORTH_BFS_TARGET_OFFSET + 15

CANDIDATE_ORDER = (
    "NORTH", "JUMP_NORTH",
    "EAST", "WEST",
    "JUMP_EAST", "JUMP_WEST",
    "IDLE",
    "SOUTH", "JUMP_SOUTH",
)

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

    last_south = _memory.get("last_south", south)
    est_counter = _memory.get("est_counter", SCROLL_START_INTERVAL)
    if turn == 0:
        est_counter = SCROLL_START_INTERVAL
    else:
        if south > last_south:
            est_counter = get_scroll_interval(turn - 1)
        else:
            est_counter = max(1, est_counter - 1)
    _memory["last_south"] = south
    _memory["est_counter"] = est_counter
    pred_south_next = south + 1 if est_counter <= 1 else south

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

    def bfs_jump(start, goals, jump_cd, depth=20, north_only_jump=False):
        if not goals:
            return None
        goal_set = set(goals)
        q = deque([(start, None, 0, min(jump_cd, 20))])
        seen = {(start[0], start[1], jump_cd <= 0)}
        jump_dirs = ("NORTH",) if north_only_jump else DIRS
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

    # ========== NORTH DIST (v56 multi-source BFS) ==========
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

    # ========== 2-PLY INFRASTRUCTURE ==========
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

    def simulate_action(c, r, mcd, jcd, act):
        if act == "IDLE":
            return (c, r), max(0, mcd - 1), max(0, jcd - 1)
        if act in OFFSETS:
            dc, dr = OFFSETS[act]
            return (c + dc, r + dr), FACTORY_MOVE_PERIOD, max(0, jcd - 1)
        if act.startswith("JUMP_"):
            d = act.split("_")[1]
            dc, dr = OFFSETS[d]
            return (c + 2 * dc, r + 2 * dr), FACTORY_MOVE_PERIOD, FACTORY_JUMP_COOLDOWN
        return (c, r), mcd, jcd

    def step_cost(from_pos, to_pos, act_type):
        gap = to_pos[1] - pred_south_next
        c1 = 1.0 if gap <= DEATH_GAP_THRESHOLD else 0.0
        dist_before = dist_at(from_pos[0], from_pos[1])
        dist_after = dist_at(to_pos[0], to_pos[1])
        c2 = -float(dist_before - dist_after)
        c3 = 1.0 if to_pos in enemy_factory_threats else 0.0
        if act_type == "JUMP" and to_pos in enemy_factory_jump_threats:
            c3 = 1.0
        cd_lock = FACTORY_JUMP_COOLDOWN if act_type == "JUMP" else (FACTORY_MOVE_PERIOD if act_type in OFFSETS else 0)
        c4 = cd_lock * p_need_jump(gap)
        c5 = -50.0 if to_pos in own_mines else 0.0
        c6 = 1.0 if to_pos in own_mines else 0.0
        return W_DEATH * c1 + W_NORTH * c2 + W_COLLISION * c3 + W_CD_LOCK * c4 + W_ENERGY * c5 - W_MINE * c6

    def bfs_jump_aggregate_cost(start_pos, start_jcd, depth=BFS_2PLY_DEPTH, north_only_jump=False):
        goals = [(tc, min(north, factory_row + GOAL_OFFSET)) for tc in range(width)]
        goal_set = set(goals)
        if start_pos in goal_set:
            return "IDLE", 0.0
        q = deque()
        q.append(((start_pos[0], start_pos[1]), None, 0, min(start_jcd, 20), 0.0))
        seen = {(start_pos[0], start_pos[1], start_jcd <= 0)}
        jump_dirs = ("NORTH",) if north_only_jump else DIRS
        while q:
            (c, r), first_d, dist, cur_jcd, agg = q.popleft()
            if (c, r) in goal_set and dist > 0:
                return first_d, agg
            if dist >= depth:
                continue
            if cur_jcd <= 0:
                for d in jump_dirs:
                    if not can_jump(c, r, d):
                        continue
                    dc, dr = OFFSETS[d]
                    nc, nr = c + 2 * dc, r + 2 * dr
                    key = (nc, nr, False)
                    if key in seen:
                        continue
                    seen.add(key)
                    sc = step_cost((c, r), (nc, nr), "JUMP")
                    q.append(((nc, nr), first_d or f"JUMP_{d}", dist + 1, 20, agg + sc))
            for d in DIRS:
                if not can_move(c, r, d):
                    continue
                nc, nr = c + OFFSETS[d][0], r + OFFSETS[d][1]
                njcd = max(0, cur_jcd - 1)
                key = (nc, nr, njcd <= 0)
                if key in seen:
                    continue
                seen.add(key)
                sc = step_cost((c, r), (nc, nr), d)
                q.append(((nc, nr), first_d or d, dist + 1, njcd, agg + sc))
        return None, float('inf')

    def two_ply_best_action():
        candidates = enumerate_legal_factory_actions()
        if not candidates:
            return None
        best_act = None
        best_total = float('inf')
        for act in candidates:
            new_pos, new_mcd, new_jcd = simulate_action(
                factory_col, factory_row, f_move_cd, f_jump_cd, act
            )
            new_c, new_r = new_pos
            new_gap = new_r - pred_south_next
            c1 = 1.0 if new_gap <= DEATH_GAP_THRESHOLD else 0.0
            c2 = -float(dist_at_factory - dist_at(new_c, new_r))
            c3 = 0.0
            if (new_c, new_r) in enemy_factory_threats:
                c3 = 1.0
            if act.startswith("JUMP_") and (new_c, new_r) in enemy_factory_jump_threats:
                c3 = 1.0
            cd_lock = FACTORY_JUMP_COOLDOWN if act.startswith("JUMP_") else (FACTORY_MOVE_PERIOD if act in OFFSETS else 0)
            c4 = cd_lock * p_need_jump(new_gap)
            c5 = -50.0 if (new_c, new_r) in own_mines else 0.0
            c6 = 1.0 if (new_c, new_r) in own_mines else 0.0
            root_cost = W_DEATH * c1 + W_NORTH * c2 + W_COLLISION * c3 + W_CD_LOCK * c4 + W_ENERGY * c5 - W_MINE * c6
            north_only = (new_r - south) <= 8
            _, future_cost = bfs_jump_aggregate_cost(new_pos, new_jcd, BFS_2PLY_DEPTH, north_only_jump=north_only)
            total = root_cost + future_cost
            if total < best_total:
                best_total = total
                best_act = act
        return best_act

    # ========== FACTORY DECISION ==========
    if factory_uid not in actions:
        if factory_gap <= 2 and south > 0:
            if f_jump_cd <= 0 and can_jump(factory_col, factory_row, "NORTH") and safe_factory_action("JUMP_NORTH"):
                nc, nr = factory_col, factory_row + 2
                if (nc, nr) not in my_positions or my_positions.get((nc, nr)) == factory_uid:
                    record(factory_uid, "JUMP_NORTH", factory_col, factory_row)
            elif f_jump_cd <= 0:
                for d in ("EAST", "WEST"):
                    act = f"JUMP_{d}"
                    if can_jump(factory_col, factory_row, d) and safe_factory_action(act):
                        dc, dr = OFFSETS[d]
                        nc, nr = factory_col + 2 * dc, factory_row + 2 * dr
                        if (nc, nr) not in my_positions or my_positions.get((nc, nr)) == factory_uid:
                            record(factory_uid, act, factory_col, factory_row)
                            break

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
        elif f_move_cd > 1:
            record(factory_uid, "IDLE", factory_col, factory_row)
        else:
            if (factory_col, factory_row) in own_mines and factory_gap > 10:
                record(factory_uid, "IDLE", factory_col, factory_row)
            if factory_uid in actions:
                pass
            else:
                best = two_ply_best_action()
                if best is not None:
                    record(factory_uid, best, factory_col, factory_row)
                else:
                    for d in ("NORTH",):
                        dc, dr = OFFSETS[d]
                        mpos = (factory_col + dc, factory_row + dr)
                        if mpos in own_mines and can_move(factory_col, factory_row, d) and safe_factory_action(d):
                            record(factory_uid, d, factory_col, factory_row)
                            break
                    if factory_uid in actions:
                        pass
                    else:
                        target_row_fb = min(north, factory_row + 20)
                        factory_goals = [(tc, target_row_fb) for tc in range(width)]
                        step = bfs_jump(
                            (factory_col, factory_row),
                            factory_goals,
                            f_jump_cd,
                            depth=20,
                            north_only_jump=factory_gap <= 8,
                        )
                        if step and not safe_factory_action(step):
                            step = None
                        if not step:
                            closer_goals = [(tc, min(north, factory_row + 5)) for tc in range(width)]
                            step = bfs_first_step((factory_col, factory_row), closer_goals, depth=10, avoid_occupied=False)
                            if step and not safe_factory_action(step):
                                step = None
                        if not step:
                            for d in ("NORTH", "EAST", "WEST"):
                                if can_move(factory_col, factory_row, d) and safe_factory_action(d):
                                    step = d
                                    break
                        if not step and factory_gap <= 3:
                            if can_move(factory_col, factory_row, "SOUTH") and safe_factory_action("SOUTH"):
                                step = "SOUTH"
                        if not step and f_jump_cd <= 0 and factory_gap <= 3:
                            for d in ("EAST", "WEST", "SOUTH"):
                                act = f"JUMP_{d}"
                                if can_jump(factory_col, factory_row, d) and safe_factory_action(act):
                                    step = act
                                    break
                        if step and step != "IDLE":
                            record(factory_uid, step, factory_col, factory_row)
                        else:
                            if spawn_ok and counts[WORKER] < 1 and factory_energy >= 200 and factory_gap <= 4:
                                record(factory_uid, "BUILD_WORKER", factory_col, factory_row)
                                counts[WORKER] += 1
                            else:
                                record(factory_uid, "IDLE", factory_col, factory_row)

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

    return actions
