# Advanced Techniques → Specialist Agent Coverage

This is the “who owns what” map for advanced post techniques.

## Techniques

- Export / delivery: `va-export` + `/va-export`
  - Status: guidance + checklist (plus any existing scripted renders)
- 4K upscaling: `va-upscale` + `/va-upscale-4k`
  - Status: guidance + QC focus (typically interactive in Resolve)
- Masking / roto (privacy, windows, cleanup): `va-masking` + `/va-masking`
  - Status: guidance + SOP (interactive in Resolve)
- Object / planar tracking (for masks/titles/cleanup): `va-tracking` + `/va-tracking`
  - Status: guidance + SOP (interactive in Resolve)
- Tracking-based stabilization quality: `va-stabilize-tracking` + `/va-stabilize-tracking`
  - Status: guidance + settings/QC (interactive in Resolve)
- Stabilize-first workflow (stabilize then analyze): `va-stabilize` + `/va-stabilize-first`
  - Status: partially automated (Resolve scripting for stabilize+render exists)
- Speed ramp editing (programmatic): `va-finishing` / `va-resolve-td` + `/va-fusion-ramps`
  - Status: automated via Fusion `TimeSpeed` comps (subtle by default)
- Color correction SOP: `va-color` + `/va-color-correction`
  - Status: guidance + repeatable workflow (interactive grading)

## Materials integration

- Use `docs/editing_books_structure.json` to locate relevant book sections.
- Convert to original SOP/checklists; do not paste book text into repo outputs.
