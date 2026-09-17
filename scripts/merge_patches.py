#!/usr/bin/env python3
"""Segment-based main.py merger (line-replace, not AST).

Convention: a combinable region is wrapped with
  # === BEGIN <name> ===
  ...
  # === END <name> ===
The --into file may also use  # === INSERT_HERE === <name>  as a placeholder.
Copies one or more segments from --from into --into and writes --out.

Usage:
  .venv/bin/python scripts/merge_patches.py --into A.py --from B.py \
      --segment v46_final_kick --segment v46_energy_floor --out OUT.py
"""
from __future__ import annotations
import argparse
import py_compile
import re
import sys
from pathlib import Path


def _block(lines: list[str], name: str) -> tuple[int, int] | None:
    begin = re.compile(rf"#\s*===\s*BEGIN\s+{re.escape(name)}\s*===\s*$")
    end = re.compile(rf"#\s*===\s*END\s+{re.escape(name)}\s*===\s*$")
    start = next((i for i, l in enumerate(lines) if begin.match(l.strip())), None)
    if start is None:
        return None
    stop = next((i for i, l in enumerate(lines[start + 1:], start + 1)
                 if end.match(l.strip())), None)
    if stop is None:
        raise SystemExit(f"unterminated BEGIN block for {name}")
    return start, stop


def _placeholder(lines: list[str], name: str) -> int | None:
    pat = re.compile(rf"#\s*===\s*INSERT_HERE\s*===\s+{re.escape(name)}\s*$")
    return next((i for i, l in enumerate(lines) if pat.match(l.strip())), None)


def _apply(into: list[str], segment: list[str], name: str) -> list[str]:
    existing = _block(into, name)
    if existing:
        s, e = existing
        return into[:s] + segment + into[e + 1:]
    ph = _placeholder(into, name)
    if ph is not None:
        return into[:ph] + segment + into[ph + 1:]
    raise SystemExit(f"target lacks BEGIN/END or '=== INSERT_HERE === {name}'; see docs/manual_merge_guide.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--into", required=True, type=Path)
    ap.add_argument("--from", dest="src", required=True, type=Path)
    ap.add_argument("--segment", action="append", required=True, help="repeatable")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    into = args.into.read_text().splitlines(keepends=True)
    src = args.src.read_text().splitlines(keepends=True)
    for name in args.segment:
        loc = _block(src, name)
        if loc is None:
            raise SystemExit(f"source lacks BEGIN/END block for {name}")
        seg = src[loc[0]:loc[1] + 1]
        into = _apply(into, seg, name)
        print(f"  + merged {name} ({len(seg)} lines)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(into))
    try:
        py_compile.compile(str(args.out), doraise=True)
    except py_compile.PyCompileError as e:
        sys.exit(f"WARN: py_compile failed for {args.out}: {e}")
    print(f"OK -> {args.out} (py_compile passed)")


if __name__ == "__main__":
    main()
