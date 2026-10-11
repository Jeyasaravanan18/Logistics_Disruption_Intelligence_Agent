"""
GET /disruptions — collects and returns active disruption signals.
Persists records to SQL with content_hash deduplication.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agents.data_collector import collect_disruptions
from agents.disruption_analyzer import analyze_disruptions
import crud
from database import get_db
from routers.auth import get_current_user

router = APIRouter()


@router.get("/disruptions")
async def get_disruptions(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    collected = await collect_disruptions()
    analyzed = await analyze_disruptions(collected["disruptions"])
    
    # Persist and deduplicate in SQL database
    saved = await crud.upsert_disruptions(db, analyzed)

    return {
        "total": len(saved),
        "weather_count": collected["weather_count"],
        "news_count": collected["news_count"],
        "collector_reasoning": collected["reasoning"],
        "disruptions": saved,
    }
