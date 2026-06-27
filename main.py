"""DocHelper Барс — API, RAG, Telegram."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# HF cache on D: before any heavy imports
_data_root = os.getenv("DATA_ROOT", "D:/bars-support-bot-data")
_hf = os.getenv("HF_HOME", f"{_data_root}/huggingface")
os.environ.setdefault("HF_HOME", _hf)
os.environ.setdefault("TRANSFORMERS_CACHE", _hf)
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", _hf)
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from redis import Redis

from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.chat import router as chat_router
from app.api.operator import router as operator_router
from app.config import settings
from app.rag.image_store import resolve_doc_image
from app.rag.indexer import collection_info, index_all
from app.rag.parser import list_document_files

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for _quiet in ("httpx", "huggingface_hub", "sentence_transformers.base.model"):
    logging.getLogger(_quiet).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

telegram_status: dict[str, object] = {"running": False, "error": None}

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.doc_images_dir.mkdir(parents=True, exist_ok=True)

    try:
        from app.llm.warmup import warmup_ollama
        from app.rag.embedder import warmup_embedder

        await asyncio.to_thread(warmup_ollama)
        await asyncio.to_thread(warmup_embedder)
        logger.info("LLM + embedding warmup done")
    except Exception as exc:
        logger.warning("Model warmup skipped: %s", exc)

    try:
        if settings.auto_index_on_start:
            info = collection_info()
            files = list_document_files(settings.docs_dir, settings.upload_dir)
            if files and info.get("points", 0) == 0:
                logger.info("Auto-index %s files...", len(files))
                stats = index_all(clear=True)
                logger.info("Indexed: %s", stats)
    except Exception as exc:
        logger.warning("Auto-index skipped: %s", exc)

    logger.info("All models ready — accepting questions")

    tg_app = None
    if settings.telegram_enabled and settings.telegram_bot_token.strip():
        try:
            from app.bot.telegram_bot import build_application

            tg_app = build_application()
            await tg_app.initialize()
            await tg_app.start()
            if tg_app.updater:
                await tg_app.updater.start_polling(drop_pending_updates=True)
            telegram_status["running"] = True
            telegram_status["error"] = None
            logger.info("Telegram bot started (single instance — do not run Docker app in parallel)")
        except Exception as exc:
            telegram_status["running"] = False
            telegram_status["error"] = str(exc)
            logger.error(
                "Telegram bot failed: %s — проверьте доступ к api.telegram.org "
                "или задайте TELEGRAM_PROXY_URL в .env",
                exc,
            )
    elif settings.telegram_bot_token.strip():
        logger.info("Telegram bot disabled (TELEGRAM_ENABLED=false)")

    yield

    if tg_app:
        try:
            if tg_app.updater and tg_app.updater.running:
                await tg_app.updater.stop()
            await tg_app.stop()
            await tg_app.shutdown()
        except Exception as exc:
            logger.warning("Telegram shutdown: %s", exc)


app = FastAPI(title="DocHelper Барс", version="1.0.0", lifespan=lifespan)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(analytics_router)
app.include_router(operator_router)

if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/api/doc-images/{file_path:path}")
async def doc_image(file_path: str):
    resolved = resolve_doc_image(file_path)
    if not resolved:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(resolved)


@app.get("/api/documents/{filename}")
async def download_document(filename: str):
    from fastapi import HTTPException
    from urllib.parse import unquote

    name = unquote(filename)
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(400, "Invalid filename")
    for folder in (settings.docs_dir, settings.upload_dir):
        path = folder / name
        if path.is_file():
            return FileResponse(path, filename=name)
    raise HTTPException(404, "Document not found")


@app.get("/operator")
async def operator_page():
    index = STATIC / "operator.html"
    if index.exists():
        return FileResponse(index)
    return FileResponse(STATIC / "index.html")


@app.get("/api/demo-links")
async def demo_links(request: Request):
    base = settings.public_demo_url.strip().rstrip("/") or str(request.base_url).rstrip("/")
    bot_user = settings.telegram_bot_username.strip().lstrip("@")
    telegram = f"https://t.me/{bot_user}" if bot_user else ""
    return {
        "web_chat": f"{base}/",
        "operator": f"{base}/operator",
        "telegram": telegram,
        "telegram_set": bool(bot_user),
        "repo": "https://tatarsan.space/one_commit/bars_support_bot",
    }


@app.get("/")
async def index_page():
    index = STATIC / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"service": settings.bot_name, "health": "/api/health", "docs": "/docs"}


@app.get("/api/health")
async def health():
    ollama_ok = False
    ollama_models: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            if r.status_code == 200:
                ollama_ok = True
                ollama_models = [m.get("name", "") for m in r.json().get("models", [])]
    except httpx.HTTPError:
        pass

    qdrant_ok = False
    qdrant_points = 0
    try:
        info = collection_info()
        qdrant_ok = info.get("exists", False)
        qdrant_points = info.get("points", 0)
    except Exception:
        pass

    redis_ok = False
    try:
        redis_ok = bool(Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping())
    except Exception:
        pass

    docs_count = len(list_document_files(settings.docs_dir, settings.upload_dir))

    return {
        "status": "ok",
        "port": settings.app_port,
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.ollama_model,
            "vision_model": settings.ollama_vision_model or None,
            "ollama_url": settings.ollama_base_url,
            "ollama_reachable": ollama_ok,
            "models_installed": ollama_models,
        },
        "embed_model": settings.embed_model,
        "qdrant_ok": qdrant_ok,
        "qdrant_points": qdrant_points,
        "redis_ok": redis_ok,
        "telegram_token_set": bool(settings.telegram_bot_token),
        "telegram_running": telegram_status["running"],
        "telegram_error": telegram_status["error"],
        "telegram_proxy_set": bool(settings.telegram_proxy_url.strip()),
        "support_chat_set": bool(settings.telegram_support_chat_id),
        "docs_count": docs_count,
        "vision_ready": bool(settings.ollama_vision_model.strip()),
        "doc_images_dir": str(settings.doc_images_dir),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=False)
