#!/usr/bin/env python3
import json, os, sys, urllib.request, urllib.error

API_URL      = os.getenv("RAG_API_URL", "http://127.0.0.1:8005")
USER_ID      = "system-ingest-001"
CORPUS_JSONL = "corpus/data/corpus.jsonl"

def map_source_origin(meta):
    sector = meta.get("primary_sector", "").lower()
    content_type = meta.get("content_type", "").lower()
    if "financial literacy" in sector:
        return "financial_literacy"
    if "trade" in sector or "retail" in sector or "wholesale" in sector:
        return "trade_guide"
    if "vocational" in sector or "education" in sector:
        return "vocational"
    return "entrepreneur_corpus"

def ingest_record(record):
    meta = record["metadata"]
    payload = {
        "filename":      record["doc_id"] + ".txt",
        "text":          record["content"],
        "source_origin": map_source_origin(meta),
        "figure_id":     meta.get("figure_id") or None,
        "market":        meta.get("country_code", "general"),
        "sector":        meta.get("primary_sector") or None,
        "content_type":  meta.get("content_type") or None,
        "language":      meta.get("language", "en"),
        # Catalogue metadata for the admin screen (card C2.2). The API coerces
        # empty strings to null, which matters here: url and date are blank in
        # 20 of the 21 Tier-1 records and channel is blank in 12.
        "title":          meta.get("title") or None,
        "author":         meta.get("speaker") or None,
        "published_date": meta.get("date") or None,
        "source_url":     meta.get("url") or None,
        "channel":        meta.get("channel") or None,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL + "/api/v1/rag/documents",
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-User-Id": USER_ID,
            # Ingest is admin-gated (card O3.5); when run directly against the
            # service (bypassing the gateway that injects roles) the loader must
            # assert the admin role itself, or every POST 403s.
            "X-User-Roles": "admin",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print("  ERROR " + str(e.code) + ": " + e.read().decode())
        return {}
    except Exception as e:
        print("  ERROR: " + str(e))
        return {}

def find_corpus_file():
    candidates = [
        os.getenv("CORPUS_JSONL", ""),
        "corpus/data/corpus.jsonl",
        "services/rag-corpus-service/corpus/data/corpus.jsonl",
        "/app/corpus/data/corpus.jsonl",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return "corpus/data/corpus.jsonl"


def main():
    corpus_file = find_corpus_file()
    if not os.path.exists(corpus_file):
        print("ERROR: " + corpus_file + " not found.")
        sys.exit(1)
    with open(corpus_file, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    print("AfriMentor RAG Corpus Ingestion")
    print("Target:  " + API_URL)
    print("Corpus:  " + corpus_file)
    print("Records: " + str(len(records)))
    print()
    success, failed = 0, 0
    for record in records:
        meta = record["metadata"]
        src = map_source_origin(meta)
        print("Ingesting: " + record["doc_id"])
        print("  Speaker:       " + meta.get("speaker", "-"))
        print("  Country:       " + meta.get("country", "-"))
        print("  Sector:        " + meta.get("primary_sector", "-"))
        print("  source_origin: " + src)
        result = ingest_record(record)
        if result.get("status") == "ready":
            print("  OK — chunks=" + str(result["chunk_count"]) + "  id=" + result["id"])
            success += 1
        else:
            err = result.get("error_message") or result.get("detail") or "Unknown error"
            print(f"  FAILED — {err}")
            failed += 1
        print()
    print("=" * 50)
    print("Done: " + str(success) + " ingested / " + str(failed) + " failed / " + str(len(records)) + " total")
    sys.exit(0 if success == len(records) else 1)


if __name__ == "__main__":
    main()