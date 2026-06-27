"""Описание изображений: docx при индексации и скрины от пользователя."""
from __future__ import annotations

import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DOC_PROMPT = (
    "Опиши на русском содержимое изображения из корпоративной инструкции. "
    "Если это схема бизнес-процесса или интерфейс программы — перечисли шаги, кнопки, "
    "стрелки и подписи. Если текст на картинке мелкий — процитируй его. Без выдумок."
)

USER_PROMPT = (
    "Пользователь прислал скриншот или фото, связанное с корпоративной системой (БАРС-Офис, "
    "документооборот, бизнес-процессы). Опиши на русском, что видно: интерфейс, ошибки, "
    "кнопки, поля, текст на экране. Кратко и по делу."
)


def vision_ready() -> bool:
    return bool(settings.ollama_vision_model.strip())


def describe_image(image_bytes: bytes, source: str, image_name: str) -> str:
    model = settings.ollama_vision_model.strip()
    if not model:
        return (
            f"[Иллюстрация {image_name} из документа {source}. "
            f"Схема или скриншот интерфейса — см. вложение в ответе бота.]"
        )
    return _ollama_vision(image_bytes, DOC_PROMPT) or (
        f"[Изображение {image_name} в {source}]"
    )


def describe_user_image(image_bytes: bytes) -> str:
    model = settings.ollama_vision_model.strip()
    if not model:
        return "[Изображение пользователя — задайте OLLAMA_VISION_MODEL для распознавания]"
    return _ollama_vision(image_bytes, USER_PROMPT)


def _ollama_vision(image_bytes: bytes, prompt: str) -> str:
    model = settings.ollama_vision_model.strip()
    if not model:
        return ""
    b64 = base64.b64encode(image_bytes).decode()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": False,
    }
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
    except Exception as exc:
        logger.warning("vision failed: %s", exc)
        return ""
