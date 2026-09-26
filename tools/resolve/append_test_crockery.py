from __future__ import annotations


def connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def find_timeline_by_name(proj, name: str):
    try:
        n = int(proj.GetTimelineCount() or 0)
    except Exception:
        n = 0
    for i in range(1, n + 1):
        tl = proj.GetTimelineByIndex(i)
        if tl and tl.GetName() == name:
            return tl
    return None


def norm(p: str) -> str:
    return str(p).replace("/", "\\").strip().lower()


def find_media_item_in_folder(folder, file_path: str):
    want = norm(file_path)
    try:
        clips = folder.GetClipList() or []
    except Exception:
        clips = []
    for it in clips:
        try:
            props = it.GetClipProperty() or {}
        except Exception:
            props = {}
        fp = props.get("File Path")
        if fp and norm(fp) == want:
            return it
    return None


def main() -> None:
    resolve = connect_resolve()
    proj = resolve.GetProjectManager().GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")
    mp = proj.GetMediaPool()
    root = mp.GetRootFolder()

    tl1 = find_timeline_by_name(proj, "CROCKERY_SELECTS_CINE")
    tl2 = find_timeline_by_name(proj, "CROCKERY_SELECTS_CINE_2")
    if not tl1:
        raise SystemExit("Missing CROCKERY_SELECTS_CINE")

    # Find the crockery bin
    crock = None
    for f in root.GetSubFolderList() or []:
        if f.GetName() == "crockery":
            crock = f
            break
    if not crock:
        raise SystemExit("No 'crockery' bin under root")

    path = r"C:\RA\Git\VideoAssistant\staging\C1601-Vertical-first20\.va\stabilized\crockery\A001_01181830_C389_03332450.mp4"
    it = find_media_item_in_folder(crock, path)
    if not it:
        # Try import into crockery bin
        mp.SetCurrentFolder(crock)
        imported = mp.ImportMedia([path])
        if imported:
            it = imported[0]
    if not it:
        raise SystemExit("Could not find/import media pool item for test clip")

    # Try to set current timeline and append one subclip
    ok = proj.SetCurrentTimeline(tl1)
    print("SetCurrentTimeline returned:", ok)
    try:
        cur = proj.GetCurrentTimeline()
        print("Current timeline:", cur.GetName() if cur else None)
    except Exception as e:
        print("GetCurrentTimeline failed:", e)

    # Append 1s..5s at 30fps
    fps = 30.0
    start_frame = int(round(1.0 * fps))
    end_frame = int(round(5.0 * fps)) - 1
    sub = {"mediaPoolItem": it, "startFrame": start_frame, "endFrame": end_frame}
    appended = mp.AppendToTimeline([sub])
    print("AppendToTimeline returned:", appended)

    def count_items(tl):
        if not tl:
            return None
        try:
            items = tl.GetItemListInTrack("video", 1) or []
        except Exception:
            items = []
        return len(items)

    print("CROCKERY_SELECTS_CINE V1 count:", count_items(tl1))
    print("CROCKERY_SELECTS_CINE_2 V1 count:", count_items(tl2))


if __name__ == "__main__":
    main()
