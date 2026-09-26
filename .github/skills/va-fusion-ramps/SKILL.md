---
name: va-fusion-ramps
description: Apply and tune subtle variable speed ramps using Fusion TimeSpeed on Resolve TimelineItems; avoid jitter/repeats/smear.
argument-hint: "ramp style=subtle|none"
---

# Fusion TimeSpeed Ramps

Use when the user wants “real” speed ramps created programmatically.

## Approach (what this repo does)
- Edit-page retime curves aren’t scriptable.
- Instead, attach a Fusion comp to each TimelineItem and keyframe a `TimeSpeed` node’s `Speed`.

## Quality rules (defaults)
- Keep speeds close to 1.0 (subtle). Deep slowdowns cause repeated frames/jitter.
- If Blend/Flow creates motion smear, prefer nearest/crisp interpolation.

## Debugging checklist
- Confirm the `VA_RAMP` comp exists on the timeline item.
- Confirm `TimeSpeed.Speed` has keyframes.
- If motion looks “cheap”: reduce ramp amplitude and number of changes.

## Related
- See [docs/editing_guide.md](../../../docs/editing_guide.md).