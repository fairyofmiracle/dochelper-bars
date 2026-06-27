"""Семантический поиск в Qdrant."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from qdrant_client import QdrantClient

from app.config import settings
from app.rag.embedder import embed_query

_STOP_WORDS = frozenset(
    {
        "как",
        "что",
        "где",
        "когда",
        "какой",
        "какая",
        "какие",
        "какое",
        "можно",
        "нужно",
        "есть",
        "этот",
        "этой",
        "компании",
        "компания",
        "барс",
        "груп",
        "групп",
        "барс",
        "офис",
        "мне",
        "меня",
    }
)


@dataclass
class SearchHit:
    source: str
    text: str
    score: float
    kind: str = "text"
    image: str = ""
    image_path: str = ""
    chunk_index: int = 0


def _get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, check_compatibility=False)


def _query_terms(query: str) -> list[str]:
    words = re.findall(r"[\w\u0400-\u04FF]+", query.lower())
    return [w for w in words if len(w) >= 4 and w not in _STOP_WORDS]


def _term_in_text(term: str, text: str) -> bool:
    if term in text:
        return True
    if len(term) >= 5:
        stem = term[: max(5, len(term) - 2)]
        return stem in text
    return False


def _rerank_hits(query: str, hits: list[SearchHit]) -> list[SearchHit]:
    terms = _query_terms(query)
    if not terms:
        return hits

    def rank(h: SearchHit) -> float:
        text = h.text.lower()
        kw = sum(1 for t in terms if _term_in_text(t, text))
        return h.score + kw * 0.12

    ranked = sorted(hits, key=rank, reverse=True)
    for h in ranked:
        h.score = rank(h)
    return ranked


def search(query: str, top_k: int | None = None) -> list[SearchHit]:
    k = top_k or settings.top_k_chunks
    client = _get_client()
    vector = embed_query(query)

    try:
        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=max(k * 4, 12),
            with_payload=True,
        )
        results = response.points
    except Exception:
        return []

    hits: list[SearchHit] = []
    for r in results:
        payload = r.payload or {}
        if payload.get("kind", "text") != "text":
            continue
        hits.append(
            SearchHit(
                source=str(payload.get("source", "")),
                text=str(payload.get("text", "")),
                score=float(r.score),
                kind="text",
                image=str(payload.get("image", "")),
                image_path=str(payload.get("image_path", "")),
                chunk_index=int(payload.get("chunk_index", 0)),
            )
        )
    return _rerank_hits(query, hits)[:k]


def search_images(
    query: str,
    *,
    prefer_sources: list[str] | None = None,
    top_k: int = 2,
    min_score: float = 0.72,
) -> list[SearchHit]:
    """Иллюстрации из docx — отдельные точки в Qdrant с kind=image."""
    client = _get_client()
    vector = embed_query(query)

    try:
        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=40,
            with_payload=True,
        )
    except Exception:
        return []

    candidates: list[SearchHit] = []
    for r in response.points:
        payload = r.payload or {}
        if payload.get("kind") != "image" or not payload.get("image_path"):
            continue
        score = float(r.score)
        if score < min_score:
            continue
        candidates.append(
            SearchHit(
                source=str(payload.get("source", "")),
                text=str(payload.get("text", "")),
                score=score,
                kind="image",
                image=str(payload.get("image", "")),
                image_path=str(payload.get("image_path", "")),
                chunk_index=int(payload.get("chunk_index", 0)),
            )
        )

    if prefer_sources:
        pref = set(prefer_sources)
        candidates.sort(
            key=lambda h: (h.source not in pref, -h.score),
        )
    else:
        candidates.sort(key=lambda h: -h.score)

    return candidates[:top_k]


def find_doc_images(source: str, image_names: list[str] | None = None) -> list[SearchHit]:
    """Точный поиск иллюстраций документа по имени файла."""
    client = _get_client()
    names = {Path(n).name for n in (image_names or [])}
    hits: list[SearchHit] = []
    offset = None
    while True:
        pts, offset = client.scroll(
            collection_name=settings.qdrant_collection,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        for p in pts:
            payload = p.payload or {}
            if payload.get("kind") != "image" or payload.get("source") != source:
                continue
            img = Path(str(payload.get("image", ""))).name
            if names and img not in names:
                continue
            hits.append(
                SearchHit(
                    source=source,
                    text=str(payload.get("text", "")),
                    score=1.0,
                    kind="image",
                    image=img,
                    image_path=str(payload.get("image_path", "")),
                    chunk_index=int(payload.get("chunk_index", 0)),
                )
            )
        if offset is None:
            break
    if names:
        order = {n: i for i, n in enumerate(names)}
        hits.sort(key=lambda h: order.get(Path(h.image).name, 99))
    return hits


def best_confidence(hits: list[SearchHit]) -> float:
    if not hits:
        return 0.0
    return max(h.score for h in hits)
