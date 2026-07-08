"""Поиск исходных файлов документации на диске."""
from __future__ import annotations

from pathlib import Path

from app.config import settings


def resolve_document_path(filename: str) -> Path | None:
    name = Path(filename).name
    if not name or name in {".", ".."}:
        return None
    for folder in (settings.docs_dir, settings.upload_dir):
        path = folder / name
        if path.is_file():
            return path
    return None
