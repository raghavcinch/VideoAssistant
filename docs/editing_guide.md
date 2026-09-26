# VideoAssistant Editing Guide (Real Estate / Walkthrough)

This guide is intentionally **actionable**: it maps editing best practices to the knobs VideoAssistant can actually automate in DaVinci Resolve.

## 1) Workflow: reliable order of operations

1. **Stabilize first in Resolve** (Deliver stabilized renders).
2. Run VideoAssistant analysis on stabilized renders:
   - finds stable segments ("selects")
   - classifies shot motion (static/pan/tilt/walk/arc/etc.)
   - estimates horizon roll (for gentle correction)
   - plans speed ramps (optional)
3. Import selects into Resolve via the generated script.
4. Review per-room timelines, then do your human pass:
   - remove repeats
   - tighten timings
   - add intentional transitions where needed
5. Color + finishing (after timing is locked).

## 2) Shot choice & pacing (walkthrough-friendly)

### Establish → detail → move pattern
For each room, aim for a repeatable micro-structure:
- **Establish**: 1 wide/slow-move shot that tells the viewer "where we are".
- **Details**: 2–4 tighter shots (static or gentle pan/tilt) that show finishes.
- **Move**: a short move (walk/arc) to reposition or reveal.

VideoAssistant’s cinematic sequencing tries to alternate **move** and **detail** shots and avoid repeating the same source clip back-to-back.

### Duration targets (starting point)
These are rules of thumb (adjust by room size and viewer intent):
- Establishing: ~3–6s
- Details: ~1.5–3.5s
- Movement shots: ~2–4s (shorter if it feels “floaty”)

If a shot has visible wobble or rolling-shutter artifacts after stabilization, prefer **shorter** durations.

## 3) Cutting rules that translate to automation

### Cut on motion / avoid jumpy angle repeats
- If two consecutive shots are similar framing, cut when there’s a **natural movement change** (camera slows/stops or begins moving).
- Avoid: static → static with near-identical framing unless it’s a deliberate “before/after”.

### Avoid speed changes in high-detail motion
Speed ramps look best when:
- the camera path is predictable (arc/pan/tilt)
- there are no fast-moving foreground objects
- the shot is already stable

If a shot is “busy” or highly textured (e.g., blinds, fine patterns), keep ramps subtle.

## 4) Speed ramps (what we can do programmatically)

Resolve’s public scripting API does not expose Edit-page retime curve controls directly, but it **does** allow attaching a Fusion composition to each timeline item.

VideoAssistant now applies speed ramps as a **Fusion `TimeSpeed` node** with keyframed `Speed` values.

### Practical guidance
- Use ramps to add “polish”, not to rescue weak shots.
- Prefer **subtle** ramps that stay close to realtime.
   - Deep slow-downs tend to cause repeated frames (“looping”) and jitter unless you’re using true optical-flow retiming.
- Prefer a mild **fast → slow → fast** for reveals and a very gentle **slow hold** for static shots.
- Keep ramps long enough to feel smooth (avoid ultra-short ramps that read as a glitch).

### How to verify in Resolve
- Select a ramped clip, go to **Fusion** page.
- You’ll see a composition named `VA_RAMP` (or a TimeSpeed node in the comp).
- Playback should reflect the speed change even if Edit-page retime UI does not show a curve.

If playback stutters, enable Render Cache for Fusion clips or pre-render that section.

Note: In Fusion `TimeSpeed`, **Blend**/**Flow** interpolation can look like motion blur/smearing on walkthrough footage.
If you want crisp motion, use **Nearest** interpolation and keep ramps subtle.

## 5) Horizon/roll correction (micro-fix)

When roll is detected with enough confidence, the import script applies:
- `RotationAngle` (small correction)
- a small linked zoom to hide corner gaps

Best practice:
- keep roll correction small; big rotations usually look like a mistake.
- if a shot is truly rotated, it’s often better to re-stabilize or reframe manually.

## 6) Re-runs & project hygiene

The generated import script now **reuses and clears** existing per-room timelines (instead of creating `..._2`, `..._3`).

Best practice:
- Treat generated timelines as **rebuildable**.
- If you want to preserve manual edits, duplicate the timeline first and work on the duplicate.
