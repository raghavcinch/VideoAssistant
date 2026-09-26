---
name: va-qc
description: Run QC checks for generated Resolve timelines and artifacts (no duplicates, expected clip counts, ramps OK).
argument-hint: "project=<Resolve project name>"
---

# QC & Delivery

Use at the end of a run or when the user reports odd behavior (loops, duplicates, empty timelines).

## Quick checks
- Artifacts exist: `.va/run_log.json`, `selects.csv`, `resolve_import_selects.py`.
- Timeline clip counts match expectation.
- Ramps are subtle and do not repeat/loop.

## Useful scripts
- `tools/resolve/list_timeline_item_counts.py`
- `tools/resolve/inspect_va_ramp_comp.py`

## Output format
- PASS/FAIL
- Defects (with reproduction)
- Next role to engage (AE / Editor / Finishing / Resolve TD).