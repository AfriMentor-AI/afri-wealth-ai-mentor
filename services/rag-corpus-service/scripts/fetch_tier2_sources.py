#!/usr/bin/env python3
"""Fetch and/or extract Tier-2 source documents to plain text (card C3.4).

Reads ``corpus/tier2/sources.json`` and, for each active source, produces
``corpus/tier2/raw/<id>/<id>.txt`` for ``scripts/ingest_tier2.py`` to ingest.

Two ways text gets produced, checked in this order:

  1. LOCAL FILE (preferred, reliable) — if you drop the report into the source's
     folder yourself, e.g. ``corpus/tier2/raw/tier2_afdb_jobs_for_youth_strategy/
     report.pdf``, this script extracts *that* file. No network needed. This is
     the intended path: publisher URLs are often landing/listing pages or block
     automated clients, whereas the actual PDF on your device always works.

  2. DOWNLOAD (fallback) — if the folder has no local ``.pdf``/``.html`` original,
     the source's ``url`` is fetched. Best effort: government/NGO sites rate-limit
     or 403 automated clients, so expect some to fail. Failures are reported per
     source and never abort the run.

PDFs are extracted with ``pypdf``; HTML is reduced to visible text with a stdlib
parser. Scanned/image-only PDFs yield little text (no OCR here) — flagged so you
can hand-extract instead.

    pip install pypdf                          # one-time (PDF extraction)
    python scripts/fetch_tier2_sources.py      # all active sources
    python scripts/fetch_tier2_sources.py --only tier2_afdb_jobs_for_youth_strategy
    python scripts/fetch_tier2_sources.py --force   # re-extract even if <id>.txt exists

An existing ``<id>.txt`` is kept unless ``--force`` is given, so a hand-corrected
extraction is never clobbered by a re-run.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from io import BytesIO

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE_ROOT = os.path.dirname(HERE)
TIER2_DIR = os.path.join(SERVICE_ROOT, "corpus", "tier2")
SOURCES_JSON = os.path.join(TIER2_DIR, "sources.json")
RAW_DIR = os.path.join(TIER2_DIR, "raw")

# Some publisher hosts 403 the default urllib agent; present a browser-like one.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
MAX_BYTES = 60 * 1024 * 1024  # guardrail against a runaway download
# A usable extraction should clear this; below it we warn (likely a scanned PDF,
# a cookie wall, or a landing page rather than the report itself).
MIN_USEFUL_CHARS = 500


class _TextExtractingParser(HTMLParser):
    """Collect visible text, dropping script/style/head-noise and collapsing runs."""

    _SKIP = {"script", "style", "noscript", "head", "meta", "link", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "\n".join(self._chunks)).strip()


def extract_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf not installed — run: pip install pypdf") from None
    reader = PdfReader(BytesIO(raw))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")  # one bad page shouldn't lose the rest
    return re.sub(r"\n{3,}", "\n\n", "\n".join(pages)).strip()


def extract_html(raw: bytes) -> str:
    parser = _TextExtractingParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return parser.text()


def extract(raw: bytes, hint: str) -> str:
    """Dispatch by content: PDF magic bytes win, else fall back to the name hint."""
    if raw[:5] == b"%PDF-" or hint.lower().endswith(".pdf"):
        return extract_pdf(raw)
    return extract_html(raw)


def find_local_original(src_dir: str) -> str | None:
    """A user-dropped (or previously downloaded) .pdf/.html to extract from."""
    if not os.path.isdir(src_dir):
        return None
    for name in sorted(os.listdir(src_dir)):
        if name.startswith("."):
            continue
        if name.lower().endswith((".pdf", ".html", ".htm")):
            return os.path.join(src_dir, name)
    return None


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read(MAX_BYTES + 1)


def process(source: dict, force: bool) -> str:
    """Return one of: 'extracted', 'kept', 'failed', 'empty'. Prints its own log."""
    source_id = source["id"]
    src_dir = os.path.join(RAW_DIR, source_id)
    os.makedirs(src_dir, exist_ok=True)
    out_path = os.path.join(src_dir, source_id + ".txt")

    if os.path.exists(out_path) and not force:
        print("  KEPT — " + source_id + ".txt already exists (use --force to redo)")
        return "kept"

    local = find_local_original(src_dir)
    try:
        if local:
            print("  local:  " + os.path.basename(local))
            with open(local, "rb") as f:
                raw = f.read()
            hint = local
        else:
            url = source.get("url")
            if not url:
                print("  FAILED — no local file and no url")
                return "failed"
            print("  GET:    " + url)
            raw = download(url)
            if len(raw) > MAX_BYTES:
                print(f"  FAILED — response exceeds {MAX_BYTES // 1024 // 1024} MB cap")
                return "failed"
            hint = url
        text = extract(raw, hint)
    except Exception as e:
        print("  FAILED — " + str(e))
        return "failed"

    if not text:
        print("  EMPTY — no text extracted (scanned PDF or blocked page?)")
        return "empty"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    note = "" if len(text) >= MIN_USEFUL_CHARS else "  (WARN: very short — check the source)"
    print("  OK — wrote " + source_id + ".txt (" + str(len(text)) + " chars)" + note)
    return "extracted"


def main() -> None:
    force = "--force" in sys.argv
    only = None
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        if i + 1 < len(sys.argv):
            only = sys.argv[i + 1]

    if not os.path.exists(SOURCES_JSON):
        print("ERROR: " + SOURCES_JSON + " not found.")
        sys.exit(1)
    with open(SOURCES_JSON, encoding="utf-8") as f:
        sources = json.load(f)

    active = [s for s in sources if s.get("status", "active") == "active"]
    if only:
        active = [s for s in active if s["id"] == only]
        if not active:
            print("ERROR: no active source with id " + only)
            sys.exit(1)

    print("AfriMentor RAG — Tier-2 Fetch/Extract")
    print("Sources: " + str(len(active)))
    print()

    counts = {"extracted": 0, "kept": 0, "failed": 0, "empty": 0}
    for source in active:
        print(source["id"])
        counts[process(source, force)] += 1
        print()

    print("=" * 55)
    print(
        f"Done: {counts['extracted']} extracted / {counts['kept']} kept / "
        f"{counts['empty']} empty / {counts['failed']} failed"
    )
    print("Next: python scripts/ingest_tier2.py")
    sys.exit(1 if counts["failed"] or counts["empty"] else 0)


if __name__ == "__main__":
    main()
