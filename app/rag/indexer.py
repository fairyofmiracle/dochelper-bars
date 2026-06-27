"""Индексация документов в Qdrant."""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import settings
from app.rag.embedder import embed_texts
from app.rag.parser import chunk_text, list_document_files, parse_document
from app.rag.image_store import save_doc_image
from app.rag.vision import describe_image

logger = logging.getLogger(__name__)


@dataclass
class IndexStats:
    files: int = 0
    chunks: int = 0
    images: int = 0
    errors: list[str] | None = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, check_compatibility=False)


def ensure_collection(client: QdrantClient, vector_size: int = 768) -> None:
    names = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection in names:
        info = client.get_collection(settings.qdrant_collection)
        existing = info.config.params.vectors.size  # type: ignore[union-attr]
        if existing != vector_size:
            client.delete_collection(settings.qdrant_collection)
        else:
            return
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
    )


def _file_hash(path) -> str:
    h = hashlib.md5()
    h.update(path.name.encode())
    h.update(str(path.stat().st_mtime).encode())
    h.update(str(path.stat().st_size).encode())
    return h.hexdigest()


def _point_id(source: str, chunk_idx: int) -> str:
    raw = f"{source}:{chunk_idx}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw))


def index_all(clear: bool = False) -> IndexStats:
    stats = IndexStats()
    files = list_document_files(settings.docs_dir, settings.upload_dir)
    if not files:
        stats.errors.append("Нет документов в data/docs и data/uploads")
        return stats

    sample = embed_texts(["probe"])
    dim = len(sample[0])
    client = get_client()
    if clear:
        try:
            client.delete_collection(settings.qdrant_collection)
        except Exception:
            pass
    ensure_collection(client, dim)

    points: list[qmodels.PointStruct] = []

    for path in files:
        try:
            text, images = parse_document(path)
            source = path.name
            file_id = _file_hash(path)

            chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
            if not chunks and not images:
                stats.errors.append(f"{path.name}: пустой документ")
                continue

            stats.files += 1

            if chunks:
                vectors = embed_texts(chunks)
                for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
                    points.append(
                        qmodels.PointStruct(
                            id=_point_id(source, i),
                            vector=vec,
                            payload={
                                "source": source,
                                "file_id": file_id,
                                "chunk_index": i,
                                "text": chunk,
                                "kind": "text",
                            },
                        )
                    )
                    stats.chunks += 1

            for img_name, img_bytes in images:
                rel_path = save_doc_image(file_id, img_name, img_bytes)
                desc = describe_image(img_bytes, source, img_name)
                if not desc.strip():
                    desc = f"[Иллюстрация {img_name} из {source}]"
                vec = embed_texts([desc])[0]
                idx = stats.chunks
                points.append(
                    qmodels.PointStruct(
                        id=_point_id(f"{source}:{img_name}", idx),
                        vector=vec,
                        payload={
                            "source": source,
                            "file_id": file_id,
                            "chunk_index": idx,
                            "text": desc,
                            "kind": "image",
                            "image": img_name,
                            "image_path": rel_path,
                        },
                    )
                )
                stats.chunks += 1
                stats.images += 1

        except Exception as exc:
            logger.exception("index %s", path)
            stats.errors.append(f"{path.name}: {exc}")

    if points:
        batch = 64
        for i in range(0, len(points), batch):
            client.upsert(collection_name=settings.qdrant_collection, points=points[i : i + batch])

        # sanity check: reject silently-zero vectors (broken embedder)
        sample, _ = client.scroll(
            collection_name=settings.qdrant_collection, limit=3, with_vectors=True
        )
        bad = sum(
            1
            for p in sample
            if not p.vector or sum(x * x for x in p.vector) < 1e-6
        )
        if bad == len(sample) and sample:
            stats.errors.append(
                "Индексация дала нулевые вектора — проверьте embedding-модель и переиндексируйте"
            )
            logger.error("Index sanity check failed: all sampled vectors are zero")

    return stats


def delete_by_source(source: str) -> None:
    client = get_client()
    try:
        names = {c.name for c in client.get_collections().collections}
        if settings.qdrant_collection not in names:
            return
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[qmodels.FieldCondition(key="source", match=qmodels.MatchValue(value=source))]
                )
            ),
        )
    except Exception as exc:
        logger.debug("delete_by_source(%s) skipped: %s", source, exc)


def collection_info() -> dict:
    client = get_client()
    try:
        info = client.get_collection(settings.qdrant_collection)
        return {"exists": True, "points": info.points_count, "status": str(info.status)}
    except Exception:
        return {"exists": False, "points": 0}
