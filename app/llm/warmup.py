"""Прогрев Ollama — загрузить LLM в память до первого вопроса."""
from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def warmup_ollama() -> None:
    if settings.llm_provider != "ollama":
        return
    if settings.ollama_api_key.strip():
        logger.info("Ollama Cloud: %s, model %s", settings.ollama_base_url, settings.ollama_model)
        return
    from app.llm.ollama_http import ollama_post

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    logger.info("Ollama: loading %s into memory (once at startup)...", settings.ollama_model)
    r = ollama_post(
        url,
        json={
            "model": settings.ollama_model,
            "messages": [{"role": "user", "content": "ok"}],
            "stream": False,
            "options": {"num_predict": 1, "temperature": 0, "num_thread": 2, "num_ctx": 2048},
        },
        timeout=300.0,
    )
    r.raise_for_status()
    logger.info("Ollama model ready")
