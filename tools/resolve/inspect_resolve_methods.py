from __future__ import annotations


def connect_resolve():
    from _resolve_bootstrap import connect_resolve as _cr

    return _cr()


def main() -> None:
    resolve = connect_resolve()
    names = sorted([n for n in dir(resolve) if any(s in n.lower() for s in ["pref", "config", "setting"])])
    print("Resolve methods:")
    for n in names:
        print(" ", n)


if __name__ == "__main__":
    main()
