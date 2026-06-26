"""Семантический поиск в Qdrant."""
from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient

from app.config import settings
from app.rag.embedder import embed_query


@dataclass
class SearchHit:
    source: str
    text: str
    score: float
    kind: str = "text"
    image: str = ""
    image_path: str = ""


def _get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, check_compatibility=False)


def search(query: str, top_k: int | None = None) -> list[SearchHit]:
    k = top_k or settings.top_k_chunks
    client = _get_client()
    vector = embed_query(query)

    try:
        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=k,
            with_payload=True,
        )
        results = response.points
    except Exception:
        return []

    hits: list[SearchHit] = []
    for r in results:
        payload = r.payload or {}
        hits.append(
            SearchHit(
                source=str(payload.get("source", "")),
                text=str(payload.get("text", "")),
                score=float(r.score),
                kind=str(payload.get("kind", "text")),
                image=str(payload.get("image", "")),
                image_path=str(payload.get("image_path", "")),
            )
        )
    return hits


def best_confidence(hits: list[SearchHit]) -> float:
    if not hits:
        return 0.0
    return max(h.score for h in hits)
