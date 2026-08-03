#!/usr/bin/env python3
import json, os, sys, urllib.request, urllib.error

API_URL = os.getenv("RAG_API_URL", "http://localhost:8005")
USER_ID = "system-ingest-001"

# ── Tier-1 Corpus Manifest ────────────────────────────────────────────────────
# Add new transcript files here. Each entry maps to a .txt file in corpus/tier1/
# Required fields: filename, source_origin, author, country, sector, content_type
# Optional: figure_id, language, source_url, channel, video_date
DOCUMENTS = [
    # ── Continental Leaders ───────────────────────────────────────────────────
    {
        "filename": "dangote_principles.txt",
        "source_origin": "entrepreneur_corpus",
        "author": "Aliko Dangote",
        "figure_id": "dangote",
        "country": "NG",
        "sector": "manufacturing_trade",
        "content_type": "interview_transcript",
        "language": "en",
        "source_url": "",
        "channel": "Bloomberg Africa",
    },
    {
        "filename": "masiyiwa_resilience.txt",
        "source_origin": "entrepreneur_corpus",
        "author": "Strive Masiyiwa",
        "figure_id": "masiyiwa",
        "country": "ZW",
        "sector": "telecoms_technology",
        "content_type": "interview_transcript",
        "language": "en",
        "source_url": "",
        "channel": "WEF Davos",
    },
    {
        "filename": "elumelu_africapitalism.txt",
        "source_origin": "entrepreneur_corpus",
        "author": "Tony Elumelu",
        "figure_id": "elumelu",
        "country": "NG",
        "sector": "finance_investment",
        "content_type": "speech_transcript",
        "language": "en",
        "source_url": "",
        "channel": "Tony Elumelu Foundation",
    },
    # ── Financial Literacy ────────────────────────────────────────────────────
    {
        "filename": "africa_financial_literacy_guide.txt",
        "source_origin": "financial_literacy",
        "author": "AfriMentor Research Team",
        "figure_id": None,
        "country": "general",
        "sector": "financial_literacy",
        "content_type": "guide",
        "language": "en",
        "source_url": "",
        "channel": "",
    },
    # ── Trade Guides ──────────────────────────────────────────────────────────
    {
        "filename": "nigeria_trade_guide.txt",
        "source_origin": "trade_guide",
        "author": "AfriMentor Research Team",
        "figure_id": None,
        "country": "NG",
        "sector": "wholesale_trade",
        "content_type": "guide",
        "language": "en",
        "source_url": "",
        "channel": "",
    },
    # ── ADD NEW TRANSCRIPTS BELOW THIS LINE ───────────────────────────────────
    # Template:
    # {
    #     "filename": "vusi_thembekwayo_entrepreneurship.txt",
    #     "source_origin": "entrepreneur_corpus",
    #     "author": "Vusi Thembekwayo",
    #     "figure_id": "vusi_thembekwayo",
    #     "country": "ZA",
    #     "sector": "general_business",
    #     "content_type": "video_transcript",
    #     "language": "en",
    #     "source_url": "https://youtube.com/watch?v=XXXXX",
    #     "channel": "Vusi Thembekwayo",
    # },
]

def build_metadata(doc):
    return {
        "author":       doc.get("author", ""),
        "figure_id":    doc.get("figure_id") or "",
        "country":      doc.get("country", "general"),
        "sector":       doc.get("sector", "general_business"),
        "content_type": doc.get("content_type", "text"),
        "language":     doc.get("language", "en"),
        "source_url":   doc.get("source_url", ""),
        "channel":      doc.get("channel", ""),
    }

def ingest_document(doc):
    filepath = os.path.join("corpus", "tier1", doc["filename"])
    if not os.path.exists(filepath):
        print("  SKIP — file not found: " + filepath)
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        print("  SKIP — empty file: " + filepath)
        return {}

    payload = {
        "filename":      doc["filename"],
        "text":          text,
        "source_origin": doc["source_origin"],
        "figure_id":     doc.get("figure_id"),
        "market":        doc.get("country", "general"),
        "language":      doc.get("language", "en"),
        "extra_metadata": build_metadata(doc),
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL + "/api/v1/rag/documents",
        data=data,
        headers={"Content-Type": "application/json", "X-User-Id": USER_ID},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print("  ERROR " + str(e.code) + ": " + e.read().decode())
        return {}
    except Exception as e:
        print("  ERROR: " + str(e))
        return {}

def main():
    print("AfriMentor Tier-1 Corpus Ingestion")
    print("Target: " + API_URL)
    print()
    success = 0
    skip = 0
    for doc in DOCUMENTS:
        author = doc.get("author", doc["filename"])
        print("Ingesting: " + doc["filename"])
        print("  Author:  " + author)
        print("  Sector:  " + doc.get("sector", "—"))
        print("  Country: " + doc.get("country", "—"))
        result = ingest_document(doc)
        if result.get("status") == "ready":
            print("  OK — chunks=" + str(result["chunk_count"]) + "  id=" + result["id"])
            success += 1
        elif not result:
            skip += 1
        else:
            print("  WARN — status=" + str(result.get("status")) + "  error=" + str(result.get("error_message")))
        print()

    total = len(DOCUMENTS)
    print("=" * 50)
    print("Done: " + str(success) + " ingested / " + str(skip) + " skipped / " + str(total) + " total")
    sys.exit(0 if success + skip == total else 1)

if __name__ == "__main__":
    main()
