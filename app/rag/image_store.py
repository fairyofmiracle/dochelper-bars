"""Хранение иллюстраций из docx для ответов с картинкой."""
from __future__ import annotations

import os
from pathlib import Path

from app.config import settings


def doc_images_root() -> Path:
    return settings.doc_images_dir


def save_doc_image(file_id: str, name: str, data: bytes) -> str:
    """Сохранить bytes, вернуть относительный путь ``file_id/name``."""
    safe_name = Path(name).name
    folder = doc_images_root() / file_id
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / safe_name
    dest.write_bytes(data)
    return f"{file_id}/{safe_name}"


def resolve_doc_image(relative: str) -> Path | None:
    rel = relative.replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        return None
    path = doc_images_root() / rel
    if path.is_file():
        return path
    return None


def image_api_url(relative: str) -> str:
    return f"/api/doc-images/{relative.replace(chr(92), '/')}"
