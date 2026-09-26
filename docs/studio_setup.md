# VideoAssistant Studio Setup (VS Code Multi-Agent)

This repo includes VS Code **custom agents** and **Agent Skills** that mirror a real post-production studio.
Humans normally doing specialized jobs become dedicated agents in this workflow.

## Where things live

- Custom agents: `.github/agents/*.agent.md`
- Skills (reusable procedures): `.github/skills/*/SKILL.md`

VS Code auto-detects these and shows them in:
- the **Agents** dropdown (custom agents)
- the `/` slash menu (skills)

If you keep purchased references in this repo, see:
- `docs/editing_books_structure.json` (structure-only index)
- `docs/materials_alignment.md` (how we apply materials without copying text)

## The “studio roster”

Start with the coordinator, then run specialists like you would in a studio.

- `va-studio` (Coordinator / Post Supervisor)
- `va-producer` (Producer/Director brief)
- `va-ae` (Assistant Editor: ingest/rooms/run pipeline)
- `va-stabilize` (Stabilization tech: stabilize-first workflow)
- `va-editor` (Editor: selects + sequencing intent)
- `va-finishing` (Online/Finishing: horizon + ramps + idempotent import)
- `va-color` (Colorist guidance)
- `va-masking` (Masking/roto: privacy blurs, windows, cleanup)
- `va-tracking` (Object/planar tracking guidance)
- `va-stabilize-tracking` (Stabilization quality tuning)
- `va-upscale` (4K upscaling strategy)
- `va-export` (Delivery/export settings + checklist)
- `va-resolve-td` (Resolve TD: scripting + Fusion/debug)
- `va-qc` (QC/Delivery)

## Typical run order

1) Producer writes a brief (deliverable, duration, pacing, must-include rooms)
2) AE runs the pipeline to generate:
   - `selects.csv`
   - `resolve_import_selects.py`
   - `.va/run_log.json`
3) Editor validates selects/coverage and requests regeneration if needed
4) Finishing runs/validates Resolve import, ramps, rotation/zoom
5) Optional specialist passes (as needed): masking/tracking, upscale, delivery/export
6) QC runs diagnostics and gives PASS/FAIL + defect list

## How this maps to the code pipeline

Internally, the Python orchestrator `VideoEditorAgent` runs these steps (when enabled):
- Index → (optional) Stabilize-first → Shakiness → Selects → Export → Resolve Import → Correction

See: `src/videoassistant/agents/video_editor.py`

## Skills you can invoke

Type `/` in chat:
- `/va-job-brief`
- `/va-room-keywords`
- `/va-stabilize-first`
- `/va-resolve-import`
- `/va-fusion-ramps`
- `/va-masking`
- `/va-tracking`
- `/va-stabilize-tracking`
- `/va-upscale-4k`
- `/va-export`
- `/va-qc`

## Notes

- The goal is **clean handoffs**. Each role produces specific artifacts/decisions and then hands off.
- Keep finishing conservative for real estate: subtle ramps and safe transforms.
- Some advanced techniques (masking/roto, object tracking, upscaling decisions) are currently **guidance + Resolve SOP** rather than fully automated via scripting in this repo.

## Resolve template project (recommended)

Resolve’s scripting API does not reliably expose the Stabilizer **Mode** (Perspective/Similarity/Translation), so the safest way to avoid “Perspective warp jitter” is to use a template project.

- Create (once): run `tools/resolve/create_template_project.py` (default project: `VA_TEMPLATE`).
- In Resolve, open `VA_TEMPLATE` and put any clip on timeline `00_TEMPLATE`.
- Set **Inspector → Stabilization → Mode = Similarity**.
- For a new job: duplicate `VA_TEMPLATE` to `VA_<JOB>`.
- Apply the same settings to other clips: copy the reference timeline clip → select target clips → **Paste Attributes…** → enable *Stabilization*.
