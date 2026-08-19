#!/usr/bin/env python3
"""Drop the RAG corpus from Postgres and ChromaDB so it can be re-ingested.

Card C2.2 added catalogue columns to `documents`. Schema comes from
`Base.metadata.create_all()` at startup, which creates tables but never alters
existing ones, and Alembic in this service is 0-byte scaffolding — so picking up
new columns means rebuilding the table.

Both stores must be cleared together: re-ingest mints fresh uuid4 doc_ids, so
chunks left in ChromaDB would orphan and inflate the vector count in /stats.

DESTRUCTIVE. Intended for dev, where the corpus is fully reproducible from
corpus/data/corpus.jsonl via scripts/ingest_tier1.py. Requires --yes.

    python scripts/reset_corpus.py --yes
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from sqlalchemy import text

from app.db.chroma import CHROMA_URL
from app.db.session import engine

COLLECTION_NAME = os.getenv("RAG_COLLECTION", "afrimentor_corpus")


def reset_postgres() -> None:
    """Drop the documents table and its enum types.

    The enums must go too — create_all() raises DuplicateObject if the type
    survives a table drop.
    """
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS documents CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS document_status CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS document_origin CASCADE"))
    print("  Postgres: dropped table 'documents' + enum types")


def reset_chroma() -> None:
    host, _, port = CHROMA_URL.replace("http://", "").replace("https://", "").partition(":")
    client = chromadb.HttpClient(host=host, port=int(port or 8000))
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"  ChromaDB: deleted collection '{COLLECTION_NAME}'")
    except Exception as exc:
        # Already absent is the expected case on a repeat run.
        print(f"  ChromaDB: nothing to delete ({exc})")


def main() -> None:
    if "--yes" not in sys.argv:
        print(__doc__)
        print("Refusing to run without --yes.")
        sys.exit(1)

    print("Resetting RAG corpus")
    print(f"  Postgres: {engine.url.render_as_string(hide_password=True)}")
    print(f"  ChromaDB: {CHROMA_URL}")
    print()

    reset_postgres()
    reset_chroma()

    print()
    print("Done. Restart the service to recreate tables, then run:")
    print("  python scripts/ingest_tier1.py")
    print("  python scripts/fetch_tier2_sources.py && python scripts/ingest_tier2.py")


if __name__ == "__main__":
    main()
