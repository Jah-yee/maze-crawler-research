#!/usr/bin/env python3
"""Poll experiments/ and log combo-test triggers when v44b/v46/v47 update.

On a new-or-modified main.py that passes py_compile, append a suggestion
to reports/combo_trigger.txt. Does NOT run combos. --once = single pass.
"""
from __future__ import annotations
import argparse, datetime as dt, py_compile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments"
LOG = ROOT / "reports" / "combo_trigger.txt"
TARGETS = {  # exact dir name -> suggested next combos
    "v44b_transfer_only":  ["v51_econ_plus_defense (with v46)", "v52_econ_plus_antimirror (with v47)"],
    "v46_defense_bundle":  ["v51_econ_plus_defense (with v44b)", "v53_defense_plus_antimirror (with v47)"],
    "v47_dirs_split":      ["v52_econ_plus_antimirror (with v44b)", "v53_defense_plus_antimirror (with v46)"],
}


def _snapshot() -> dict[str, float]:
    return {d.name: (d / "main.py").stat().st_mtime
            for d in EXP.glob("v*") if (d / "main.py").is_file()}

def _suggest(name: str) -> list[str]:
    return TARGETS.get(name, [])

def _tick(prev: dict[str, float]) -> dict[str, float]:
    cur = _snapshot()
    for name, mt in cur.items():
        if prev.get(name) == mt or not (sugg := _suggest(name)):
            continue
        path = EXP / name / "main.py"
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as e:
            print(f"[watch] {name} updated but py_compile FAILED: {e}")
            continue
        ts = dt.datetime.now().isoformat(timespec="seconds")
        line = f"[{ts}] TRIGGER {name}  ({path})\n" + "".join(f"  -> {s}\n" for s in sugg)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.open("a").write(line)
        print(line, end="")
    return cur

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    prev = _snapshot()
    print(f"[watch] baseline = {len(prev)} dirs; targets={list(TARGETS)}")
    if args.once:
        _tick(prev); return
    while True:
        time.sleep(args.interval)
        prev = _tick(prev)

if __name__ == "__main__":
    main()
