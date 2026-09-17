#!/usr/bin/env python3
"""Extract %%writefile cells from Kaggle notebooks."""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat


def normalize_header(line: str) -> tuple[bool, Path] | None:
    parts = line.strip().split()
    if not parts or parts[0] != "%%writefile":
        return None

    append = False
    target = None
    for part in parts[1:]:
        if part == "-a":
            append = True
        elif not part.startswith("-"):
            target = Path(part)

    if target is None:
        raise ValueError(f"Cannot parse writefile header: {line!r}")
    return append, target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--target",
        default=None,
        help="Only extract this notebook write target, e.g. main.py.",
    )
    args = parser.parse_args()

    nb = nbformat.read(args.notebook, as_version=4)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[Path, int] = {}
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        source = cell.source
        lines = source.splitlines(keepends=True)
        if not lines:
            continue
        parsed = normalize_header(lines[0])
        if parsed is None:
            continue
        append, target = parsed
        if args.target is not None and target.as_posix() != args.target:
            continue

        out_path = args.out_dir / target.name
        mode = "a" if append else "w"
        with out_path.open(mode, encoding="utf-8") as fh:
            fh.writelines(lines[1:])
            if lines[1:] and not lines[-1].endswith("\n"):
                fh.write("\n")
        written[out_path] = written.get(out_path, 0) + 1

    if not written:
        raise SystemExit("No matching %%writefile cells found.")

    for path, count in sorted(written.items()):
        print(f"{path} ({count} cells)")


if __name__ == "__main__":
    main()
