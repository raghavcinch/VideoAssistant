from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import BinaryIO, Iterable, Optional


def _u32(b: bytes) -> int:
    return struct.unpack(">I", b)[0]


def _u64(b: bytes) -> int:
    return struct.unpack(">Q", b)[0]


@dataclass
class Box:
    start: int
    size: int
    typ: str
    header_size: int

    @property
    def end(self) -> int:
        return self.start + self.size

    @property
    def data_start(self) -> int:
        return self.start + self.header_size


def iter_boxes(f: BinaryIO, start: int, end: int) -> Iterable[Box]:
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        hdr = f.read(8)
        if len(hdr) < 8:
            return

        size = _u32(hdr[:4])
        typ = hdr[4:8].decode("latin-1", errors="replace")
        header_size = 8

        if size == 0:
            size = end - pos
        elif size == 1:
            ext = f.read(8)
            if len(ext) < 8:
                return
            size = _u64(ext)
            header_size = 16

        if size < header_size or pos + size > end:
            return

        yield Box(start=pos, size=size, typ=typ, header_size=header_size)
        pos += size


def find_child(f: BinaryIO, parent: Box, child_typ: str) -> Optional[Box]:
    for b in iter_boxes(f, parent.data_start, parent.end):
        if b.typ == child_typ:
            return b
    return None


def _looks_like_box_header(buf: bytes) -> bool:
    if len(buf) < 8:
        return False
    size = _u32(buf[:4])
    typ = buf[4:8]
    if size < 8:
        return False
    # Heuristic: type bytes should be printable-ish ASCII
    return all(32 <= b <= 126 for b in typ)


def meta_children_start(f: BinaryIO, meta: Box) -> int:
    """Return best-guess offset to the first child box inside a 'meta' box."""
    candidates = [meta.data_start, meta.data_start + 4]
    # Prefer offsets where the first child looks like a known metadata child.
    preferred_types = {b"hdlr", b"keys", b"ilst", b"iinf", b"iloc", b"dinf", b"iprp"}
    for off in candidates:
        if off + 8 > meta.end:
            continue
        f.seek(off)
        hdr = f.read(8)
        if not _looks_like_box_header(hdr):
            continue
        typ = hdr[4:8]
        if typ in preferred_types:
            return off
    # Fall back to whichever candidate looks like a box header.
    for off in candidates:
        if off + 8 > meta.end:
            continue
        f.seek(off)
        hdr = f.read(8)
        if _looks_like_box_header(hdr):
            return off
    # Last resort: assume FullBox layout.
    return meta.data_start + 4


def iter_meta_children(f: BinaryIO, meta: Box) -> Iterable[Box]:
    start = meta_children_start(f, meta)
    if start > meta.end:
        return []
    return iter_boxes(f, start, meta.end)


def parse_keys_box(f: BinaryIO, keys: Box, limit: int = 200) -> list[str]:
    # keys is a FullBox.
    f.seek(keys.data_start)
    header = f.read(8)
    if len(header) < 8:
        return []
    entry_count = _u32(header[4:8])

    pos = keys.data_start + 8
    out: list[str] = []
    for _ in range(min(entry_count, limit)):
        f.seek(pos)
        ent_hdr = f.read(8)
        if len(ent_hdr) < 8:
            break
        ent_size = _u32(ent_hdr[:4])
        namespace = ent_hdr[4:8].decode("latin-1", errors="replace")
        if ent_size < 8:
            break
        f.seek(pos + 8)
        key_bytes = f.read(ent_size - 8)
        key_str = key_bytes.decode("utf-8", errors="replace")
        out.append(f"{namespace}:{key_str}")
        pos += ent_size
        if pos >= keys.end:
            break
    return out


def parse_hdlr_handler_type(f: BinaryIO, hdlr: Box) -> Optional[str]:
    # FullBox: version/flags (4), pre_defined (4), handler_type (4)
    f.seek(hdlr.data_start)
    data = f.read(min(32, hdlr.size - hdlr.header_size))
    if len(data) < 12:
        return None
    return data[8:12].decode("latin-1", errors="replace")


def parse_stsd_sample_entry_types(f: BinaryIO, stsd: Box, limit: int = 5) -> list[str]:
    # stsd: FullBox header (4) + entry_count (4), then sample entries
    f.seek(stsd.data_start)
    header = f.read(8)
    if len(header) < 8:
        return []
    entry_count = _u32(header[4:8])
    types: list[str] = []

    pos = stsd.data_start + 8
    for _ in range(min(entry_count, limit)):
        f.seek(pos)
        ent = f.read(8)
        if len(ent) < 8:
            break
        ent_size = _u32(ent[:4])
        ent_typ = ent[4:8].decode("latin-1", errors="replace")
        types.append(ent_typ)
        if ent_size < 8:
            break
        pos += ent_size
        if pos >= stsd.end:
            break

    return types


def scan_for_strings(path: str, needles: list[bytes]) -> dict[str, int]:
    counts = {n: 0 for n in needles}
    max_len = max(len(n) for n in needles)
    buf_size = 1024 * 1024

    with open(path, "rb") as fh:
        prev = b""
        while True:
            chunk = fh.read(buf_size)
            if not chunk:
                break
            data = prev + chunk
            for n in needles:
                counts[n] += data.count(n)
            prev = data[-(max_len - 1) :] if max_len > 1 else b""

    return {k.decode("latin-1"): v for k, v in counts.items() if v}


def inspect(path: str) -> int:
    if not os.path.exists(path):
        print(f"ERROR: file not found: {path}")
        return 2

    size = os.path.getsize(path)
    print(f"File: {os.path.abspath(path)}")
    print(f"Size: {size/1024/1024:.1f} MiB")

    with open(path, "rb") as f:
        top = list(iter_boxes(f, 0, size))
        print("Top-level boxes:", ", ".join(b.typ for b in top))

        moov = next((b for b in top if b.typ == "moov"), None)
        if not moov:
            print("No 'moov' box found; cannot inspect tracks.")
            return 1

        traks = [b for b in iter_boxes(f, moov.data_start, moov.end) if b.typ == "trak"]
        print(f"Tracks found: {len(traks)}")

        for idx, trak in enumerate(traks, 1):
            mdia = find_child(f, trak, "mdia")
            if not mdia:
                print(f"  Track {idx}: (no mdia)")
                continue

            hdlr = next((b for b in iter_boxes(f, mdia.data_start, mdia.end) if b.typ == "hdlr"), None)
            handler = parse_hdlr_handler_type(f, hdlr) if hdlr else None

            minf = find_child(f, mdia, "minf")
            stsd = None
            if minf:
                stbl = find_child(f, minf, "stbl")
                if stbl:
                    stsd = find_child(f, stbl, "stsd")

            entries = parse_stsd_sample_entry_types(f, stsd) if stsd else []
            print(f"  Track {idx}: handler={handler} sample_entries={entries}")

        moov_children = [b.typ for b in iter_boxes(f, moov.data_start, moov.end)]
        interesting = sorted({t for t in moov_children if t in {"udta", "meta", "uuid", "mvex"}})
        print("Interesting 'moov' children:", interesting or "(none)")

        meta = next((b for b in iter_boxes(f, moov.data_start, moov.end) if b.typ == "meta"), None)
        if meta:
            start = meta_children_start(f, meta)
            f.seek(start)
            peek = f.read(16)
            print(f"meta child start offset guess: {start - meta.start} bytes into meta")
            print("meta child peek:", peek.hex(" "))

            meta_children = [b.typ for b in iter_meta_children(f, meta)]
            print("meta children:", meta_children or "(none)")
            keys = next((b for b in iter_meta_children(f, meta) if b.typ == "keys"), None)
            if keys:
                key_list = parse_keys_box(f, keys)
                print(f"meta/keys entries: {len(key_list)}")
                interesting_keys = [
                    k
                    for k in key_list
                    if any(s in k.lower() for s in ["gyro", "imu", "motion", "accel", "acce", "stabil"])
                ]
                if interesting_keys:
                    print("gyro/IMU-related keys (names only):")
                    for k in interesting_keys[:50]:
                        print(f"  - {k}")
                else:
                    print("gyro/IMU-related keys (names only): (none found)")

    needles = [
        b"gyro", b"GYRO", b"GPMF", b"gpmd", b"camm", b"IMU", b"acce", b"ACCL",
        b"Blackmagic", b"blackmagic", b"bmd", b"com.blackmagic",
    ]
    hits = scan_for_strings(path, needles)
    print("String hits (rough scan):", hits or "(none)")

    print("\nInterpretation:")
    print("- If you see ONLY handler=vide and handler=soun tracks, there is likely NO embedded gyro time-series.")
    print("- If you see a track with handler=meta (or 'data') and unusual sample_entries, there MAY be timed metadata to investigate further.")
    print("- A plain 'moov/meta' box often contains static tags (camera/app info); that alone usually isn't enough for gyro-based stabilization.")

    return 0


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else r"samples\\A001_12201705_C385.mov"
    raise SystemExit(inspect(target))
