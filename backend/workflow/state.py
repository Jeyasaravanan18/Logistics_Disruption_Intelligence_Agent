"""
Typed state and Pydantic schemas for the LangGraph disruption intelligence workflow.
Enforces typed schemas across all nodes in the stateful workflow.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, Optional, TypedDict
from pydantic import BaseModel, Field


class CollectorPlan(BaseModel):
    """Execution plan determined by the plan node."""
    collectors: list[str] = Field(default_factory=lambda: ["weather", "news"])
    target_cities: list[str] = Field(default_factory=lambda: ["Chennai", "Mumbai", "Delhi", "Bangalore"])
    search_keywords: list[str] = Field(default_factory=lambda: ["highway closure", "flood", "protest", "strike"])
    reasoning: str = "Deterministic regional coverage based on active shipment origins/destinations."


class NewsClassification(BaseModel):
    """Structured LLM classification for an individual news event."""
    id: str
    subtype: str
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    location: str
    lat: float
    lon: float
    confidence: float = Field(ge=0.0, le=1.0)
    impact_duration_hours: int = Field(default=4, ge=1, le=72)
    summary: str


class WorkflowTrace(TypedDict):
    """Telemetry record captured for each node execution."""
    node: str
    started_at: str
    duration_ms: float
    input_hash: Optional[str]
    output_summary: str
    used_llm: bool
    fallback_used: bool
    tokens_estimate: int
    error: Optional[str]


class WorkflowState(TypedDict):
    """
    Central state container passed between LangGraph nodes.
    Maintains telemetry traces, signal collections, risk assessments, and loop counters.
    """
    run_id: str
    owner_id: str
    shipments: list[dict[str, Any]]
    
    # Planning
    plan: dict[str, Any]
    
    # Collection
    raw_weather: list[dict[str, Any]]
    raw_news: list[dict[str, Any]]
    collected_disruptions: list[dict[str, Any]]
    
    # Analysis & Review Loop
    analyzed_disruptions: list[dict[str, Any]]
    low_confidence_ratio: float
    review_loop_count: int
    review_needed: bool
    
    # Risk Scoring
    risk_assessments: list[dict[str, Any]]
    risk_breakdown: dict[str, int]
    has_high_or_medium_risk: bool
    
    # Recommendations
    recommendations: list[dict[str, Any]]
    
    # Telemetry and Execution Status
    traces: Annotated[list[WorkflowTrace], operator.add]
    pipeline_status: str
    error: Optional[str]
