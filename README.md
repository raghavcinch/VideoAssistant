# VideoAssistant (Real Estate)

Local assistant that scans raw footage, finds stable "best segments" inside each clip (time-sliced shakiness scoring), and exports a DaVinci Resolve handoff (CSV + optional Resolve scripting).

## Agent-based architecture

This repo follows a simple "agent" pattern (similar in spirit to Copilot Agents):

- Each agent does one job and writes artifacts to `.va/` or the chosen output folder.
- A `VideoEditorAgent` orchestrates agents in a fixed order for a single property folder.

Agents:

- `IndexAgent`: finds clips + assigns `room`
- `ShakinessAgent`: computes time-sliced shakiness metrics
- `SelectsAgent`: picks best stable segments (`t_in`, `t_out`) per clip
- `ExportAgent`: writes `selects.csv` and `resolve_import_selects.py`

Orchestrator:

- `VideoEditorAgent`: runs the pipeline and writes `.va/run_log.json`

### VS Code multi-agent "studio" setup

In addition to the Python agent pipeline, this repo includes a VS Code multi-agent setup that mirrors a real editing studio (Producer → AE → Editor → Finishing → QC).

- Custom agents live in `.github/agents/` (files ending in `.agent.md`)
- Reusable procedures live in `.github/skills/` (each skill is a folder containing `SKILL.md`)

See: `docs/studio_setup.md`

Advanced techniques coverage: `docs/advanced_techniques_matrix.md`
Materials alignment (books → SOPs): `docs/materials_alignment.md`

## Quick start

1. Create/activate a venv (you already have `.venv`).
2. Install deps:

```powershell
python -m pip install -r requirements.txt
```

3. Run on a folder:

```powershell
python -m videoassistant.cli process --root "D:\PropertyFolder" --out .\out --project "VA_Property"
```

Outputs land in `out/` (CSV + Resolve helper script).

## Room-based deliverables

You said: one property folder in, one deliverable per room out (e.g. `LIVING_ROOM`, `KITCHEN`).

The assistant assigns each clip a `room` using filename/folder keyword heuristics (see `videoassistant/rooms.py`).

### Custom room keywords (recommended)

Create a room keyword file in the property folder at `.va/room_keywords.json`.

You can generate a starter template:

```powershell
python -m videoassistant.cli init-rooms --root "D:\PropertyFolder"
```

Then edit `.va/room_keywords.json` to add your own rooms/keywords (e.g. `foyer`, `pooja`, `wardrobe`).

Best results if you either:

- Put footage into room subfolders inside the property folder (e.g. `Living Room/`, `Kitchen/`), OR
- Include room keywords in filenames (e.g. `living_01.mov`, `kitchen_pan.mov`).

The Resolve export script creates:

- One bin per room
- One timeline per room (named like `LIVING_ROOM`, `KITCHEN`)
- IN/OUT markers on clips to show the recommended stable segments
