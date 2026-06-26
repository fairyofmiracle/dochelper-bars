"""Описание картинок из docx через Ollama vision (опционально)."""
from __future__ import annotations

import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PROMPT = (
    "Опиши на русском языке содержимое изображения из корпоративной инструкции. "
    "Если это схема бизнес-процесса или интерфейс программы — перечисли шаги, кнопки, "
    "стрелки и подписи. Если текст на картинке мелкий — процитируй его. Без выдумок."
)


def describe_image(image_bytes: bytes, source: str, image_name: str) -> str:
    model = settings.ollama_vision_model.strip()
    if not model:
        return f"[Изображение {image_name} в документе {source}. Для распознавания задайте OLLAMA_VISION_MODEL=qwen2-vl:7b]"

    b64 = base64.b64encode(image_bytes).decode()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT, "images": [b64]}],
        "stream": False,
    }
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            content = r.json()["message"]["content"].strip()
            return f"[Изображение: {image_name}]\n{content}"
    except Exception as exc:
        logger.warning("vision failed for %s/%s: %s", source, image_name, exc)
        return f"[Изображение {image_name} в {source} — vision недоступен: {exc}]"
