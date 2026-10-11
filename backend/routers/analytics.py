"""
Analytics router: advanced relational SQL endpoints for logistics intelligence.
Provides dashboard KPIs (aggregate + FILTER), risk trends (LAG window function),
corridor exposure ranking (multi-table join with GROUP BY/HAVING), and disruption timeline.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

import crud
import schemas
from database import get_db
from routers.auth import get_current_user, owner_id_from_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/kpis", response_model=schemas.DashboardKPIsResponse)
async def get_dashboard_kpis(
    run_id: str | None = Query(default=None, description="Optional pipeline run ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Dashboard KPIs for the latest pipeline run.
    Uses SQL single-pass aggregate with FILTER clauses to count risk levels and averages.
    """
    owner_id = owner_id_from_user(current_user)
    return await crud.get_dashboard_kpis(db, owner_id, run_id=run_id)


@router.get("/risk-trends", response_model=schemas.RiskTrendsResponse)
async def get_risk_trends(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Shipment risk score delta vs. previous pipeline run using SQL LAG() window function.
    Identifies whether each shipment's risk INCREASED, DECREASED, remained STABLE, or is NEW.
    """
    owner_id = owner_id_from_user(current_user)
    trends = await crud.get_risk_trends(db, owner_id)
    return {"count": len(trends), "trends": trends}


@router.get("/corridors", response_model=schemas.CorridorExposureResponse)
async def get_corridor_exposure(
    min_assessments: int = Query(default=1, ge=1, description="Minimum assessments for corridor inclusion"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Highway corridor exposure ranking.
    Executes a 3-way SQL join (Shipments -> RiskAssessments -> Disruptions)
    aggregated by route_highway corridor with HAVING filter and composite ORDER BY.
    """
    owner_id = owner_id_from_user(current_user)
    corridors = await crud.get_corridor_exposure(db, owner_id, min_assessments=min_assessments)
    return {"corridors": corridors}


@router.get("/timeline", response_model=schemas.DisruptionTimelineResponse)
async def get_disruption_timeline(
    days: int = Query(default=7, ge=1, le=60, description="Number of past days to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Disruption event timeline across the specified past day window.
    Employs date_trunc and generate_series (or recursive CTE) to guarantee zero-filled days.
    """
    timeline = await crud.get_disruption_timeline(db, days=days)
    return {"days_analyzed": days, "timeline": timeline}
