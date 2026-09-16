"""GET /disruptions — collects and returns active disruption signals."""
from fastapi import APIRouter, Depends

from agents.data_collector import collect_disruptions
from agents.disruption_analyzer import analyze_disruptions
from routers.auth import get_current_user

router = APIRouter()


@router.get("/disruptions")
async def get_disruptions(current_user: dict = Depends(get_current_user)):
    collected = await collect_disruptions()
    analyzed = await analyze_disruptions(collected["disruptions"])
    return {
        "total": len(analyzed),
        "weather_count": collected["weather_count"],
        "news_count": collected["news_count"],
        "collector_reasoning": collected["reasoning"],
        "disruptions": analyzed,
    }
