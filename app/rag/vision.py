"""Описание изображений: docx при индексации и скрины от пользователя."""
from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass

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
    "документооборот, бизнес-процессы). Опиши на русском:\n"
    "1) Тип: интерфейс / ошибка / схема / документ / другое\n"
    "2) Что видно: окна, кнопки, поля, текст на экране, коды ошибок\n"
    "3) Ключевые слова для поиска в документации\n"
    "Кратко, без выдумок."
)

IMAGE_TYPE_LABELS = {
    "ui": "Интерфейс системы",
    "error": "Ошибка на экране",
    "diagram": "Схема / блок-схема",
    "document": "Документ / таблица",
    "other": "Изображение",
}


@dataclass
class ImageAnalysis:
    description: str
    image_type: str
    search_query: str
    type_label: str


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


def classify_image_description(desc: str) -> str:
    low = desc.lower()
    if any(w in low for w in ("ошибк", "error", "exception", "fatal", "не удалось", "failed")):
        return "error"
    if any(w in low for w in ("схем", "блок-схем", "diagram", "стрелк", "бп ", "процесс")):
        return "diagram"
    if any(w in low for w in ("таблиц", "документ", "pdf", "реестр", "список")):
        return "document"
    if any(
        w in low
        for w in (
            "интерфейс",
            "кнопк",
            "окно",
            "форма",
            "меню",
            "вкладк",
            "поле",
            "экран",
            "барс",
            "фильтр",
        )
    ):
        return "ui"
    return "other"


def extract_search_query(desc: str, caption: str = "") -> str:
    parts: list[str] = []
    if caption.strip():
        parts.append(caption.strip())
    for line in desc.splitlines():
        low = line.lower()
        if "ключев" in low or "поиск" in low:
            parts.append(re.sub(r"^[\d\.\)\-\*]+\s*", "", line).strip())
    quoted = re.findall(r"[«\"']([^»\"']{3,80})[»\"']", desc)
    parts.extend(quoted[:3])
    if not parts:
        sentences = re.split(r"[.!?]\s+", desc)
        if sentences:
            parts.append(sentences[0][:200])
    query = " ".join(parts)
    query = re.sub(r"\s+", " ", query).strip()
    return query[:400] if query else desc[:200]


def analyze_user_image(image_bytes: bytes, caption: str = "") -> ImageAnalysis | None:
    desc = describe_user_image(image_bytes)
    if not desc or desc.startswith("["):
        return None
    image_type = classify_image_description(desc)
    return ImageAnalysis(
        description=desc,
        image_type=image_type,
        search_query=extract_search_query(desc, caption),
        type_label=IMAGE_TYPE_LABELS.get(image_type, IMAGE_TYPE_LABELS["other"]),
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
        from app.llm.ollama_http import ollama_post

        r = ollama_post(url, json=payload, timeout=180.0)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as exc:
        logger.warning("vision failed: %s", exc)
        return ""
