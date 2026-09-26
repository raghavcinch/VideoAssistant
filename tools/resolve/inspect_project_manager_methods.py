from __future__ import annotations

from _resolve_bootstrap import connect_resolve


def main() -> None:
    resolve = connect_resolve()
    pm = resolve.GetProjectManager()

    names = sorted(dir(pm))
    # Only print the interesting ones
    keys = [
        "copy",
        "dup",
        "export",
        "import",
        "archive",
        "load",
        "save",
        "project",
        "template",
    ]

    hits = []
    for n in names:
        nl = n.lower()
        if any(k in nl for k in keys):
            hits.append(n)

    print("ProjectManager interesting methods:")
    for n in hits:
        print(" ", n)


if __name__ == "__main__":
    main()
