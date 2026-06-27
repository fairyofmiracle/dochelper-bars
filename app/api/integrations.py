"""Webhooks и статус интеграций (Git, Confluence, TMS)."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.services.doc_sync import get_last_sync, handle_confluence_webhook, handle_git_webhook, run_reindex
from app.services.tickets import get_ticket

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _check_webhook_secret(secret: str | None) -> None:
    expected = settings.webhook_secret.strip()
    if not expected:
        return
    if not secret or secret.strip() != expected:
        raise HTTPException(401, "Invalid webhook secret")


@router.get("/status")
async def integrations_status(request: Request):
    base = str(request.base_url).rstrip("/")
    last = get_last_sync()
    return {
        "ticket_provider": settings.ticket_provider or "mock",
        "ticket_demo": settings.ticket_provider.lower() in ("", "mock", "usedesk", "jira", "zendesk"),
        "webhooks": {
            "git": f"{base}/api/integrations/webhooks/git",
            "confluence": f"{base}/api/integrations/webhooks/confluence",
            "secret_required": bool(settings.webhook_secret.strip()),
        },
        "last_sync": last,
        "sync_reindex_clear": settings.sync_reindex_clear,
    }


@router.post("/webhooks/git")
async def webhook_git(
    request: Request,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    _check_webhook_secret(x_webhook_secret)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    result = handle_git_webhook(payload if isinstance(payload, dict) else {})
    if not result.ok:
        raise HTTPException(500, result.message)
    return {"ok": True, "sync": result.to_dict()}


@router.post("/webhooks/confluence")
async def webhook_confluence(
    request: Request,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    _check_webhook_secret(x_webhook_secret)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    result = handle_confluence_webhook(payload if isinstance(payload, dict) else {})
    if not result.ok:
        raise HTTPException(500, result.message)
    return {"ok": True, "sync": result.to_dict()}


@router.post("/demo/git-sync")
async def demo_git_sync(clear: bool = False):
    """Кнопка на панели оператора — симуляция push в Git для демо."""
    result = run_reindex("git", trigger="demo: git push main (simulated)", clear=clear)
    if not result.ok:
        raise HTTPException(500, result.message)
    return {"ok": True, "sync": result.to_dict()}


@router.post("/demo/confluence-sync")
async def demo_confluence_sync():
    """Симуляция обновления страницы Confluence."""
    from app.services.doc_sync import handle_confluence_webhook

    result = handle_confluence_webhook({"page_title": "Functionalnie.docx (demo)"})
    if not result.ok:
        raise HTTPException(500, result.message)
    return {"ok": True, "sync": result.to_dict()}


@router.get("/ticket/{session_id}")
async def ticket_for_session(session_id: str):
    ticket = get_ticket(session_id)
    if not ticket:
        return {"ticket": None}
    return {"ticket": ticket}
