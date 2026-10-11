"""
LangGraph Workflow Engine: Assembles and compiles the stateful LangGraph pipeline.
Defines nodes, conditional branching (review loop and recommendation filter),
and coordinates database persistence and telemetry trace logging.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

import crud
from models import PipelineRun
from workflow.nodes import (
    analyze_node,
    collect_news_node,
    collect_weather_node,
    persist_finish_node,
    plan_node,
    recommend_node,
    refine_loop_increment,
    score_node,
)
from workflow.state import WorkflowState


def after_score_decision(state: WorkflowState) -> str:
    """
    Conditional routing edge following risk scoring:
    1. If low-confidence classifications exceed 30% and retry counter < 2 -> 'refine_query' (loops back to news collection)
    2. Else if shipments exhibit HIGH or MEDIUM threat level -> 'recommend'
    3. Else (all SAFE/LOW shipments) -> bypass LLM and route directly to 'persist_finish'
    """
    if state.get("review_needed", False) and state.get("review_loop_count", 0) < 2:
        return "refine_query"
    if state.get("has_high_or_medium_risk", False):
        return "recommend"
    return "persist_finish"


def build_workflow_graph():
    """Construct and compile the LangGraph StateGraph."""
    builder = StateGraph(WorkflowState)

    # Register workflow nodes
    builder.add_node("plan", plan_node)
    builder.add_node("collect_weather", collect_weather_node)
    builder.add_node("collect_news", collect_news_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("score", score_node)
    builder.add_node("refine_query", refine_loop_increment)
    builder.add_node("recommend", recommend_node)
    builder.add_node("persist_finish", persist_finish_node)

    # Establish directed graph flow
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "collect_weather")
    builder.add_edge("collect_weather", "collect_news")
    builder.add_edge("collect_news", "analyze")
    builder.add_edge("analyze", "score")

    # Conditional branching following score
    builder.add_conditional_edges(
        "score",
        after_score_decision,
        {
            "refine_query": "refine_query",
            "recommend": "recommend",
            "persist_finish": "persist_finish",
        },
    )

    # Bounded review loop: returns from refine_query back to collect_news
    builder.add_edge("refine_query", "collect_news")

    # Recommendation path leads to finalize
    builder.add_edge("recommend", "persist_finish")
    builder.add_edge("persist_finish", END)

    return builder.compile()


# Pre-compiled workflow graph instance
compiled_workflow = build_workflow_graph()


async def execute_workflow(
    shipments: list[dict[str, Any]],
    owner_id: str = "default_operator",
    db: Optional[AsyncSession] = None,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Execute the stateful LangGraph workflow for freight disruption intelligence.
    Persists pipeline runs, deduplicated disruptions, risk assessments, and agent traces to SQL.
    """
    assigned_run_id = run_id or str(uuid.uuid4())

    # Create pipeline_runs record if DB session is supplied
    if db is not None:
        try:
            pipeline_run = PipelineRun(
                id=assigned_run_id,
                owner_id=owner_id,
                status="RUNNING",
            )
            db.add(pipeline_run)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            print(f"[WorkflowGraph] Notice: could not record initial pipeline_run ({exc})")

    initial_state: WorkflowState = {
        "run_id": assigned_run_id,
        "owner_id": owner_id,
        "shipments": shipments,
        "plan": {},
        "raw_weather": [],
        "raw_news": [],
        "collected_disruptions": [],
        "analyzed_disruptions": [],
        "low_confidence_ratio": 0.0,
        "review_loop_count": 0,
        "review_needed": False,
        "risk_assessments": [],
        "risk_breakdown": {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "SAFE": 0},
        "has_high_or_medium_risk": False,
        "recommendations": [],
        "traces": [],
        "pipeline_status": "RUNNING",
        "error": None,
    }

    # Execute LangGraph ainvoke
    final_state = await compiled_workflow.ainvoke(initial_state)

    # Persist outputs to SQL if DB session is provided
    if db is not None:
        try:
            # 1. Upsert disruptions
            if final_state["analyzed_disruptions"]:
                await crud.upsert_disruptions(db, final_state["analyzed_disruptions"])

            # 2. Persist assessments & recommendations
            if final_state["recommendations"]:
                await crud.save_pipeline_results(db, assigned_run_id, final_state["recommendations"])

            # 3. Persist agent telemetry traces
            if final_state["traces"]:
                await crud.save_agent_traces(db, assigned_run_id, final_state["traces"])

            # 4. Update PipelineRun record
            rb = final_state["risk_breakdown"]
            await crud.update_pipeline_run(
                db,
                assigned_run_id,
                disruptions_count=len(final_state["analyzed_disruptions"]),
                shipments_count=len(final_state["recommendations"]),
                high_count=rb.get("HIGH", 0),
                medium_count=rb.get("MEDIUM", 0),
                low_count=rb.get("LOW", 0),
                safe_count=rb.get("SAFE", 0),
                status="COMPLETED",
                reasoning=final_state["plan"].get("reasoning", "Completed stateful workflow."),
            )
        except Exception as exc:
            await db.rollback()
            print(f"[WorkflowGraph] Database persistence warning: {exc}")

    return {
        "pipeline": {
            "run_id": assigned_run_id,
            "disruptions_collected": len(final_state["analyzed_disruptions"]),
            "shipments_evaluated": len(final_state["recommendations"]),
            "risk_breakdown": final_state["risk_breakdown"],
            "collector_reasoning": final_state["plan"].get("reasoning", "Completed stateful workflow."),
            "traces": final_state["traces"],
        },
        "recommendations": final_state["recommendations"],
    }
