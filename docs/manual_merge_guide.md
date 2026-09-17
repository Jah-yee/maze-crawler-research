# Manual merge guide (when no magic comments exist)

`scripts/merge_patches.py` only works when both source and target wrap their
segment(s) with `# === BEGIN <name> === / # === END <name> ===` markers
(or the target uses `# === INSERT_HERE === <name>` as a placeholder).

Worker outputs from v44b / v46 / v47 currently do **not** include these markers,
and we intentionally do not edit other workers' files. Use this manual recipe
instead when building v51–v54.

## Step 1 — choose the base

Copy the largest contributor as `experiments/<vNew>/main.py`. Typically:

| target | copy this as base |
| --- | --- |
| v51 (econ + defense) | `experiments/v44b_transfer_only/main.py` |
| v52 (econ + anti-mirror) | `experiments/v44b_transfer_only/main.py` |
| v53 (defense + anti-mirror) | `experiments/v46_defense_bundle/main.py` |
| v54 (full stack) | start from v51, then layer v47 on top |

```bash
cp experiments/v44b_transfer_only/main.py experiments/v51_econ_plus_defense/main.py
```

## Step 2 — diff against v37 to identify each contributor's change set

```bash
diff -u experiments/v37_late_save_jump_no_scout/main.py \
        experiments/v46_defense_bundle/main.py > /tmp/v46_vs_v37.diff
```

Read the diff and **group** changes into named hunks, e.g.:

- `v46_final_kick` — late-turn kick into enemy core
- `v46_energy_floor` — refuse to spend below threshold
- `v46_emergency_north_fallback` — fallback when north blocked

## Step 3 — paste each hunk into the base by hand

For each hunk, locate the corresponding region in the base file (use surrounding
unchanged context lines as anchors) and wrap the pasted block:

```python
# === BEGIN v46_final_kick ===
... pasted body ...
# === END v46_final_kick ===
```

These markers are how `merge_patches.py` finds the block later — so once you've
done this once, future re-merges (e.g. when v46 improves) become a one-command
operation:

```bash
.venv/bin/python scripts/merge_patches.py \
    --into experiments/v51_econ_plus_defense/main.py \
    --from experiments/v46_defense_bundle/main.py \
    --segment v46_final_kick --out experiments/v51_econ_plus_defense/main.py
```

(For the first build, source side will lack BEGIN/END too — wrap it locally in
a scratch copy or accept that the first merge stays manual.)

## Step 4 — validate

```bash
.venv/bin/python -m py_compile experiments/v51_econ_plus_defense/main.py
.venv/bin/python scripts/paired_eval.py \
    --a experiments/v51_econ_plus_defense/main.py \
    --b experiments/v37_late_save_jump_no_scout/main.py --seeds 40
```

If z < 0 — bisect by removing one segment at a time.

## Conflict cheatsheet

| both A & B touched... | resolution |
| --- | --- |
| same `BUILD_MINER` priority block | take v44b's version (econ-focused) |
| same `final_kick` window | take v46's (defense-focused) |
| same `random.choice(DIRS)` site | take v47's (it added hash noise) |
| same `if turn >= NN` gate | merge conditions with `and`, not `or` |

When in doubt: **keep the base's version**, then layer the smallest delta from
the other contributor that still expresses its intent.
