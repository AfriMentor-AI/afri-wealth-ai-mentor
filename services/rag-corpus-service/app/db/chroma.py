import os

import chromadb

CHROMA_URL = os.getenv("CHROMA_URL", "http://localhost:8100")

def get_chroma_collection(collection_name: str = "afrimentor_corpus"):
    """Return the ChromaDB collection, creating it if it doesn't exist."""
    host, port = CHROMA_URL.replace("http://", "").split(":")
    client = chromadb.HttpClient(host=host, port=int(port))
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return collection
