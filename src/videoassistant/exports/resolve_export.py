from __future__ import annotations

import json
from pathlib import Path


def _ramp_hint(seg: dict) -> dict:
    """Return a lightweight speed-ramp recommendation for a segment.

    Resolve scripting does not expose speed-ramp keyframing; we use this to
    annotate timeline items with markers so you can apply it quickly in the UI.
    """

    st = (seg.get("shot_type") or "").lower()
    try:
        motion_speed = float(seg.get("motion_speed") or 0.0)
    except Exception:
        motion_speed = 0.0
    try:
        curvature = float(seg.get("motion_curvature") or 0.0)
    except Exception:
        curvature = 0.0

    # fastness in [0..1]
    fastness = 1.0 / (1.0 + pow(2.718281828, -((motion_speed - 1.0) / 0.5)))
    subtle = 0.35 + 0.55 * fastness

    kind = "constant"
    s_start = 1.0
    s_mid = 1.0
    s_end = 1.0

    if st == "arc":
        kind = "fast_slow_fast"
        s_mid = max(0.65, min(0.90, 0.65 + 0.25 * subtle))
        s_start = max(1.0, min(1.18, 1.05 + 0.10 * (1.0 - subtle)))
        s_end = s_start
    elif st == "walk":
        kind = "fast_to_slow"
        s_start = max(1.0, min(1.22, 1.08 + 0.12 * (1.0 - subtle)))
        s_end = max(0.75, min(0.95, 0.78 + 0.12 * subtle))
        s_mid = s_end
    elif st in {"pan", "tilt", "slow_pan", "slow_tilt"}:
        kind = "subtle_fast_slow_fast"
        s_mid = max(0.78, min(0.95, 0.78 + 0.10 * subtle))
        s_start = max(1.0, min(1.14, 1.03 + 0.08 * (1.0 - subtle)))
        s_end = s_start
    elif st == "static":
        kind = "slow_hold"
        s_mid = max(0.62, min(0.82, 0.62 + 0.15 * subtle))

    elif curvature >= 0.42:
        kind = "fast_slow_fast"
        s_mid = max(0.70, min(0.92, 0.70 + 0.20 * subtle))
        s_start = max(1.0, min(1.16, 1.03 + 0.10 * (1.0 - subtle)))
        s_end = s_start

    return {
        "kind": kind,
        "start": float(s_start),
        "mid": float(s_mid),
        "end": float(s_end),
    }


def _segment_role(seg: dict) -> str:
    st = (seg.get("shot_type") or "unknown").lower()
    try:
        dur = float(seg.get("t_out", 0.0)) - float(seg.get("t_in", 0.0))
    except Exception:
        dur = 0.0

    if st in {"static", "slow_pan", "slow_tilt"}:
        return "establish" if dur >= 4.0 else "detail"
    if st in {"pan", "tilt", "arc", "walk"}:
        return "move"
    if st in {"whip"}:
        return "transition"
    if st in {"shaky"}:
        return "avoid"
    return "move" if dur >= 4.0 else "detail"


def _cinematic_sequence(segments: list[dict]) -> list[dict]:
    """Greedy sequencing to make a more 'cinematic' flow.

    Priorities:
    - Start with a strong establishing shot when possible.
    - Alternate movement and detail shots.
    - Avoid using the same source clip back-to-back.
    - Prefer higher stability score and usable duration.
    """

    if not segments:
        return []

    remaining = segments[:]

    def weight(seg: dict) -> float:
        try:
            score = float(seg.get("score", 0.0))
        except Exception:
            score = 0.0
        # Stability score can be extreme when mean jitter is ~0; cap it so sequencing isn't dominated.
        score = min(score, 50.0)
        try:
            dur = float(seg.get("t_out", 0.0)) - float(seg.get("t_in", 0.0))
        except Exception:
            dur = 0.0
        # favor stability, then duration modestly
        return score * (1.0 + min(1.0, dur / 6.0) * 0.35)

    def pick(candidates: list[dict], last_rel: str | None) -> dict | None:
        if not candidates:
            return None
        # Prefer not repeating clip.
        non_repeat = [s for s in candidates if (not last_rel) or s.get("rel") != last_rel]
        pool = non_repeat or candidates
        pool.sort(key=weight, reverse=True)
        return pool[0]

    # Start: establishing if possible, otherwise best overall non-avoid.
    establishing = [s for s in remaining if _segment_role(s) == "establish"]
    first = pick(establishing, None)
    if first is None:
        ok = [s for s in remaining if _segment_role(s) != "avoid"]
        first = pick(ok, None) or remaining[0]
    out = [first]
    remaining.remove(first)

    # Alternate move/detail, inject a transition occasionally.
    role_cycle = ["move", "detail", "move", "detail", "move", "transition"]
    role_i = 0
    while remaining:
        last_rel = out[-1].get("rel")
        desired = role_cycle[role_i % len(role_cycle)]
        role_i += 1

        cand = [s for s in remaining if _segment_role(s) == desired and _segment_role(s) != "avoid"]
        chosen = pick(cand, last_rel)

        if chosen is None and desired != "transition":
            # fall back to any non-avoid, but try to keep variety
            cand = [s for s in remaining if _segment_role(s) != "avoid"]
            chosen = pick(cand, last_rel)
        if chosen is None:
            # last resort
            remaining.sort(key=weight, reverse=True)
            chosen = remaining[0]

        out.append(chosen)
        remaining.remove(chosen)

    return out


def write_resolve_script(path: Path, index: dict, selects: dict, project_name: str, sequence_mode: str = "cinematic") -> None:
    """Write a Resolve Python script that imports media and adds markers for suggested segments.

    Notes:
    - Resolve scripting APIs vary by version. This script is conservative: it imports media, creates bins,
      and adds clip markers at the in/out points.
    - Timeline assembly is attempted but may require minor tweaks depending on Resolve version.
    """

    # Pre-compute an ordered list of segments per room so timeline assembly is intentional.
    clips_by_rel = {c.get("rel"): c for c in (index.get("clips") or [])}
    ordered_segments_by_room: dict[str, list[dict]] = {}

    if (sequence_mode or "").lower() in {"cinematic", "cine", "cinema"}:
        room_to_segments: dict[str, list[dict]] = {}
        for rel, info in (selects.get("clips") or {}).items():
            if not info or info.get("error"):
                continue
            room = info.get("room") or (clips_by_rel.get(rel) or {}).get("room") or "unknown"
            for seg in info.get("segments") or []:
                d = dict(seg)
                d["rel"] = rel
                # carry file order hints
                clip = clips_by_rel.get(rel) or {}
                d["mtime"] = clip.get("mtime")
                d["name"] = clip.get("name")
                room_to_segments.setdefault(room, []).append(d)

        for room, segs in room_to_segments.items():
            # Make ordering deterministic within same source clip.
            try:
                segs.sort(key=lambda s: (str(s.get("rel") or ""), float(s.get("t_in", 0.0))))
            except Exception:
                pass
            ordered = _cinematic_sequence(segs)
            ordered_segments_by_room[room] = [
                {
                    "rel": s.get("rel"),
                    "t_in": float(s.get("t_in", 0.0)),
                    "t_out": float(s.get("t_out", 0.0)),
                    "score": float(s.get("score", 0.0)),
                    "shot_type": s.get("shot_type"),
                    "shot_confidence": (float(s.get("shot_confidence")) if s.get("shot_confidence") is not None else None),
                    "motion_speed": (float(s.get("motion_speed")) if s.get("motion_speed") is not None else None),
                    "motion_dir_var": (float(s.get("motion_dir_var")) if s.get("motion_dir_var") is not None else None),
                    "motion_curvature": (float(s.get("motion_curvature")) if s.get("motion_curvature") is not None else None),
                    "roll_deg": (float(s.get("roll_deg")) if s.get("roll_deg") is not None else None),
                    "ramp": _ramp_hint(s),
                }
                for s in ordered
                if s.get("rel")
            ]

    payload = {
        "project_name": project_name,
        "root": index.get("root"),
        "clips": index.get("clips"),
        "selects": selects,
        "sequence_mode": sequence_mode,
        "ordered_segments_by_room": ordered_segments_by_room,
    }

    payload_json = json.dumps(payload)

    script = """# Auto-generated by VideoAssistant
# Usage (Windows):
# 1) Start DaVinci Resolve.
# 2) Run this script with Resolve's scripting (external Python) OR paste into the Console.
#
# External Python note:
# This script will try to auto-add common Resolve scripting Modules paths.
# If external Python still can't import DaVinciResolveScript, ensure this folder exists:
#   C:/ProgramData/Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules/

from pathlib import Path
import json
import os
import sys

PAYLOAD = json.loads(r'''""" + payload_json + r"""''')


def add_resolve_modules_to_syspath():
    # Make external Python able to `import DaVinciResolveScript` on Windows.

    candidates = []
    for env_key in ['RESOLVE_SCRIPTING_MODULES', 'RESOLVE_SCRIPT_API']:
        env = os.environ.get(env_key)
        if env:
            candidates.append(env)

    candidates.extend([
        r"C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\Modules",
        r"C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\Modules",
    ])

    for p in candidates:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)


def get_resolve():
    add_resolve_modules_to_syspath()
    try:
        import DaVinciResolveScript as dvr
    except Exception as e:
        raise SystemExit(
            "Cannot import DaVinciResolveScript. Add Resolve scripting Modules path to sys.path.\n"
            + "Original error: "
            + str(e)
        )
    resolve = dvr.scriptapp('Resolve')
    if resolve is None:
        raise SystemExit(
            'Resolve scripting app not available.\n'
            '- Start DaVinci Resolve first, then re-run this script.\n'
            '- If Resolve is already running, try running this script as the same user.\n'
        )
    return resolve


def ensure_project(pm, project_name: str):
    proj = pm.LoadProject(project_name)
    if proj:
        return proj
    try:
        cur = pm.GetCurrentProject()
    except Exception:
        cur = None
    if cur:
        return cur
    proj = pm.CreateProject(project_name)
    if not proj:
        raise SystemExit('Failed to create project: ' + project_name)
    return proj


def ensure_bin(media_pool, parent, name: str):
    for b in parent.GetSubFolderList() or []:
        if b.GetName() == name:
            return b
    return media_pool.AddSubFolder(parent, name)


def _norm_path(p: str | None) -> str:
    if not p:
        return ""
    try:
        p = str(p)
    except Exception:
        return ""
    # Resolve often returns Windows paths with backslashes.
    return p.replace("/", "\\").strip().lower()


def import_or_find_media_item(media_pool, target_folder, clip_path: str, clip_name: str | None = None):
    # Import can return [] on reruns when media already exists in the pool.
    # In that case, find the existing MediaPoolItem by File Path in the target bin.
    try:
        items = media_pool.ImportMedia([clip_path])
    except Exception:
        items = None
    if items:
        try:
            return items[0]
        except Exception:
            pass

    want = _norm_path(clip_path)
    try:
        existing = target_folder.GetClipList() or []
    except Exception:
        existing = []

    for it in existing:
        try:
            props = it.GetClipProperty() or {}
        except Exception:
            props = {}
        fp = props.get('File Path') or props.get('FilePath') or props.get('Path')
        if fp and _norm_path(fp) == want:
            return it
        if clip_name:
            try:
                nm = props.get('Clip Name') or props.get('Name')
            except Exception:
                nm = None
            if nm and str(nm).strip() == str(clip_name).strip():
                # Fallback match (less reliable than file path).
                return it
    return None


def find_timeline_by_name(proj, name: str):
    try:
        count = int(proj.GetTimelineCount())
    except Exception:
        return None
    for i in range(1, count + 1):
        tl = proj.GetTimelineByIndex(i)
        if tl and tl.GetName() == name:
            return tl
    return None


def ensure_timeline(proj, media_pool, name: str):
    tl = find_timeline_by_name(proj, name)
    if tl:
        return tl
    # Resolve API naming can vary across versions; try a few.
    for fn in ['CreateEmptyTimeline', 'CreateTimeline']:
        try:
            create = getattr(media_pool, fn, None)
            if create:
                tl = create(name)
                if tl:
                    return tl
        except Exception:
            pass
    return find_timeline_by_name(proj, name)


def clear_timeline(tl):
    # Best-effort: remove all timeline items so re-running this script updates in-place.
    for track_type in ['video', 'audio']:
        try:
            n = int(tl.GetTrackCount(track_type) or 0)
        except Exception:
            n = 0
        for track_idx in range(1, n + 1):
            try:
                items = tl.GetItemListInTrack(track_type, track_idx) or []
            except Exception:
                items = []
            if not items:
                continue
            try:
                # Second argument: ripple delete (defaults False).
                tl.DeleteClips(items, False)
                continue
            except Exception:
                pass
            # Fallback: attempt per-item removal.
            for it in items:
                for fn in ['RemoveItem', 'RemoveClip']:
                    try:
                        rm = getattr(tl, fn, None)
                        if rm:
                            rm(it)
                            break
                    except Exception:
                        pass


def ensure_unique_timeline(proj, media_pool, base_name: str):
    # Generated timelines should be fully re-runnable.
    # Clearing can fail (especially when items have Fusion comps), leading to
    # duplicated clips and a "looping"/cheap feel. Deleting+recreating is more
    # reliable and keeps the name stable.
    tl = find_timeline_by_name(proj, base_name)
    if tl:
        try:
            # Best-effort: delete and recreate with the same name.
            media_pool.DeleteTimelines([tl])
        except Exception:
            try:
                clear_timeline(tl)
            except Exception:
                pass
    return ensure_timeline(proj, media_pool, base_name)


def recreate_timeline(proj, media_pool, name: str):
    # Some timelines can get into a state where AppendToTimeline silently fails
    # (returns [None]). When that happens, deleting and recreating the timeline
    # tends to restore normal behavior.
    try:
        tl_old = find_timeline_by_name(proj, name)
    except Exception:
        tl_old = None
    if tl_old:
        try:
            media_pool.DeleteTimelines([tl_old])
        except Exception:
            pass
    return ensure_timeline(proj, media_pool, name)


def load_speedramp_map(timeline_fps: float):
    # Optional: created by VideoAssistant `speedramps` step.
    # Mapping key: (rel, t_in, t_out) -> curve pieces.
    # Note: We deliberately key by seconds (rounded) instead of frames because
    # Resolve timelines are often 29.97/23.976, while our speedramp exports
    # commonly use 30.0fps for analysis/baking.
    try:
        plan_path = Path(__file__).resolve().parent / 'speedramps' / 'speedramp_plan.json'
    except Exception:
        plan_path = None
    if (not plan_path) or (not plan_path.is_file()):
        return {}
    try:
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    m = {}
    rooms = plan.get('rooms') or {}
    for _room, entries in rooms.items():
        for e in entries or []:
            try:
                rel = e.get('rel')
                t_in = float(e.get('t_in'))
                t_out = float(e.get('t_out'))
                curve = e.get('curve') or []
                if rel and curve:
                    m[(rel, round(t_in, 3), round(t_out, 3))] = curve
            except Exception:
                pass
    return m


def apply_fusion_speed_curve(ti, curve_pieces, fps: float, comp_name: str = 'VA_RAMP'):
    # Implements variable speed ramps via Fusion `TimeSpeed` node keyframes.
    # This avoids the Edit-page retime curve UI, which is not exposed by the public scripting API.
    try:
        existing_names = ti.GetFusionCompNameList() or []
    except Exception:
        existing_names = []

    try:
        if comp_name in existing_names:
            ti.DeleteFusionCompByName(comp_name)
    except Exception:
        pass

    comp = None
    try:
        before = set(ti.GetFusionCompNameList() or [])
    except Exception:
        before = set()
    try:
        comp = ti.AddFusionComp()
    except Exception:
        comp = None
    if not comp:
        return False
    try:
        after = set(ti.GetFusionCompNameList() or [])
        new_names = list(after - before)
        if new_names:
            ti.RenameFusionCompByName(new_names[0], comp_name)
    except Exception:
        pass

    # Find MediaIn/MediaOut
    try:
        tools = comp.GetToolList(False)
    except Exception:
        tools = {}
    media_in = None
    media_out = None
    for _k, t in (tools.items() if hasattr(tools, 'items') else []):
        try:
            reg = (t.GetAttrs() or {}).get('TOOLS_RegID')
        except Exception:
            reg = None
        if reg == 'MediaIn':
            media_in = t
        elif reg == 'MediaOut':
            media_out = t
    if (not media_in) or (not media_out):
        return False

    try:
        ts = comp.AddTool('TimeSpeed')
        ts.Input = media_in.Output
        media_out.Input = ts.Output

        # Default to crisp motion: disable interpolation (Nearest).
        # Blend/Flow can look like "motion blur" on real-estate walkthrough footage.
        # Since our ramps are intentionally subtle (close to 1.0x), Nearest is usually
        # the most professional default.
        try:
            ts.InterpolateBetweenFrames = 0
        except Exception:
            pass
        try:
            ts.SampleSpread = 0.0
        except Exception:
            pass

        # Best-effort: if Flow-related warp toggles exist, disable them.
        for k in [
            'EnableWarp.PrevForward',
            'EnableWarp.NextForward',
            'EnableWarp.PrevBackward',
            'EnableWarp.NextBackward',
        ]:
            try:
                ts[k] = 0
            except Exception:
                pass
    except Exception:
        return False

    # Keyframe Speed over time.
    last_speed = None
    last_t1 = None
    for piece in curve_pieces or []:
        try:
            t0 = float(piece.get('t0', 0.0))
            t1 = float(piece.get('t1', 0.0))
            sp = float(piece.get('speed', 1.0))
        except Exception:
            continue
        f0 = int(round(t0 * fps))
        try:
            ts.Speed[f0] = sp
        except Exception:
            try:
                ts.Speed = sp
            except Exception:
                pass
        last_speed = sp
        last_t1 = t1
    if last_speed is not None and last_t1 is not None:
        try:
            f1 = int(round(float(last_t1) * fps))
            ts.Speed[f1] = float(last_speed)
        except Exception:
            pass
    return True


def add_marker_to_item(item, frame_id: int, name: str, note: str, color: str = 'Blue'):
    try:
        item.AddMarker(frame_id, color, name, note, 1, '')
        return True
    except Exception:
        return False


def set_current_timeline(proj, tl, expected_name: str) -> bool:
    # Resolve can occasionally fail to switch timelines (especially when scripts
    # are re-run rapidly). If that happens, AppendToTimeline() can end up adding
    # clips to an unintended existing timeline (often a *_2 duplicate).
    try:
        proj.SetCurrentTimeline(tl)
    except Exception:
        pass

    try:
        cur = proj.GetCurrentTimeline()
        if cur and (cur.GetName() == expected_name):
            return True
    except Exception:
        pass

    # Fallback: look up by name and retry.
    try:
        cand = find_timeline_by_name(proj, expected_name)
    except Exception:
        cand = None
    if cand:
        try:
            proj.SetCurrentTimeline(cand)
        except Exception:
            pass
        try:
            cur = proj.GetCurrentTimeline()
            if cur and (cur.GetName() == expected_name):
                return True
        except Exception:
            pass
    return False


def main():
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    proj = ensure_project(pm, PAYLOAD['project_name'])
    media_pool = proj.GetMediaPool()
    root_folder = media_pool.GetRootFolder()

    # Use timeline fps for seconds->frame conversion.
    try:
        timeline_fps = float(proj.GetSetting('timelineFrameRate') or 30.0)
    except Exception:
        timeline_fps = 30.0

    speedramp_map = load_speedramp_map(timeline_fps)

    # Room-based organization
    rooms = set([c.get('room') for c in PAYLOAD['clips'] if c.get('room')])
    room_bins = {}
    for r in sorted(rooms):
        room_bins[r] = ensure_bin(media_pool, root_folder, r)

    rel_to_item = {}
    rel_to_sort = {}
    for clip in PAYLOAD['clips']:
        r = clip.get('room') or 'unknown'
        target_bin = room_bins.get(r, root_folder)
        media_pool.SetCurrentFolder(target_bin)
        it = import_or_find_media_item(media_pool, target_bin, clip['path'], clip.get('name'))
        if it:
            rel_to_item[clip['rel']] = it
        # Use modified time when available; fall back to name/rel for deterministic ordering.
        try:
            mtime = float(clip.get('mtime') or 0.0)
        except Exception:
            mtime = 0.0
        rel_to_sort[clip.get('rel')] = (mtime, (clip.get('name') or ''), (clip.get('rel') or ''))

    # Build timelines per room from *trimmed segments* (subclips).
    room_to_segments = {}
    selects_by_rel = PAYLOAD['selects']['clips']
    for clip in PAYLOAD['clips']:
        rel = clip['rel']
        info = selects_by_rel.get(rel)
        if not info or info.get('error'):
            continue
        room = info.get('room') or clip.get('room') or 'unknown'
        # Prefer chronological order within each clip.
        segs = info.get('segments', []) or []
        try:
            segs = sorted(segs, key=lambda s: float(s.get('t_in', 0.0)))
        except Exception:
            pass
        for seg in segs:
            room_to_segments.setdefault(room, []).append((rel, seg))

    def seg_sort_key(pair):
        rel, seg = pair
        base = rel_to_sort.get(rel, (0.0, '', rel))
        try:
            t_in = float(seg.get('t_in', 0.0))
        except Exception:
            t_in = 0.0
        return (base[0], base[1], base[2], t_in)

    for room in list(room_to_segments.keys()):
        try:
            room_to_segments[room].sort(key=seg_sort_key)
        except Exception:
            pass

    ordered = PAYLOAD.get('ordered_segments_by_room') or {}

    seq_mode = (PAYLOAD.get('sequence_mode') or '').lower()
    tl_suffix = '_SELECTS_CINE' if seq_mode in ['cinematic', 'cine', 'cinema'] else '_SELECTS'

    for room in sorted(room_to_segments.keys()):
        # Use a dedicated timeline name to avoid confusing "full clips" runs.
        tl_name = room.upper() + tl_suffix
        tl = ensure_unique_timeline(proj, media_pool, tl_name)
        if not tl:
            continue

        if not set_current_timeline(proj, tl, tl_name):
            # Avoid appending into some other current timeline.
            print(f"WARN: could not activate timeline {tl_name}; skipping")
            continue
        appended_meta = []  # (rel, t_in, t_out)
        if room in ordered and ordered[room]:
            seg_list = [(d.get('rel'), d) for d in (ordered.get(room) or [])]
        else:
            seg_list = room_to_segments[room]

        for rel, seg in seg_list:
            item = rel_to_item.get(rel)
            if not item:
                continue
            t_in = float(seg['t_in'])
            t_out = float(seg['t_out'])
            start_frame = int(round(t_in * timeline_fps))
            end_excl = int(round(t_out * timeline_fps))
            end_frame = end_excl - 1
            if end_frame < start_frame:
                end_frame = start_frame
            subclip = {
                'mediaPoolItem': item,
                'startFrame': start_frame,
                'endFrame': end_frame,
            }
            try:
                appended = media_pool.AppendToTimeline([subclip])

                # Resolve can silently fail to append into some timelines and return [None].
                # If this happens on an empty timeline, recreate the timeline and retry once.
                try:
                    bad_append = (
                        (not appended)
                        or (not isinstance(appended, list))
                        or (len(appended) > 0 and appended[0] is None)
                    )
                except Exception:
                    bad_append = False

                if bad_append:
                    try:
                        v1_now = tl.GetItemListInTrack('video', 1) or []
                    except Exception:
                        v1_now = []
                    if not v1_now:
                        try:
                            tl = recreate_timeline(proj, media_pool, tl_name)
                        except Exception:
                            tl = None
                        if tl and set_current_timeline(proj, tl, tl_name):
                            appended = media_pool.AppendToTimeline([subclip])
                # Finishing pass: apply slight horizon correction (roll) + safe crop zoom.
                # Note: official scripting docs do not list speed ramps/transitions; this script
                # keeps finishing conservative and sizing-only.
                if appended and isinstance(appended, list):
                    ti = appended[0]
                    try:
                        appended_meta.append((rel, float(t_in), float(t_out)))
                    except Exception:
                        appended_meta.append((rel, t_in, t_out))
                    try:
                        roll = seg.get('roll_deg', None)
                        if roll is not None:
                            roll = float(roll)
                        if roll is not None and abs(roll) >= 0.3:
                            ti.SetProperty('RotationAngle', -roll)

                            # Apply a small zoom to hide black corners after rotation.
                            # Resolve's Zoom units can vary (some builds report 1.0, others ~100).
                            try:
                                cur_zoom = ti.GetProperty('ZoomX')
                                cur_zoom = float(cur_zoom) if cur_zoom is not None else None
                            except Exception:
                                cur_zoom = None

                            # Approximate scale needed for small rotations.
                            import math
                            z = 1.0 / max(0.90, math.cos(abs(roll) * math.pi / 180.0))
                            z = min(1.10, max(1.01, z))
                            if cur_zoom is not None and cur_zoom > 10.0:
                                z_val = z * 100.0
                            else:
                                z_val = z
                            try:
                                ti.SetProperty('ZoomGang', True)
                                ti.SetProperty('ZoomX', z_val)
                                ti.SetProperty('ZoomY', z_val)
                            except Exception:
                                pass

                        # If this is a moving shot, prefer higher-quality retime processing.
                        # Note: This does not change speed by itself; it sets the algorithm used
                        # when retiming is applied in the UI.
                        try:
                            st = (seg.get('shot_type') or '').lower()
                            if st in ['walk', 'arc', 'pan', 'tilt', 'slow_pan', 'slow_tilt']:
                                # 3 = RETIME_OPTICAL_FLOW, 2 = MOTION_EST_STANDARD_BETTER
                                ti.SetProperty('RetimeProcess', 3)
                                ti.SetProperty('MotionEstimation', 2)
                        except Exception:
                            pass

                        # Annotate suggested speed ramp for this shot.
                        try:
                            ramp = seg.get('ramp') or {}
                            kind = ramp.get('kind')
                            s0 = ramp.get('start')
                            sm = ramp.get('mid')
                            s1 = ramp.get('end')
                            if kind and s0 and sm and s1:
                                note = f"{kind} start={float(s0):.2f} mid={float(sm):.2f} end={float(s1):.2f}"
                                # Marker frameId is clip-offset frames.
                                ti.AddMarker(0, 'Blue', 'RAMP', note, 1, '')
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass

        # Apply actual variable-speed ramps (Fusion comps) in a second pass.
        # This tends to be more reliable than attaching comps immediately after AppendToTimeline.
        try:
            if speedramp_map and appended_meta:
                try:
                    v1_items = tl.GetItemListInTrack('video', 1) or []
                except Exception:
                    v1_items = []

                want = 0
                ok = 0
                for idx, (rel, t_in, t_out) in enumerate(appended_meta):
                    if idx >= len(v1_items):
                        break
                    curve = speedramp_map.get((rel, round(float(t_in), 3), round(float(t_out), 3)))
                    if not curve:
                        continue
                    want += 1
                    ti = v1_items[idx]
                    applied = False
                    try:
                        applied = apply_fusion_speed_curve(ti, curve, timeline_fps, comp_name='VA_RAMP')
                    except Exception:
                        applied = False
                    if not applied:
                        # One small retry helps on some Resolve builds.
                        try:
                            import time

                            time.sleep(0.05)
                        except Exception:
                            pass
                        try:
                            applied = apply_fusion_speed_curve(ti, curve, timeline_fps, comp_name='VA_RAMP')
                        except Exception:
                            applied = False
                    if applied:
                        ok += 1

                if want:
                    print(f"{tl_name}: applied Fusion ramps {ok}/{want}")
        except Exception:
            pass
    for rel, info in PAYLOAD['selects']['clips'].items():
        item = rel_to_item.get(rel)
        if (not item) or info.get('error'):
            continue
        segs = info.get('segments', [])
        for i, seg in enumerate(segs, 1):
            t_in = float(seg['t_in'])
            t_out = float(seg['t_out'])
            f_in = int(round(t_in * timeline_fps))
            f_out = int(round(t_out * timeline_fps))
            score = seg.get('score')
            add_marker_to_item(item, f_in, 'SELECT %d IN' % i, 'score=%s' % score, 'Green')
            add_marker_to_item(item, f_out, 'SELECT %d OUT' % i, 'score=%s' % score, 'Red')

    print('Done. Imported media into room bins, created per-room timelines, and added markers to clips.')
    if seq_mode in ['cinematic', 'cine', 'cinema']:
        print('Use each room timeline (LIVING_ROOM_SELECTS_CINE, etc.) to review and export.')
    else:
        print('Use each room timeline (LIVING_ROOM_SELECTS, etc.) to review and export.')
    print('If markers are off by a bit, use selects.csv as the source of truth.')


if __name__ == '__main__':
    main()
"""

    path.write_text(script, encoding="utf-8")
