#!/usr/bin/env python3
"""Append a 'Tactical archive' qualitative section to each team's profile.md.

Run after scripts/top_competitors_summary.py. Re-running is safe: the script
replaces any existing '## Tactical archive' block in each profile.md.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_DIR = ROOT / "reports" / "top_competitors"

ARCHIVES: dict[str, str] = {
    "02_andrey_saveliev": """## Tactical archive

**Core playbook (1-3 lines).** A near-clone of the bunterrrrr school: zero routine scouts, first directional miner around step 27 (some as early as step 7), and the factory grinds northward harvesting its own miners' output. Distinguishing feature is a stronger willingness to put roughly **43% of all miner builds onto EAST/WEST mining nodes** (vs bunterrrrr's ~39%), making the economy slightly less north-tempo dependent.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: more side miners, slightly fewer total miners (3.3 vs 3.8), and slightly more SOUTH/JUMP_SOUTH defensive actions (6.4 per game).
- vs our v37: we still spawn scouts every ~5-10 steps and only ever mine north (with v15/v17/v19 experiments); they spawn zero scouts and mine three directions from step ~27 onward.

**Unique tricks.** Heaviest JUMP_NORTH user in the directional school (`JUMP_NORTH` is in the per-replay action top-5). Combined with the early miner that gives the factory a `TRANSFER_NORTH` energy refill, they can pop +2 rows in a single turn cheaper than most opponents.

**Largest weakness (from losses).** 11/14 losses are `timeout_tiebreak`. They reach step 500 but lose tiebreak; head-to-head losses are clustered against other top-tier directional teams (`Nicolas Klodt`, `Hazy Maze Crawler`, `Takahiro Matsumoto`). They lose 3 games to `factory_collision`, mainly when their JUMP_NORTH crosses an enemy factory's threat radius.

**Most likely outcome vs our v37.** They win on energy/tiebreak ~70-80% of games. Our only realistic edge is forcing a factory collision when their pre-emptive JUMP_NORTH lands next to our factory — but their step-50 row average (~13) is faster than ours, so we rarely catch them in collision range.
""",

    "03_takahiro_matsumoto": """## Tactical archive

**Core playbook (1-3 lines).** Legacy-NORTH miner spelling: every miner build observed in the focus set is plain `BUILD_MINER`, which the environment interprets as a NORTH spawn. Combined with **heavy SOUTH usage (89.2 SOUTH/JUMP_SOUTH per replay — the most extreme in the top-15)**, they run a cyclical pattern of "race north, dump factory south to refresh cooldowns, race north again".

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: uses the legacy NORTH spelling rather than explicit directional actions. Also builds **7.3 scouts per game** while bunterrrrr builds none.
- vs our v37: first miner around step 29 (we are ~step 90+). They also actively choose SOUTH retreats; v37 treats SOUTH as a near-error.

**Unique tricks.** The repeated SOUTH-then-NORTH cycle resets factory move/jump cooldowns near the boundary, then bursts north when an opponent is out of position. Highest factory jump count of any team (40.8 per replay). Final factory energy averages 6137 — comparable to bunterrrrr despite the very different mechanic.

**Largest weakness (from losses).** 5 `factory_collision` + 4 `boundary_scroll` + 5 `timeout_tiebreak` — the aggressive SOUTH posture exposes them to scroll death when they linger one step too long, and to collisions when the enemy factory anticipates the NORTH burst.

**Most likely outcome vs our v37.** Their economy snowballs faster than ours, but they take more risks. If our v37 can hold a single row of buffer and let them push too far south, we might catch a `boundary_scroll` win. Realistically we lose 60-70% of games due to their TRANSFER-fueled tiebreak energy.
""",

    "04_hazy_maze_crawler": """## Tactical archive

**Core playbook (1-3 lines).** The most "complete" directional miner school in the top-15: uses **all four directions** (34N/23E/26W/17S) and is the only studied team that systematically builds **SOUTH miners** (17% of builds). Low scouts (1.5/game), early first miner (step 33), highest mean peak factory energy (7099) of any team studied.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: adds defensive SOUTH miners — bunterrrrr almost never builds SOUTH.
- vs our v37: every miner-economy lever we don't use, they pull.

**Unique tricks.** SOUTH miners are placed on the south-side mining nodes — they generate energy and the factory can step onto them when forced south, turning a defensive scroll-avoidance into an energy gain. This is rare and likely high-EV.

**Largest weakness (from losses).** 11/14 losses are `timeout_tiebreak`. Their economy is strong but they don't always convert it into row dominance; against other directional teams the game decays into a tiebreak race.

**Most likely outcome vs our v37.** They win on energy. SOUTH miners would also dampen any scroll-pressure tactic v37 could attempt. ~75% loss likely.
""",

    "05_pavelliashkov": """## Tactical archive

**Core playbook (1-3 lines).** Heaviest miner builder in the top-15 (5.8 per replay) with the highest mean simultaneous mine count (2.6). Balanced 4-direction miner mix (38N/23E/19W/21S) with hybrid scout use (2.7/game). First miner slightly later (median 40), but the volume compensates.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: builds many more miners and holds more mines at once. Slightly later first miner.
- vs our v37: economy is on a completely different scale — by step 200 they average 4100 factory energy, our v37 averages a few hundred.

**Unique tricks.** Multi-mine compounding — at peak they hold 2-3 owned mines simultaneously, each providing +50/turn to the factory plus stored energy. This is the closest thing to a "mine farm" in the top-15.

**Largest weakness (from losses).** Balanced cause mix: 6 timeout + 5 collision + 3 scroll. No single Achilles heel.

**Most likely outcome vs our v37.** Strong loss probability. The only meaningful counter is a step-30 to step-80 collision attempt before their second mine comes online.
""",

    "06_nicolas_klodt": """## Tactical archive

**Core playbook (1-3 lines).** Late-and-disciplined directional miner — median first miner is **step 65**, latest of the top tier. Compensates with hybrid scouts (5.3/game), the highest defensive SOUTH usage in the directional school (71.4/game), and the highest mean peak factory energy (7382) of the entire study.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: much later first miner, more scouts, much more SOUTH activity.
- vs our v37: closest to "what we could plausibly evolve into" — scout-aware late mine economy, careful row management.

**Unique tricks.** 71.4 SOUTH/JUMP_SOUTH per replay — they intentionally race south to bait enemy factories into over-commit, then JUMP_NORTH back. Their late-but-efficient first miner means they don't sacrifice opening tempo for economy.

**Largest weakness (from losses).** 10/13 losses are `timeout_tiebreak`. Zero draws across 25 replays — every game has a decisive outcome.

**Most likely outcome vs our v37.** Probably their tempo wins via slightly better north pacing then a midgame miner. Window for our v37: step 0-65 where they don't yet have a miner. If we can establish a 2-row north lead and lock the corridor, scroll could rescue us before their economy catches up.
""",

    "07_daniel_bekker": """## Tactical archive

**Core playbook (1-3 lines).** NORTH-heavy directional miner (59% NORTH, 0% SOUTH), low scouts (2.3), low miners (2.2). Distinguishing feature is **the highest worker count in the top-15 (3.16 per replay)** — they invest in workers for support/wall removal where others don't.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: similar no-south miner stance but a meaningful worker pipeline.
- vs our v37: worker builds plus an early(ish) first miner (step 52) plus zero SOUTH miners — a more conservative version of the bunterrrrr school.

**Unique tricks.** Worker fleet — late game they have ~3 workers active, which can REMOVE walls or transfer energy back. Highest mean reward (1304) outside of harmo-miu.

**Largest weakness (from losses).** **4 `boundary_scroll` losses** — the most among ranks 2-10. They push north hard and get caught when south boundary scrolls.

**Most likely outcome vs our v37.** They have a real economy but also a real scroll vulnerability. If our v37 plays patient and lets them over-commit, we can survive while they die to scroll. They are the most-beatable strong team if v37 played slightly more defensively.
""",

    "08_ai_took_my_job": """## Tactical archive

**Core playbook (1-3 lines).** Legacy-NORTH miner spelling with **earliest median first miner (step 23, minimum step 3)** of the entire study. Hybrid scout (4.1) + miner (4.3) builds, heavy SOUTH (25.3 per game), 33.6 factory jumps. By far the most public episodes (1218) — they iterate fast.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: legacy plain NORTH action and very early commitment to mine economy (step 3-23 first miner).
- vs our v37: opposite of v37 in every economy dimension.

**Unique tricks.** Step-3 first miner is the earliest observed in any focus replay across all teams. It still spawns north of the factory; the distinguishing feature is timing, not a separate spawn mechanic.

**Largest weakness (from losses).** 14/20 losses are `timeout_tiebreak` and the **median reward is only -1** (vs Takahiro Matsumoto's similar mechanic that produces median -1 with mean 551). They grind a lot of 1/-1 wins via the tiebreak, but max reward is only 4048 — their snowball ceiling is lower than the directional school.

**Most likely outcome vs our v37.** They almost always reach step 500. Tiebreak goes to whoever has more final energy + higher row; our v37 has neither. ~75-80% loss expected.
""",

    "09_zero_hqr": """## Tactical archive

**Core playbook (1-3 lines).** Legacy-NORTH miner spelling + **low scout count (1.0)** + low SOUTH usage (12/game). Median first miner 46, 4.1 miners per game.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: legacy plain NORTH action, slightly later first miner.
- vs our v37: ~no scouts and many early NORTH miners — we have the opposite.

**Unique tricks.** Plain-action NORTH miners with minimal SOUTH activity; the edge is disciplined timing rather than special spawn geometry.

**Largest weakness (from losses).** 5 `factory_collision` (high) + 8 timeout_tiebreak. Mean final factory energy 2984 — middle of the pack, so tiebreak is not their strongest mode.

**Most likely outcome vs our v37.** They likely win via earlier NORTH mining, but their factory-collision rate (5/14 losses) is higher than most top tier teams. If our v37 plays straight north and forces head-on factory collisions, we have an unusual amount of upside here.
""",

    "10_josephmontana": """## Tactical archive

**Core playbook (1-3 lines).** Full 4-direction directional miner with **the most balanced miner distribution** (40N/21E/21W/18S) — they truly use the entire compass. Low scouts (1.0), 5.4 miners per game, first miner at step 32.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: more side+south mining, similar total miner count, similar low-scout discipline.
- vs our v37: same gap as the other heavy miners.

**Unique tricks.** True 4-direction miner placement — they place miners on whichever adjacent mining node is visible, regardless of direction. Highest peak factory energy outside of Nicolas Klodt (6543 mean).

**Largest weakness (from losses).** **7/15 losses are `boundary_scroll`** — by far the most scroll-loss-heavy team in the top-15. Their broad-direction mining slows their north tempo, so they sometimes get pushed off the bottom.

**Most likely outcome vs our v37.** They have a real economy and a real scroll vulnerability. Aggressive north play from our v37 could pressure them into a scroll-loss; otherwise they out-economy us.
""",

    "11_harmo_miu": """## Tactical archive

**Core playbook (1-3 lines).** Directional NORTH + side miner (48N/29E/24W/0S), late first miner (median 62), low miner count (1.7) but **the highest mean reward of any directional team (1258)** — they are unusually efficient with the miners they do build. Hybrid scouts (3.0/game).

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: very similar miner mechanic and distribution (both avoid SOUTH miners) but later commitment.
- vs our v37: still earlier and more efficient than ours.

**Unique tricks.** High reward-per-miner — they get more energy per miner than any other team. Likely strong miner timing and placement. Median reward 0 but max reward 7592 — they have jackpot games.

**Largest weakness (from losses).** Balanced 5+5+5 (collision/timeout/scroll). No single dominant failure — they don't have an obvious counter, which makes them slippery.

**Most likely outcome vs our v37.** Likely loss; their reward-per-miner means even a single midgame miner snowballs.
""",

    "12_curvecowboy": """## Tactical archive

**Core playbook (1-3 lines).** **Hybrid legacy-NORTH + explicit side miner spelling** — plain `BUILD_MINER` contributes NORTH builds, alongside explicit EAST/SOUTH/WEST actions. Heavy scouts (5.3), late first miner (52).

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: hybrid build mechanic and no NORTH directional miners.
- vs our v37: still mines earlier and more than v37.

**Unique tricks.** Mixed action spelling and broad direction coverage. **Lowest peak factory energy of mid-tier (3671 mean)** — they don't snowball, they grind.

**Largest weakness (from losses).** **7/15 losses are `factory_collision` — the most of any team in the study.** They take aggressive collision risks that backfire.

**Most likely outcome vs our v37.** Their collision-prone style is exactly the matchup where our v37's path-careful factory could win. If we avoid head-on factory geometry, they may collision-die without our doing anything special.
""",

    "13_pavlo_ivanin": """## Tactical archive

**Core playbook (1-3 lines).** Light legacy-NORTH miner use (0.9/game, max only 23 events across 25 replays), **heavy scouts (5.8)**, very low reward magnitudes (**mean reward 15, max 315 — by far the lowest in the study**). They reach rank 13 mainly by winning 1/-1 tiebreaks, not by snowballing.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: opposite of bunterrrrr — barely uses the mine economy.
- vs our v37: their median first miner (step 30) is earlier than ours, but they only build ~1 miner per game.

**Unique tricks.** Survival-first play with **60.9 SOUTH/JUMP_SOUTH per replay** — they actively race south as a survival tactic, then nudge north when it's safe. Their factory energy at step 400 is below 1000 on average; they don't try to win on energy, only on row position.

**Largest weakness (from losses).** **8 `factory_collision` + 6 `boundary_scroll` + 1 single_factory_death** — they die a lot. With essentially no energy reserve, any mistake is fatal.

**Most likely outcome vs our v37.** **This is the most beatable top-15 opponent.** They have no jackpot mode and die frequently to scroll/collision. A clean v37 game (north-push + collision-avoidance) likely wins. Closing the gap to this team is the single most actionable lift.
""",

    "14_henry_solberg": """## Tactical archive

**Core playbook (1-3 lines).** Side-and-south miner (E55%/W18%/S27%, **zero NORTH miners**) — they reserve the north corridor for the factory itself and only mine where the factory wouldn't walk anyway. Low final energy (1719 mean), heavy SOUTH (20.2/game), heavy EAST/WEST move actions (~1400 each per 25 replays).

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: completely different — they NEVER build NORTH miners. SOUTH miners are a quarter of their builds.
- vs our v37: we mine on the same direction we travel (north only when we try). They mine away from their travel direction.

**Unique tricks.** "Off-axis mining" — the factory marches north on the NORTH lane, mining nodes on EAST/WEST/SOUTH cells provide energy without contesting the factory's path. The factory steps off the lane only briefly to collect.

**Largest weakness (from losses).** 8 timeout_tiebreak + 7 factory_collision + 3 simultaneous_tiebreak. Low energy (1719 mean) means tiebreak position is weak.

**Most likely outcome vs our v37.** Tight games. Their no-north-miner discipline gives them a faster effective north pace than miner-heavy teams, but the low energy means they're vulnerable in a tiebreak.
""",

    "15_nicolas_bridelance": """## Tactical archive

**Core playbook (1-3 lines).** **Pure scout strategy — 0 miners, 7.8 scouts per game, 0 workers, no mine economy at all.** They survive via factory navigation only. Final factory energy averages 318 (lowest in the study), IDLE-heavy action mix.

**Key differences vs bunterrrrr / our v37.**
- vs bunterrrrr: complete opposite school — no mine economy whatsoever.
- vs our v37: **this is the most strategically similar team to our agent**. They rank 15 with this playbook; we rank 24. The gap is execution, not strategy class.

**Unique tricks.** No tricks — just disciplined scout + navigate. Their 777 public episodes (third-highest sample) means the rank is honest, not a low-sample fluke.

**Largest weakness (from losses).** **9 `factory_collision` losses — the most of any team in the study.** With no energy reserve they cannot afford navigation errors; the moment they encounter a mine-economy team and lose row pace, they're done.

**Most likely outcome vs our v37.** Approximately even matchup. The gap to rank 15 from rank 24 is probably: (1) collision-avoidance tightening, (2) the very rare opportunistic miner build when a mining node is on an adjacent tile, (3) late-game wall removal. Closing those gaps lifts us to rank ~15 even without adopting the full bunterrrrr economy.
""",
}


def main() -> None:
    for slug, body in ARCHIVES.items():
        path = TOP_DIR / slug / "profile.md"
        if not path.exists():
            print(f"[skip] {path} missing")
            continue
        text = path.read_text(encoding="utf-8")
        # Drop any prior tactical archive block (between "## Tactical archive" and next H2 or EOF).
        cleaned = re.sub(
            r"\n## Tactical archive\n.*?(?=\n## |\Z)",
            "\n",
            text,
            flags=re.DOTALL,
        )
        if not cleaned.endswith("\n"):
            cleaned += "\n"
        cleaned += "\n" + body.strip() + "\n"
        path.write_text(cleaned, encoding="utf-8")
        print(f"[append] {path}")


if __name__ == "__main__":
    main()
