from __future__ import annotations


def connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def main() -> None:
    resolve = connect_resolve()
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    if not proj:
        raise SystemExit("No current project")

    print("Project:", proj.GetName())

    # Show setting-related methods.
    methods = sorted([n for n in dir(proj) if "setting" in n.lower()])
    print("Setting methods:", methods)

    get_setting = getattr(proj, "GetSetting", None)
    if not callable(get_setting):
        raise SystemExit("Project has no GetSetting")

    # Try best-effort: some APIs accept no args and return a dict.
    settings = None
    try:
        settings = get_setting()  # type: ignore[call-arg]
    except TypeError:
        settings = None

    if isinstance(settings, dict) and settings:
        keys = sorted([str(k) for k in settings.keys()])
        print(f"Settings keys: {len(keys)}")
        for k in keys:
            if "stabil" in k.lower() or "gyro" in k.lower() or "camera" in k.lower() or "smooth" in k.lower():
                print(f"  {k}: {settings.get(k)}")
        return

    # Fallback: brute some likely keys.
    candidate_keys = [
        "stabilizationMode",
        "stabilizationmode",
        "stabilization_mode",
        "stabilizerMode",
        "stabilizer_mode",
        "stabilizer",
        "stabilization",
        "gyroStabilization",
    ]
    for k in candidate_keys:
        try:
            v = get_setting(k)
        except Exception as e:
            v = f"EXC: {e}"
        print(f"GetSetting({k!r}) -> {v}")


if __name__ == "__main__":
    main()
