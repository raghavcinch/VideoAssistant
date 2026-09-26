---
name: va-masking
description: Masking/roto SOP: privacy blur, windows, object removal, and edge-quality QC.
argument-hint: "mask=faces|plates|screens"
---

# Masking / Roto SOP

Use when footage needs privacy blurs, cleanup, or localized grading.

## Checklist
- Identify what must be masked and for how long
- Choose tool: power window (Color) vs Fusion mask
- If motion: track the mask (hand off to `/va-tracking`)

## QC
- Edge chatter/flicker
- Temporal consistency (no popping)
- Feather appropriate for scale

## Time management
- Prefer the simplest mask that meets the requirement.

## References
- Use `docs/editing_books_structure.json` to locate masking/cleanup topics in `Editing-Books/`.
- Do not reproduce book text; write original checklists.