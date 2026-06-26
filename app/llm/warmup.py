"""Прогрев Ollama — загрузить LLM в память до первого вопроса."""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def warmup_ollama() -> None:
    if settings.llm_provider != "ollama":
        return
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    logger.info("Ollama: loading %s into memory (once at startup)...", settings.ollama_model)
    with httpx.Client(timeout=300.0) as client:
        r = client.post(
            url,
            json={
                "model": settings.ollama_model,
                "messages": [{"role": "user", "content": "ok"}],
                "stream": False,
                "options": {"num_predict": 1, "temperature": 0},
            },
        )
        r.raise_for_status()
    logger.info("Ollama model ready")
