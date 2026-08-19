#!/usr/bin/env python3
"""Ingest Tier-2 reference reports into the RAG corpus (card C3.4).

Tier-2 sources are declared in ``corpus/tier2/sources.json`` — a small registry
(id, title, publisher, country, sector, url, cadence, status). Their extracted
plain text lives under ``corpus/tier2/raw/<id>/`` as one or more ``.txt``/``.md``
files, produced by ``scripts/fetch_tier2_sources.py`` (or dropped in by hand).

For each active source this POSTs to the RAG ingest endpoint with:
  - ``tier=2``                  → tags the document and every chunk as Tier-2, so
                                  retrieval and the admin catalogue can scope it.
  - ``external_id=<source id>`` → idempotent **upsert**: re-running replaces the
                                  same row and its vectors instead of minting a
                                  fresh UUID and orphaning the old chunks. That is
                                  what makes the Tier-2 refresh cadence
                                  (annual/triennial) safe to re-run.

Sources whose ``raw/<id>/`` dir has no extracted text yet are skipped with a
notice (not counted as failures), so the loader is runnable before every report
has been fetched.

    python scripts/ingest_tier2.py

Env:
  RAG_API_URL   base url of the RAG corpus service (default http://localhost:8005)
"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE_ROOT = os.path.dirname(HERE)
TIER2_DIR = os.path.join(SERVICE_ROOT, "corpus", "tier2")
SOURCES_JSON = os.path.join(TIER2_DIR, "sources.json")
RAW_DIR = os.path.join(TIER2_DIR, "raw")

API_URL = os.getenv("RAG_API_URL", "http://localhost:8005")
USER_ID = "system-ingest-001"

# Tier-2 reports are continental unless a single country is named. ``market`` is
# a String(10); we store ISO-3166 alpha-2 for single-country sources and "AFR"
# for pan-African scope so /stats by_country stays legible instead of carrying a
# free-text "Pan-Africa".
COUNTRY_CODES = {
    "nigeria": "NG",
    "ghana": "GH",
    "kenya": "KE",
    "south africa": "ZA",
    "ethiopia": "ET",
    "senegal": "SN",
    "zimbabwe": "ZW",
    "pan-africa": "AFR",
}


def market_code(country: str | None) -> str:
    return COUNTRY_CODES.get((country or "").strip().lower(), "AFR")


def read_extracted_text(source_id: str) -> str:
    """Concatenate every ``.txt``/``.md`` file under ``raw/<id>/`` (sorted).

    Returns "" when the dir is missing or holds no extracted text yet — the
    caller treats that as "not fetched", not as an error. The original
    downloaded ``.pdf``/``.html`` (if any) is ignored: only extracted text is
    ingested.
    """
    src_dir = os.path.join(RAW_DIR, source_id)
    if not os.path.isdir(src_dir):
        return ""
    parts = []
    for name in sorted(os.listdir(src_dir)):
        if name.startswith(".") or not name.lower().endswith((".txt", ".md")):
            continue
        with open(os.path.join(src_dir, name), encoding="utf-8", errors="replace") as f:
            parts.append(f.read().strip())
    return "\n\n".join(p for p in parts if p).strip()


def ingest_source(source: dict, text: str) -> dict:
    payload = {
        "filename": source["id"] + ".txt",
        "text": text,
        # Reference reports don't fit the entrepreneur/trade/finance/vocational
        # origins; "general" is the catch-all. Tier is the real discriminator.
        "source_origin": "general",
        "market": market_code(source.get("country")),
        "sector": source.get("sector") or None,
        "content_type": "reference_report",
        "language": "en",
        "tier": 2,
        "external_id": source["id"],
        "title": source.get("title") or None,
        "author": source.get("publisher") or None,
        "source_url": source.get("url") or None,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL + "/api/v1/rag/documents",
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-User-Id": USER_ID,
            # Ingest is admin-gated (card O3.5). Talking straight to the service
            # bypasses the gateway that would otherwise inject verified roles, so
            # the loader has to assert the admin role itself.
            "X-User-Roles": "admin",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print("  ERROR " + str(e.code) + ": " + e.read().decode(errors="replace"))
        return {}
    except Exception as e:
        print("  ERROR: " + str(e))
        return {}


def main() -> None:
    if not os.path.exists(SOURCES_JSON):
        print("ERROR: " + SOURCES_JSON + " not found.")
        sys.exit(1)
    with open(SOURCES_JSON, encoding="utf-8") as f:
        sources = json.load(f)
    active = [s for s in sources if s.get("status", "active") == "active"]

    print("AfriMentor RAG — Tier-2 Ingestion")
    print("Target:  " + API_URL)
    print("Sources: " + str(len(active)) + " active / " + str(len(sources)) + " total")
    print()

    success, failed, skipped = 0, 0, 0
    for source in active:
        print("Ingesting: " + source["id"])
        print("  Title:     " + source.get("title", "-"))
        print("  Publisher: " + source.get("publisher", "-"))
        text = read_extracted_text(source["id"])
        if not text:
            print("  SKIP — no extracted text in corpus/tier2/raw/" + source["id"] + "/ yet")
            print("         run: python scripts/fetch_tier2_sources.py")
            skipped += 1
            print()
            continue
        print("  Bytes:     " + str(len(text.encode("utf-8"))))
        result = ingest_source(source, text)
        if result.get("status") == "ready":
            print("  OK — chunks=" + str(result["chunk_count"]) + "  id=" + result["id"])
            success += 1
        else:
            failed += 1
        print()

    print("=" * 55)
    print(
        "Done: " + str(success) + " ingested / " + str(failed) + " failed / "
        + str(skipped) + " skipped / " + str(len(active)) + " active"
    )
    # Exit non-zero only on real failures. "Skipped" means not-yet-fetched, which
    # is an expected intermediate state, not a build failure.
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
