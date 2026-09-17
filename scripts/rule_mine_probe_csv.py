#!/usr/bin/env python3
"""Mine shallow, human-readable rules from probe CSVs.

This is analysis-only. The exported trees are hypotheses for hand-reviewed
rules; they are not intended to be imported into a runtime agent.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.tree import DecisionTreeClassifier, export_text


DEFAULT_STEPS = [
    "reports/probes/active_v51_53414790_phase_route_steps.csv",
    "reports/probes/active_v67_53414814_phase_route_steps.csv",
    "reports/probes/hist_v51_53412795_phase_route_steps.csv",
    "reports/probes/hist_v99_53412815_phase_route_steps.csv",
]

FEATURES = [
    "step_idx",
    "phase_id",
    "factory_gap",
    "factory_energy",
    "f_move_cd",
    "f_jump_cd",
    "f_build_cd",
    "scout_count",
    "worker_count",
    "miner_count",
    "support_count",
    "support_energy",
    "opp_support_count",
    "opp_support_energy",
    "collision_tiebreak_bad",
    "enemy_factory_near",
    "rq_known_available",
    "rq_known_score",
    "rq_oracle_score",
    "can_move_north",
    "can_jump_north",
    "north_wall_blocked",
    "north_cell_occupied",
    "jump_north_landing_occupied",
    "factory_action_is_build",
    "factory_action_is_transfer",
    "factory_action_is_jump",
    "factory_action_is_lateral",
    "factory_action_is_south",
    "late_spend_action",
    "late_support_spend_count",
    "r1_transfer_candidate",
    "r1_transfer_fired",
    "mine_build_candidate_north",
    "scout_build_candidate",
    "worker_build_candidate",
]


def truthy(value: object) -> int:
    return int(str(value or "").strip().lower() in {"1", "true", "yes", "y"})


def numeric(row: dict[str, str], key: str) -> float:
    raw = str(row.get(key, "")).strip()
    if raw == "":
        return 0.0
    if raw.lower() in {"true", "false"}:
        return float(raw.lower() == "true")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def load_rows(paths: list[Path], target: str) -> tuple[np.ndarray, np.ndarray, list[dict[str, str]]]:
    xs: list[list[float]] = []
    ys: list[int] = []
    raw_rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source_group") == "source_group":
                    continue
                xs.append([numeric(row, feat) for feat in FEATURES])
                ys.append(truthy(row.get(target)))
                raw_rows.append(row)
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=int), raw_rows


def summarize_groups(rows: list[dict[str, str]], target: str, top_n: int = 20) -> list[tuple]:
    groups: dict[tuple[str, str, str, str], list[int]] = {}
    for row in rows:
        key = (
            row.get("source_group", ""),
            row.get("phase", ""),
            row.get("rq_oracle_bucket", ""),
            row.get("factory_action_head", ""),
        )
        groups.setdefault(key, []).append(truthy(row.get(target)))
    ranked = []
    for key, vals in groups.items():
        if len(vals) < 10:
            continue
        positives = sum(vals)
        ranked.append((positives / len(vals), positives, len(vals), key))
    ranked.sort(key=lambda x: (-x[0], -x[1], -x[2]))
    return ranked[:top_n]


def write_report(
    out: Path,
    target: str,
    x: np.ndarray,
    y: np.ndarray,
    rows: list[dict[str, str]],
    max_depth: int,
    min_samples_leaf: int,
) -> None:
    positives = int(y.sum())
    clf = DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        class_weight="balanced",
        random_state=0,
    )
    clf.fit(x, y)
    pred = clf.predict(x)
    tree_text = export_text(clf, feature_names=FEATURES, decimals=2)
    labels = [0, 1]
    cm = confusion_matrix(y, pred, labels=labels)
    report = classification_report(y, pred, labels=labels, zero_division=0)

    lines = [
        f"# Probe Rule Mining: `{target}` - 2026-06-06",
        "",
        "Analysis-only shallow tree. Use these as hypotheses for manual rules, not as runtime ML.",
        "",
        f"- Rows: `{len(y)}`",
        f"- Positives: `{positives}`",
        f"- Positive rate: `{positives / len(y) if len(y) else 0:.4f}`",
        f"- Max depth: `{max_depth}`",
        f"- Min samples leaf: `{min_samples_leaf}`",
        "",
        "## Decision Tree",
        "",
        "```text",
        tree_text,
        "```",
        "",
        "## Training Confusion Matrix",
        "",
        "```text",
        str(cm),
        "```",
        "",
        "## Classification Report",
        "",
        "```text",
        report,
        "```",
        "",
        "## High-Rate Phase / Route / Action Buckets",
        "",
        "| Rate | Positives | Rows | Source | Phase | Oracle route | Action head |",
        "|---:|---:|---:|---|---|---|---|",
    ]
    for rate, pos, count, key in summarize_groups(rows, target):
        lines.append(f"| {rate:.3f} | {pos} | {count} | {key[0]} | {key[1]} | {key[2]} | {key[3]} |")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", nargs="*", type=Path, default=[Path(p) for p in DEFAULT_STEPS])
    ap.add_argument("--target", default="bad_any")
    ap.add_argument("--max-depth", type=int, default=4)
    ap.add_argument("--min-samples-leaf", type=int, default=50)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    paths = [p.expanduser().resolve() for p in args.steps]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise SystemExit(f"missing step CSV(s): {', '.join(missing)}")

    x, y, rows = load_rows(paths, args.target)
    if len(set(y.tolist())) < 2:
        raise SystemExit(f"target {args.target!r} has only one class")
    out = args.out or Path(f"reports/probe_rule_mine_{args.target}_20260606.md")
    write_report(out.expanduser(), args.target, x, y, rows, args.max_depth, args.min_samples_leaf)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
