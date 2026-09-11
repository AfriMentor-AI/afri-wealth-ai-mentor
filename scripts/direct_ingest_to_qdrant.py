#!/usr/bin/env python3
"""
Direct Host-Side Ingestion for AfriMentor RAG Tier-1 Corpus.
Runs on the host Python environment using cached ONNX embeddings and
writes points directly to Qdrant Cloud.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

# Configuration
QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "https://1f8cc189-f88c-4f04-84e5-3bf54f5face0.us-west-2-0.aws.cloud.qdrant.io",
).rstrip("/")
QDRANT_API_KEY = os.getenv(
    "QDRANT_API_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6OWQ4YTAyMDMtZTdhNy00ODNjLWFlZDktNWE2ZDc0OTBkNGRiIn0.Kh0SNa9hjyxZKno7--yUM7SIHAGL1HkrBjPxa_uN9Pc",
)
COLLECTION_NAME = "afrimentor_corpus"
CORPUS_PATH = os.path.join("services", "rag-corpus-service", "corpus", "data", "corpus.jsonl")

CHUNK_SIZE = 600
CHUNK_OVERLAP = 80
_SECTOR_SPLIT_RE = re.compile(r"[&/,]| and ")


def normalize_sector(sector: str | None) -> str:
    if not sector:
        return ""
    parts = [p.strip().lower().replace(" ", "_") for p in _SECTOR_SPLIT_RE.split(sector)]
    return ",".join(p for p in parts if p)


def map_source_origin(meta: dict) -> str:
    sector = meta.get("primary_sector", "").lower()
    if "financial literacy" in sector:
        return "financial_literacy"
    if "trade" in sector or "retail" in sector or "wholesale" in sector:
        return "trade_guide"
    if "vocational" in sector or "education" in sector:
        return "vocational"
    return "entrepreneur_corpus"


def ensure_qdrant_collection():
    headers = {"Content-Type": "application/json", "api-key": QDRANT_API_KEY}
    check_url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}"
    req = urllib.request.Request(check_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if data.get("result"):
                print(f"[Qdrant] Collection '{COLLECTION_NAME}' exists.", flush=True)
                return
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"[Qdrant] Warning on collection check: {e}", flush=True)

    print(f"[Qdrant] Creating collection '{COLLECTION_NAME}'...", flush=True)
    create_payload = {
        "vectors": {
            "size": 384,
            "distance": "Cosine",
        }
    }
    create_req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        data=json.dumps(create_payload).encode(),
        headers=headers,
        method="PUT",
    )
    with urllib.request.urlopen(create_req, timeout=15) as resp:
        print("[Qdrant] Collection created successfully.", flush=True)


def upload_points_to_qdrant(points: list[dict]):
    headers = {"Content-Type": "application/json", "api-key": QDRANT_API_KEY}
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        data = json.dumps({"points": batch}).encode("utf-8")
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
            data=data,
            headers=headers,
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            pass


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks of chunk_size."""
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(current) + len(p) + 2 <= chunk_size:
            current = f"{current}\n\n{p}" if current else p
        else:
            if current:
                chunks.append(current)
            if len(p) <= chunk_size:
                current = p
            else:
                # Split large paragraph by lines or sentences
                sentences = re.split(r"(?<=[.!?])\s+", p)
                for s in sentences:
                    if len(current) + len(s) + 1 <= chunk_size:
                        current = f"{current} {s}" if current else s
                    else:
                        if current:
                            chunks.append(current)
                        current = s
    if current:
        chunks.append(current)

    # Apply sliding overlap
    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-chunk_overlap:] if len(chunks[i - 1]) >= chunk_overlap else chunks[i - 1]
            merged = f"{prev_tail} {chunks[i]}"
            overlapped.append(merged)
        return [c.strip() for c in overlapped if c.strip()]

    return [c.strip() for c in chunks if c.strip()]


def main():
    if not os.path.exists(CORPUS_PATH):
        print(f"ERROR: Corpus not found at {CORPUS_PATH}", flush=True)
        sys.exit(1)

    print("=== AfriMentor RAG Direct Host-Side Ingestion ===", flush=True)
    print(f"Target: Qdrant Cloud ({QDRANT_URL})", flush=True)

    # 1. Ensure collection exists
    ensure_qdrant_collection()

    # 2. Initialize Chroma embedding function
    print("Loading Chroma embedding function (all-MiniLM-L6-v2)...", flush=True)
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    embedding_fn = DefaultEmbeddingFunction()

    # 3. Read records
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    print(f"Found {len(records)} documents to ingest.\n", flush=True)

    total_chunks = 0
    t0 = time.time()

    for idx, record in enumerate(records, start=1):
        doc_id = record["doc_id"]
        meta = record["metadata"]
        content = record["content"]
        speaker = meta.get("speaker", "-")
        country = meta.get("country", "-")
        sector = meta.get("primary_sector", "-")

        print(f"[{idx}/{len(records)}] Ingesting {doc_id} ({speaker}, {country})...", flush=True)

        chunks = chunk_text(content)
        if not chunks:
            print("  Skipped: empty content", flush=True)
            continue

        # Embed all chunks
        embeddings = embedding_fn(chunks)

        # Build Qdrant points
        points = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_{i}"
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))
            payload = {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "content": chunk,
                "document": chunk,
                "figure_id": meta.get("figure_id") or "",
                "market": meta.get("country_code", "general"),
                "country_code": meta.get("country_code", "general"),
                "sector": normalize_sector(sector),
                "sector_label": sector or "",
                "content_type": (meta.get("content_type") or "").lower(),
                "language": meta.get("language", "en"),
                "tier": 1,
                "chunk_index": i,
                "title": meta.get("title") or "",
                "author": speaker or "",
                "source_url": meta.get("url") or "",
                "channel": meta.get("channel") or "",
                "source_origin": map_source_origin(meta),
            }
            vec = [float(x) for x in embeddings[i]]
            points.append({
                "id": point_id,
                "vector": vec,
                "payload": payload,
            })

        # Upload to Qdrant Cloud
        upload_points_to_qdrant(points)
        total_chunks += len(chunks)
        print(f"  OK: {len(chunks)} chunks embedded & written to Qdrant.", flush=True)

    elapsed = round(time.time() - t0, 1)
    print("\n" + "=" * 50, flush=True)
    print(f"Ingestion complete: {len(records)} documents, {total_chunks} chunks.", flush=True)
    print(f"Total time: {elapsed} seconds.", flush=True)

    # 4. Check Qdrant point count
    count_req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/count",
        data=json.dumps({"exact": True}).encode(),
        headers={"Content-Type": "application/json", "api-key": QDRANT_API_KEY},
        method="POST",
    )
    with urllib.request.urlopen(count_req, timeout=10) as resp:
        count_data = json.loads(resp.read().decode())
        active_points = count_data.get("result", {}).get("count", 0)
        print(f"Qdrant Active Points: {active_points}", flush=True)


if __name__ == "__main__":
    main()