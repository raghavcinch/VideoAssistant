---
name: va-export
description: Studio export/delivery SOP: render settings, naming conventions, and delivery QC for real-estate videos.
argument-hint: "platform=YouTube resolution=4K fps=30"
---

# Export / Delivery SOP

Use at the end of the pipeline.

If present, treat [docs/materials_notes.md](../../../docs/materials_notes.md) as the authoritative studio SOP.

## Decide deliverables
- Primary: YouTube master (typical: 4K or 1080p depending on source)
- Optional: 1080p fast upload, IG vertical cut

## Resolve Deliver checklist
- Confirm timeline fps matches source intent (avoid unintended frame rate conversions)
- Confirm video scopes look sane (no crushed blacks/highlights unless stylistic)
- Confirm audio peaks don’t clip; verify dialogue/music balance if present
- Confirm titles/graphics safe areas and no edge cutoffs
- Export format/codec per platform requirements

## Recommended defaults (when user doesn’t specify)
- Platform: YouTube
- Delivery: MP4 container
- Codec: H.265/HEVC if available, else H.264
- Resolution: match source; upscale only when requested/beneficial
- Audio: AAC, stereo

## Naming + folders
- `deliverables/<PROPERTY>/<DATE>/master_<RES>_<FPS>.<ext>`
- Keep a text log of settings for reproducibility

## Handoff
- Run `/va-qc` or hand off to QC agent for final checks.

## References
- Use `docs/editing_books_structure.json` to locate export-related topics in `Editing-Books/`.
- Do not paste book text into outputs; convert to original SOP steps.