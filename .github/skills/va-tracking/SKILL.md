---
name: va-tracking
description: Tracking SOP for masking, titles, and cleanup (planar/point/surface) with troubleshooting guidance.
argument-hint: "track target + shot type"
---

# Tracking SOP

Use when a mask, title, or cleanup needs to stick to a moving object/surface.

## Choose tracker
- Planar/surface for walls, screens, signs
- Point tracker for small distinct features

## Troubleshooting
- Occlusion: split track into segments
- Motion blur: pick frames with clearer features
- Drift: reduce search region, add manual keyframes

## Handoff
- Send results to `va-masking` or `va-finishing` depending on usage.

## References
- Use `docs/editing_books_structure.json` to locate tracking-related topics in `Editing-Books/`.
- Output must be original SOP steps.