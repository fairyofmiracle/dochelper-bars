"""HTTP-клиент Ollama: локально или Ollama Cloud (Bearer API key)."""
from __future__ import annotations

import httpx

from app.config import settings


def ollama_headers() -> dict[str, str]:
    key = settings.ollama_api_key.strip()
    if key:
        return {"Authorization": f"Bearer {key}"}
    return {}


def ollama_get(url: str, **kwargs) -> httpx.Response:
    with httpx.Client(timeout=kwargs.pop("timeout", 30.0), headers=ollama_headers()) as client:
        return client.get(url, **kwargs)


def ollama_post(url: str, **kwargs) -> httpx.Response:
    with httpx.Client(timeout=kwargs.pop("timeout", 180.0), headers=ollama_headers()) as client:
        return client.post(url, **kwargs)
