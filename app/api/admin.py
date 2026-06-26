import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.rag.indexer import collection_info, delete_by_source, index_all
from app.rag.parser import SUPPORTED, list_document_files

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/documents")
async def list_docs():
    files = list_document_files(settings.docs_dir, settings.upload_dir)
    items = []
    for p in files:
        items.append(
            {
                "name": p.name,
                "folder": p.parent.name,
                "size_bytes": p.stat().st_size,
                "suffix": p.suffix.lower(),
            }
        )
    return {"documents": items, "qdrant": collection_info()}


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED:
        raise HTTPException(400, f"Формат {ext} не поддерживается. Допустимо: {SUPPORTED}")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.upload_dir / (file.filename or "upload" + ext)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    delete_by_source(dest.name)
    stats = index_all(clear=False)
    return {"ok": True, "file": dest.name, "index": stats.__dict__}


@router.delete("/documents/{filename}")
async def remove_doc(filename: str):
    removed = False
    for folder in (settings.docs_dir, settings.upload_dir):
        path = folder / filename
        if path.exists():
            path.unlink()
            removed = True
    if not removed:
        raise HTTPException(404, "Файл не найден")
    delete_by_source(filename)
    return {"ok": True, "deleted": filename}


@router.post("/reindex")
async def reindex(clear: bool = True):
    stats = index_all(clear=clear)
    return {"ok": True, "stats": stats.__dict__}
