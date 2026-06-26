from fastapi import APIRouter

from app.services.analytics import get_stats

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
async def analytics():
    return get_stats()
