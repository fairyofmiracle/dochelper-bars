"""Embeddings: sentence-transformers или Ollama."""
from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_data_root = os.getenv("DATA_ROOT", "D:/bars-support-bot-data")
_default_hf = os.getenv("HF_HOME", f"{_data_root}/huggingface")
os.environ.setdefault("HF_HOME", _default_hf)
os.environ.setdefault("TRANSFORMERS_CACHE", _default_hf)
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", _default_hf)
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

_model = None
_model_lock = __import__("threading").Lock()


def _hf_cache_dir() -> Path:
    return Path(os.environ.get("HF_HOME", _default_hf))


def _model_cached_locally() -> bool:
    cache = _hf_cache_dir()
    slug = settings.embed_model.replace("/", "--")
    return (cache / f"models--{slug}").exists() or (cache / "hub" / f"models--{slug}").exists()


def _resolve_model_path() -> str:
    from huggingface_hub import snapshot_download

    cache = str(_hf_cache_dir())
    if _model_cached_locally():
        os.environ["HF_HUB_OFFLINE"] = "1"
        logger.info("Embeddings: load from local cache (offline, no HuggingFace download)")
        return snapshot_download(settings.embed_model, cache_dir=cache, local_files_only=True)
    logger.info("Embeddings: first-time download to %s ...", cache)
    os.environ.pop("HF_HUB_OFFLINE", None)
    return snapshot_download(settings.embed_model, cache_dir=cache)


def _get_st_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            model_path = _resolve_model_path()
            _model = SentenceTransformer(model_path, local_files_only=_model_cached_locally())
            logger.info("Embedding model in memory")
    return _model


def warmup_embedder() -> None:
    """Загрузить модель embeddings в RAM один раз при старте."""
    if settings.embed_provider == "ollama":
        _ollama_embed("warmup")
        logger.info("Ollama embedding model ready: %s", settings.embed_model)
        return
    _get_st_model()
    embed_query("warmup")


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if settings.embed_provider == "ollama":
        return [_ollama_embed(t) for t in texts]
    model = _get_st_model()
    prefixed = [f"query: {t}" if settings.embed_provider == "sentence-transformers" else t for t in texts]
    if "e5" in settings.embed_model.lower():
        prefixed = [f"passage: {t}" for t in texts]
    vectors = model.encode(prefixed, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_query(query: str) -> list[float]:
    if settings.embed_provider == "ollama":
        return _ollama_embed(query)
    model = _get_st_model()
    prefix = f"query: {query}" if "e5" in settings.embed_model.lower() else query
    vector = model.encode(prefix, normalize_embeddings=True)
    return vector.tolist()


def _ollama_embed(text: str) -> list[float]:
    base = settings.ollama_base_url.rstrip("/")
    payload = {"model": settings.embed_model, "input": text}
    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{base}/api/embed", json=payload)
        if r.status_code == 404:
            r = client.post(
                f"{base}/api/embeddings",
                json={"model": settings.embed_model, "prompt": text},
            )
        r.raise_for_status()
        data = r.json()
        if "embeddings" in data:
            return data["embeddings"][0]
        return data["embedding"]
