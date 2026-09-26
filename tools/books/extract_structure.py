from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT
from ebooklib import epub
from pypdf import PdfReader


@dataclass
class TocEntry:
    title: str
    page: int | None = None


def _safe_str(x: Any) -> str:
    try:
        s = str(x)
    except Exception:
        s = repr(x)
    return s.replace("\u0000", "").strip()


def extract_pdf_toc(pdf_path: Path, limit: int = 500) -> list[TocEntry]:
    reader = PdfReader(str(pdf_path))
    entries: list[TocEntry] = []

    outline = getattr(reader, "outline", None)
    if not outline:
        outline = getattr(reader, "outlines", None)

    def walk(node: Any) -> None:
        if len(entries) >= limit:
            return
        if isinstance(node, list):
            for it in node:
                walk(it)
            return

        title = None
        page_num = None
        try:
            title = getattr(node, "title", None)
        except Exception:
            title = None

        if title is None:
            try:
                title = node.get("/Title")  # type: ignore[attr-defined]
            except Exception:
                title = None

        try:
            # May raise if destination unsupported.
            page_num = reader.get_destination_page_number(node) + 1  # 1-based
        except Exception:
            page_num = None

        if title:
            entries.append(TocEntry(title=_safe_str(title), page=page_num))

        # Nested outline items
        try:
            kids = getattr(node, "children", None)
        except Exception:
            kids = None
        if kids:
            walk(list(kids))

    try:
        walk(outline)
    except Exception:
        return entries

    # De-dupe consecutive duplicates
    deduped: list[TocEntry] = []
    for e in entries:
        if deduped and deduped[-1].title == e.title and deduped[-1].page == e.page:
            continue
        deduped.append(e)
    return deduped


def _extract_pdf_toc_from_contents_pages(reader: PdfReader, max_pages: int = 25, limit: int = 300) -> list[TocEntry]:
    """Fallback TOC extraction.

    Many PDFs don't include outlines. We scan early pages for a 'contents' section and
    collect TOC-looking lines only (short lines ending with a page number).
    """

    def is_contents_page(text: str) -> bool:
        t = text.lower()
        return "table of contents" in t or ("contents" in t and "chapter" in t)

    def parse_line(line: str) -> TocEntry | None:
        raw = " ".join(line.strip().split())
        if not raw:
            return None
        if len(raw) > 160:
            return None
        # Common TOC line patterns: "Title .... 12" or "Title 12"
        # Grab last token if it is a small integer.
        parts = raw.replace("·", ".").split()
        if not parts:
            return None
        last = parts[-1]
        if not last.isdigit():
            return None
        page = int(last)
        if page <= 0 or page > 5000:
            return None
        title = raw[: raw.rfind(last)].rstrip(" .·\t")
        title = title.replace(" . . . ", " ").strip(" .")
        if not title:
            return None
        return TocEntry(title=title, page=page)

    collected: list[TocEntry] = []
    contents_mode = False
    for i in range(min(max_pages, len(reader.pages))):
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception:
            text = ""
        if not text:
            continue
        text_norm = "\n".join([" ".join(ln.split()) for ln in text.splitlines() if ln.strip()])
        if not contents_mode and is_contents_page(text_norm):
            contents_mode = True

        if not contents_mode:
            continue

        for line in text.splitlines():
            if len(collected) >= limit:
                break
            entry = parse_line(line)
            if entry:
                collected.append(entry)
        if len(collected) >= limit:
            break

        # Stop if we already have a decent number and the page no longer looks like TOC.
        if len(collected) >= 40 and ("chapter" not in text_norm.lower()) and ("contents" not in text_norm.lower()):
            break

    # De-dupe
    deduped: list[TocEntry] = []
    seen = set()
    for e in collected:
        key = (e.title.lower(), e.page)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    return deduped


def extract_epub_headings(epub_path: Path, limit: int = 500) -> list[str]:
    book = epub.read_epub(str(epub_path))
    headings: list[str] = []

    def add_heading(text: str) -> None:
        t = _safe_str(text)
        if not t:
            return
        if len(t) > 200:
            t = t[:200] + "…"
        if headings and headings[-1] == t:
            return
        headings.append(t)

    # Prefer nav/toc items
    try:
        toc = book.toc
    except Exception:
        toc = []

    def walk_toc(node: Any) -> None:
        if len(headings) >= limit:
            return
        if isinstance(node, (list, tuple)):
            for it in node:
                walk_toc(it)
            return
        title = getattr(node, "title", None)
        if title:
            add_heading(title)
        try:
            subitems = getattr(node, "subitems", None)
        except Exception:
            subitems = None
        if subitems:
            walk_toc(subitems)

    try:
        walk_toc(toc)
    except Exception:
        pass

    # Fallback: scan html items for h1/h2
    if not headings:
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            if len(headings) >= limit:
                break
            try:
                soup = BeautifulSoup(item.get_content(), "lxml")
                for tag in soup.find_all(["h1", "h2"]):
                    add_heading(tag.get_text(" ", strip=True))
                    if len(headings) >= limit:
                        break
            except Exception:
                continue

    return headings


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    books_dir = root / "Editing-Books"
    out_path = root / "docs" / "editing_books_structure.json"

    result: dict[str, Any] = {
        "note": (
            "This file intentionally stores only high-level structure (outlines/headings) "
            "so the repo does not contain copyrighted book text."
        ),
        "books": [],
    }

    for p in sorted(books_dir.glob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        item: dict[str, Any] = {"file": p.name, "ext": ext}
        if ext == ".pdf":
            toc = extract_pdf_toc(p)
            if len(toc) < 3:
                try:
                    reader = PdfReader(str(p))
                    toc = _extract_pdf_toc_from_contents_pages(reader)
                except Exception:
                    pass
            item["toc"] = [e.__dict__ for e in toc]
        elif ext == ".epub":
            item["headings"] = extract_epub_headings(p)
        else:
            continue
        result["books"].append(item)

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
