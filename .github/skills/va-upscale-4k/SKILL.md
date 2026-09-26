---
name: va-upscale-4k
description: 4K upscaling guidance: when to upscale, how to do it in Resolve, and how to avoid sharpening/halo artifacts.
argument-hint: "source=1080p target=4K"
---

# 4K Upscaling

Use when client/platform needs 4K but footage is lower-res.

## Principles
- Don’t upscale if it makes artifacts more visible than the benefit.
- Prefer gentle sharpening and noise management before upscaling.

## Resolve approach (practical)
- Decide whether to upscale via timeline resolution or via per-clip tools (e.g., Super Scale where available).
- Review fine edges (railings, blinds) for halos.

## QC focus
- Haloing, ringing, moiré, and over-sharpened textures.

## References
- Use `docs/editing_books_structure.json` to find upscaling-related Resolve sections in `Editing-Books/`.
- Keep guidance original and procedural.