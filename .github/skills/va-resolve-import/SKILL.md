---
name: va-resolve-import
description: Import VideoAssistant outputs into DaVinci Resolve reliably (bins, room timelines, idempotent regeneration).
argument-hint: "out=<output folder>"
---

# Resolve Import Handoff

Use when running the generated Resolve import script, or when debugging duplicates/stale timelines.

## Inputs
- `selects.csv`
- `resolve_import_selects.py`

## Procedure
- Open Resolve project.
- Run the generated script with Resolve’s scripting environment (per your setup).

## Expectations
- One bin per room
- One timeline per room (and optional `*_SELECTS_CINE` timelines)
- Re-running should not create confusing duplicates for generated timelines

## If something looks duplicated
- Verify you’re viewing the latest generated timeline name.
- If needed, delete/recreate generated timelines (the exporter prefers idempotency).

## Related
- See [docs/editing_guide.md](../../../docs/editing_guide.md) for finishing conventions.