import logging
import os
import time
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_embedding_fn = None
_cached_adapters: dict[str, Any] = {}


def get_embedding_fn():
    """Lazy load the default Chroma embedding function (all-MiniLM-L6-v2)."""
    global _embedding_fn
    if _embedding_fn is None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        _embedding_fn = DefaultEmbeddingFunction()
    return _embedding_fn


class QdrantCollectionAdapter:
    """Adapts Qdrant REST API to ChromaDB collection interface with retries
    and connection pooling.
    """

    def __init__(self, name: str, url: str, api_key: str | None = None):
        self.name = name
        url = url.strip().rstrip("/")
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        self.url = url
        self.api_key = api_key
        self._headers = {"Content-Type": "application/json"}
        if self.api_key:
            self._headers["api-key"] = self.api_key
        self._created = False
        self._client = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=15.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        self._ensure_collection()

    def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.url}{path}"
        headers = kwargs.pop("headers", self._headers)
        last_exc = None
        for attempt in range(4):
            try:
                resp = self._client.request(method, url, headers=headers, **kwargs)
                return resp
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning(
                    "Qdrant request %s %s failed (attempt %d/4): %s",
                    method,
                    path,
                    attempt + 1,
                    exc,
                )
                time.sleep(1.0 * (attempt + 1))
        raise last_exc

    def _ensure_collection(self) -> None:
        if self._created:
            return
        try:
            resp = self._request_with_retry("GET", f"/collections/{self.name}", timeout=20.0)
            if resp.status_code == 404 or (
                resp.status_code == 200 and not resp.json().get("result")
            ):
                logger.info("Creating Qdrant collection '%s'", self.name)
                create_payload = {
                    "vectors": {
                        "size": 384,
                        "distance": "Cosine",
                    }
                }
                c_resp = self._request_with_retry(
                    "PUT",
                    f"/collections/{self.name}",
                    json=create_payload,
                    timeout=30.0,
                )
                c_resp.raise_for_status()
            self._created = True
        except Exception as exc:
            logger.warning("Failed to verify/create Qdrant collection %s: %s", self.name, exc)

    def count(self) -> int:
        try:
            resp = self._request_with_retry(
                "POST",
                f"/collections/{self.name}/points/count",
                json={"exact": True},
                timeout=20.0,
            )
            if resp.status_code == 200:
                return resp.json().get("result", {}).get("count", 0)
        except Exception as exc:
            logger.warning("Error counting Qdrant points: %s", exc)
        return 0

    def add(
        self,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if not documents:
            return
        self._ensure_collection()
        ef = get_embedding_fn()
        embeddings = ef(documents)

        points = []
        for i, doc_text in enumerate(documents):
            chunk_id = ids[i] if i < len(ids) else f"chunk_{i}"
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))
            meta = dict(metadatas[i]) if metadatas and i < len(metadatas) else {}
            meta["chunk_id"] = chunk_id
            if "doc_id" not in meta:
                meta["doc_id"] = chunk_id.rsplit("_", 1)[0]
            meta["content"] = doc_text
            meta["document"] = doc_text

            points.append({
                "id": point_id,
                "vector": [float(x) for x in embeddings[i]],
                "payload": meta,
            })

        batch_size = 64
        for idx in range(0, len(points), batch_size):
            batch = points[idx : idx + batch_size]
            resp = self._request_with_retry(
                "PUT",
                f"/collections/{self.name}/points?wait=true",
                json={"points": batch},
                timeout=60.0,
            )
            resp.raise_for_status()

    def query(
        self,
        query_texts: list[str],
        n_results: int = 5,
        include: list[str] | None = None,
    ) -> dict[str, list]:
        if not query_texts:
            return {"documents": [[]], "ids": [[]], "metadatas": [[]], "distances": [[]]}

        self._ensure_collection()
        ef = get_embedding_fn()
        raw_vec = ef([query_texts[0]])[0]
        query_vec = [float(x) for x in raw_vec]

        search_payload = {
            "vector": query_vec,
            "limit": n_results,
            "with_payload": True,
            "with_vector": False,
        }
        resp = self._request_with_retry(
            "POST",
            f"/collections/{self.name}/points/search",
            json=search_payload,
            timeout=30.0,
        )
        resp.raise_for_status()
        items = resp.json().get("result", [])

        res_docs: list[str] = []
        res_ids: list[str] = []
        res_metas: list[dict] = []
        res_dists: list[float] = []

        for item in items:
            payload = item.get("payload") or {}
            score = float(item.get("score", 0.0))
            distance = max(0.0, 1.0 - score)
            chunk_id = payload.get("chunk_id") or str(item.get("id"))
            content = payload.get("document") or payload.get("content") or ""
            clean_meta = {k: v for k, v in payload.items() if k not in ("document",)}

            res_docs.append(content)
            res_ids.append(chunk_id)
            res_metas.append(clean_meta)
            res_dists.append(distance)

        return {
            "documents": [res_docs],
            "ids": [res_ids],
            "metadatas": [res_metas],
            "distances": [res_dists],
        }

    def delete(self, where: dict | None = None) -> None:
        if not where:
            return
        doc_id = where.get("doc_id")
        if not doc_id:
            return
        del_payload = {
            "filter": {
                "must": [
                    {
                        "key": "doc_id",
                        "match": {"value": doc_id},
                    }
                ]
            }
        }
        try:
            self._request_with_retry(
                "POST",
                f"/collections/{self.name}/points/delete?wait=true",
                json=del_payload,
                timeout=30.0,
            )
        except Exception as exc:
            logger.warning("Failed to delete points for doc_id %s: %s", doc_id, exc)


CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")


def get_chroma_collection(collection_name: str = "afrimentor_corpus"):
    """Return collection instance (cached Qdrant Cloud adapter or ChromaDB fallback)."""
    global _cached_adapters
    if collection_name in _cached_adapters:
        return _cached_adapters[collection_name]

    qdrant_url = os.getenv("QDRANT_URL", "").strip()
    if qdrant_url:
        api_key = os.getenv("QDRANT_API_KEY", "").strip() or None
        adapter = QdrantCollectionAdapter(collection_name, url=qdrant_url, api_key=api_key)
        _cached_adapters[collection_name] = adapter
        return adapter

    import chromadb
    from urllib.parse import urlparse

    chroma_url = os.getenv("CHROMA_URL", "").strip()
    if chroma_url:
        try:
            parsed = urlparse(chroma_url)
            host = parsed.hostname or "chromadb"
            port = parsed.port or 8000
            ssl = parsed.scheme == "https"
            client = chromadb.HttpClient(host=host, port=port, ssl=ssl)
            coll = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            _cached_adapters[collection_name] = coll
            return coll
        except Exception as exc:
            logger.warning(
                "Remote Chroma connection failed: %s, falling back to persistent client",
                exc,
            )

    client = chromadb.PersistentClient(path=os.getenv("CHROMA_PERSIST_DIR", "/app/chroma_data"))
    coll = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    _cached_adapters[collection_name] = coll
    return coll

