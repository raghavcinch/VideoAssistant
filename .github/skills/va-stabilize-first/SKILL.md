---
name: va-stabilize-first
description: Run the practical workflow: stabilize in Resolve first, then analyze stabilized renders to generate selects and timelines.
argument-hint: "stabilized_root=<folder> out=<folder>"
---

# Stabilize-First Workflow

Use when raw camera gyro data is unreliable or shakiness analysis is noisy.

## Steps
1) In Resolve, stabilize the raw clips (interactive).
2) Render stabilized clips to a clean folder:
- Prefer stable filenames and a room-friendly structure.
3) Run VideoAssistant on the stabilized render root.

## Why this works
- The assistant selects stable segments; stabilizing first makes the stability signal meaningful.

## Done when
- `selects.csv` and `resolve_import_selects.py` are generated from stabilized media.