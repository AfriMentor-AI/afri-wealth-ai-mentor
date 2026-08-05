#!/usr/bin/env python3
import json, os, sys, urllib.request, urllib.error

API_URL      = os.getenv("RAG_API_URL", "http://localhost:8005")
USER_ID      = "system-ingest-001"
CORPUS_JSONL = "corpus/data/corpus.jsonl"

def ingest_record(record):
    meta = record["metadata"]
    payload = {
        "filename":      record["doc_id"] + ".txt",
        "text":          record["content"],
        "source_origin": meta.get("content_type", "video_transcript"),
        "figure_id":     meta.get("figure_id") or None,
        "market":        meta.get("country_code", "general"),
        "language":      meta.get("language", "en"),
    }
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
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
    if not os.path.exists(CORPUS_JSONL):
        print("ERROR: " + CORPUS_JSONL + " not found.")
        sys.exit(1)

    with open(CORPUS_JSONL, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    print("AfriMentor RAG Corpus Ingestion")
    print("Target:  " + API_URL)
    print("Records: " + str(len(records)))
    print()

    success, failed = 0, 0
    for record in records:
        meta = record["metadata"]
        print("Ingesting: " + record["doc_id"])
        print("  Speaker: " + meta.get("speaker", "-"))
        print("  Country: " + meta.get("country", "-"))
        print("  Sector:  " + meta.get("primary_sector", "-"))

        result = ingest_record(record)
        if result.get("status") == "ready":
            print("  OK — chunks=" + str(result["chunk_count"]) + "  id=" + result["id"])
            success += 1
        elif result.get("status") == "failed":
            print("  FAILED — " + str(result.get("error_message")))
            failed += 1
        else:
            failed += 1
        print()

    print("=" * 50)
    print("Done: " + str(success) + " ingested / " + str(failed) + " failed / " + str(len(records)) + " total")
    sys.exit(0 if success == len(records) else 1)

if __name__ == "__main__":
    main()
