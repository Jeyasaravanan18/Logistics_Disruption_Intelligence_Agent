"""
Workflow Nodes: Individual execution steps in the LangGraph intelligence pipeline.
Implements planning, weather collection, news collection, LLM analysis with validation retry,
deterministic corridor risk scoring, bounded review loop, and conditional recommendation.
Every node records typed telemetry traces for full observability.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from config import (
    DEFAULT_RADIUS_KM,
    RISK_THRESHOLD_HIGH,
    RISK_THRESHOLD_MEDIUM,
)
from services.gemini_service import generate_gemini_json
from services.geo_matcher import compute_risk_score, match_disruptions_to_shipments
from services.news_service import LOCATION_KEYWORDS, fetch_news_disruptions
from services.weather_service import MONITORED_CITIES, fetch_weather_disruptions
from workflow.state import (
    CollectorPlan,
    NewsClassification,
    WorkflowState,
    WorkflowTrace,
)

ALLOWED_COLLECTORS = {"weather", "news"}
ALLOWED_CITIES = set(c["name"] for c in MONITORED_CITIES).union(set(LOCATION_KEYWORDS.keys()))


def _hash_input(data: Any) -> str:
    """Generate SHA-256 fingerprint for node input tracking."""
    dumped = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]


# ============================================================================
# 1. Plan Node
# ============================================================================


async def plan_node(state: WorkflowState) -> dict[str, Any]:
    """
    LLM Planning Step:
    Analyzes active shipment corridors and plans targeted collectors and query targets.
    Validates plan against allowlist; defaults to deterministic regional plan on failure.
    """
    t0 = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    shipments = state.get("shipments", [])
    input_hash = _hash_input(shipments)

    # Extract target regions from active shipments
    target_regions = set()
    for s in shipments:
        if s.get("origin"):
            target_regions.add(s["origin"])
        if s.get("destination"):
            target_regions.add(s["destination"])

    matched_cities = [c for c in target_regions if c in ALLOWED_CITIES]
    if not matched_cities:
        matched_cities = ["Chennai", "Mumbai", "Delhi", "Bangalore"]

    # Attempt LLM-directed plan
    prompt = f"""You are a logistics dispatch coordinator.
Active freight corridors involve these Indian regions: {matched_cities}.
Choose:
1. Which collectors to run (choose from: ["weather", "news"])
2. Specific target cities from: {matched_cities}
3. 3-4 news search keywords to detect freight bottlenecks (e.g. "highway closure", "flood", "strike", "monsoon")
Return a JSON object with:
{{
  "collectors": ["weather", "news"],
  "target_cities": [...],
  "search_keywords": [...],
  "reasoning": "..."
}}
"""
    used_llm = False
    fallback_used = False
    plan_dict = None

    try:
        raw_plan = await generate_gemini_json(prompt, system_instruction="Respond with valid JSON only.")
        if raw_plan:
            validated = CollectorPlan(**raw_plan)
            # Validate against allowlist
            valid_collectors = [c for c in validated.collectors if c in ALLOWED_COLLECTORS]
            valid_cities = [c for c in validated.target_cities if c in ALLOWED_CITIES]
            if valid_collectors and valid_cities:
                plan_dict = {
                    "collectors": valid_collectors,
                    "target_cities": valid_cities,
                    "search_keywords": validated.search_keywords,
                    "reasoning": validated.reasoning,
                }
                used_llm = True
    except Exception as exc:
        print(f"[PlanNode] LLM planning failed: {exc}. Using deterministic fallback.")

    if not plan_dict:
        fallback_used = True
        plan_dict = {
            "collectors": ["weather", "news"],
            "target_cities": matched_cities[:5],
            "search_keywords": ["highway closure", "flood", "protest", "strike"],
            "reasoning": f"Deterministic fallback covering {len(matched_cities)} active shipment hubs.",
        }

    duration_ms = round((time.time() - t0) * 1000, 2)
    trace: WorkflowTrace = {
        "node": "plan",
        "started_at": started_at,
        "duration_ms": duration_ms,
        "input_hash": input_hash,
        "output_summary": f"Targeting {len(plan_dict['target_cities'])} cities with {plan_dict['collectors']}",
        "used_llm": used_llm,
        "fallback_used": fallback_used,
        "tokens_estimate": 180 if used_llm else 0,
        "error": None,
    }

    return {"plan": plan_dict, "traces": [trace]}


# ============================================================================
# 2. Collect Weather Node
# ============================================================================


async def collect_weather_node(state: WorkflowState) -> dict[str, Any]:
    """
    Weather Collection Step:
    Tool calls to OpenWeatherMap API for planned hubs with backoff retry.
    Deduplicates and assigns SHA-256 content hashes.
    """
    t0 = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    plan = state.get("plan", {})
    collectors = plan.get("collectors", ["weather"])

    weather_items = []
    error = None

    if "weather" in collectors:
        try:
            weather_items = await fetch_weather_disruptions()
        except Exception as exc:
            error = str(exc)
            print(f"[CollectWeatherNode] Weather collection warning: {exc}")

    # Standardize content_hash and unified radius
    processed_weather = []
    for d in weather_items:
        loc = d.get("location", "Unknown")
        sub = d.get("subtype", "Weather")
        raw_str = f"weather:{loc}:{sub}:{d.get('timestamp', '')}"
        content_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
        d_clean = {
            **d,
            "radius_km": DEFAULT_RADIUS_KM,
            "content_hash": content_hash,
        }
        processed_weather.append(d_clean)

    duration_ms = round((time.time() - t0) * 1000, 2)
    trace: WorkflowTrace = {
        "node": "collect_weather",
        "started_at": started_at,
        "duration_ms": duration_ms,
        "input_hash": _hash_input(plan.get("target_cities", [])),
        "output_summary": f"Collected {len(processed_weather)} atmospheric disruption signals",
        "used_llm": False,
        "fallback_used": False,
        "tokens_estimate": 0,
        "error": error,
    }

    return {"raw_weather": processed_weather, "traces": [trace]}


# ============================================================================
# 3. Collect News Node
# ============================================================================


async def collect_news_node(state: WorkflowState) -> dict[str, Any]:
    """
    News Collection Step:
    Tool calls to RSS / GNews for planned freight corridors.
    Assigns content hashes for disruption deduplication.
    """
    t0 = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    plan = state.get("plan", {})
    collectors = plan.get("collectors", ["news"])

    news_items = []
    error = None

    if "news" in collectors:
        try:
            news_items = await fetch_news_disruptions()
        except Exception as exc:
            error = str(exc)
            print(f"[CollectNewsNode] News collection warning: {exc}")

    processed_news = []
    for d in news_items:
        loc = d.get("location", "India")
        title = d.get("title") or d.get("description", "Incident")
        raw_str = f"news:{loc}:{title}"
        content_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
        d_clean = {
            **d,
            "radius_km": DEFAULT_RADIUS_KM,
            "content_hash": content_hash,
        }
        processed_news.append(d_clean)

    duration_ms = round((time.time() - t0) * 1000, 2)
    trace: WorkflowTrace = {
        "node": "collect_news",
        "started_at": started_at,
        "duration_ms": duration_ms,
        "input_hash": _hash_input(plan.get("search_keywords", [])),
        "output_summary": f"Collected {len(processed_news)} live news disturbance signals",
        "used_llm": False,
        "fallback_used": False,
        "tokens_estimate": 0,
        "error": error,
    }

    return {"raw_news": processed_news, "traces": [trace]}


# ============================================================================
# 4. Analyze Node (with Pydantic validation & retry feedback)
# ============================================================================


async def analyze_node(state: WorkflowState) -> dict[str, Any]:
    """
    LLM Analysis Step:
    Classifies raw items with structured output (severity, region, confidence).
    Validates with Pydantic; retries up to 2 times feeding back validation errors.
    Falls back to deterministic rule-based analysis if validation fails or LLM is offline.
    """
    t0 = time.time()
    started_at = datetime.now(timezone.utc).isoformat()

    all_raw = state.get("raw_weather", []) + state.get("raw_news", [])
    # Deduplicate raw items by content_hash
    unique_items: dict[str, dict] = {}
    for item in all_raw:
        h = item.get("content_hash") or _hash_input(item)
        if h not in unique_items:
            unique_items[h] = item

    collected = list(unique_items.values())
    used_llm = False
    fallback_used = False
    analyzed_list = []
    error = None

    # Evaluate each item or batch
    for item in collected:
        # Weather is already quantified with meteorological thresholds
        if item.get("type") == "weather":
            item_clean = {
                **item,
                "confidence": 0.95,
                "impact_duration_hours": item.get("impact_duration_hours", 6),
                "analyzed_by": "meteorological_rules",
            }
            analyzed_list.append(item_clean)
            continue

        # News item: classify with LLM and validate with Pydantic
        classified = None
        last_val_err = ""
        for attempt in range(2):  # up to 2 attempts with validation error feedback
            feedback = f" Note: Previous attempt failed validation with error: {last_val_err}" if last_val_err else ""
            prompt = f"""Classify this logistics news event into structured format.{feedback}
Headline: {item.get('title', '')}
Snippet: {item.get('description', '')}
Reported Location: {item.get('location', '')}

Respond ONLY with this JSON:
{{
  "id": "{item.get('id', 'N1')}",
  "subtype": "<e.g. Highway Closure, Flood, Strike, Accident, Protest>",
  "severity": "<HIGH or MEDIUM or LOW>",
  "location": "<City or Highway>",
  "lat": {item.get('lat', 13.0)},
  "lon": {item.get('lon', 80.0)},
  "confidence": <float between 0.0 and 1.0>,
  "impact_duration_hours": <integer 1-72>,
  "summary": "<1-sentence operational summary>"
}}"""
            try:
                raw_json = await generate_gemini_json(prompt, system_instruction="Output valid JSON matching schema.")
                if raw_json:
                    val = NewsClassification(**raw_json)
                    classified = val.model_dump()
                    used_llm = True
                    break
            except ValidationError as val_err:
                last_val_err = str(val_err)
            except Exception as exc:
                last_val_err = str(exc)
                break

        if classified:
            analyzed_list.append({
                **item,
                **classified,
                "radius_km": DEFAULT_RADIUS_KM,
                "analyzed_by": "gemini_structured",
            })
        else:
            # Deterministic rule-based fallback
            fallback_used = True
            analyzed_list.append({
                **item,
                "confidence": 0.85,
                "impact_duration_hours": item.get("impact_duration_hours", 4),
                "analyzed_by": "rule-based",
            })

    # Evaluate confidence metrics for the review loop
    low_confidence = [d for d in analyzed_list if float(d.get("confidence", 1.0)) < 0.6]
    low_conf_ratio = len(low_confidence) / max(1, len(analyzed_list))
    current_loops = state.get("review_loop_count", 0)
    review_needed = (low_conf_ratio > 0.3) and (current_loops < 2)

    duration_ms = round((time.time() - t0) * 1000, 2)
    trace: WorkflowTrace = {
        "node": "analyze",
        "started_at": started_at,
        "duration_ms": duration_ms,
        "input_hash": _hash_input([d.get("id") for d in collected]),
        "output_summary": f"Analyzed {len(analyzed_list)} signals (low confidence share: {low_conf_ratio:.1%})",
        "used_llm": used_llm,
        "fallback_used": fallback_used,
        "tokens_estimate": 250 * len(collected) if used_llm else 0,
        "error": error,
    }

    return {
        "collected_disruptions": collected,
        "analyzed_disruptions": analyzed_list,
        "low_confidence_ratio": low_conf_ratio,
        "review_needed": review_needed,
        "traces": [trace],
    }


# ============================================================================
# 5. Score Node (Deterministic Corridor & Haversine Scoring)
# ============================================================================


async def score_node(state: WorkflowState) -> dict[str, Any]:
    """
    Deterministic Risk Scoring Step:
    Cross-references analyzed disruptions with shipment corridors using Haversine formulas.
    Employs unified configuration thresholds (HIGH >= 4.5, MEDIUM >= 1.8).
    """
    t0 = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    analyzed = state.get("analyzed_disruptions", [])
    shipments = state.get("shipments", [])

    matches = match_disruptions_to_shipments(analyzed, shipments, radius_km=DEFAULT_RADIUS_KM)
    shipment_risks: dict[str, dict] = {}

    for match in matches:
        shipment = match["shipment"]
        disruption = match["disruption"]
        distance_km = match["distance_km"]
        sid = shipment["shipment_id"]

        risk_level, score = compute_risk_score(
            disruption_severity=disruption.get("severity", "LOW"),
            delivery_priority=shipment.get("delivery_priority", "LOW"),
            distance_km=distance_km,
            radius_km=DEFAULT_RADIUS_KM,
        )

        highway = shipment.get("route_highway", "")
        reason = (
            f"{disruption.get('subtype', 'Disruption')} detected {distance_km}km from origin/corridor "
            f"({shipment['origin']} -> {shipment['destination']}). Corridor {highway} impacted. "
            f"Cargo: {shipment.get('cargo_type', 'General')} | Priority: {shipment['delivery_priority']}."
        )

        if sid not in shipment_risks or score > shipment_risks[sid]["risk_score"]:
            shipment_risks[sid] = {
                "shipment_id": sid,
                "origin": shipment["origin"],
                "destination": shipment["destination"],
                "route_highway": highway,
                "cargo_type": shipment.get("cargo_type", ""),
                "delivery_priority": shipment["delivery_priority"],
                "risk_level": risk_level,
                "risk_score": score,
                "disruption_id": disruption.get("id", ""),
                "disruption_type": disruption.get("subtype", ""),
                "disruption_location": disruption.get("location", ""),
                "distance_to_disruption_km": distance_km,
                "reason": reason,
                "impact_duration_hours": disruption.get("impact_duration_hours", 4),
            }

    # Add SAFE records for unaffected shipments
    affected_ids = set(shipment_risks.keys())
    for s in shipments:
        sid = s["shipment_id"]
        if sid not in affected_ids:
            shipment_risks[sid] = {
                "shipment_id": sid,
                "origin": s["origin"],
                "destination": s["destination"],
                "route_highway": s.get("route_highway", ""),
                "cargo_type": s.get("cargo_type", ""),
                "delivery_priority": s["delivery_priority"],
                "risk_level": "SAFE",
                "risk_score": 0.0,
                "disruption_id": None,
                "disruption_type": None,
                "disruption_location": None,
                "distance_to_disruption_km": None,
                "reason": f"No active weather or news disruption within {DEFAULT_RADIUS_KM}km corridor.",
                "impact_duration_hours": 0,
            }

    assessments = list(shipment_risks.values())
    risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "SAFE": 0}
    baseline_recommendations = []
    for a in assessments:
        lvl = a["risk_level"]
        risk_counts[lvl] = risk_counts.get(lvl, 0) + 1
        baseline_recommendations.append({
            **a,
            "suggested_action": "Continue route on nominal schedule",
            "alternate_route": None,
            "estimated_delay_hours": 0,
            "customer_message": "Shipment on schedule for on-time delivery.",
            "recommendation_by": "deterministic_rules",
        })

    has_high_or_med = (risk_counts["HIGH"] + risk_counts["MEDIUM"]) > 0

    duration_ms = round((time.time() - t0) * 1000, 2)
    trace: WorkflowTrace = {
        "node": "score",
        "started_at": started_at,
        "duration_ms": duration_ms,
        "input_hash": _hash_input([s["shipment_id"] for s in shipments]),
        "output_summary": f"Scored {len(assessments)} targets: HIGH={risk_counts['HIGH']}, MED={risk_counts['MEDIUM']}, LOW={risk_counts['LOW']}, SAFE={risk_counts['SAFE']}",
        "used_llm": False,
        "fallback_used": False,
        "tokens_estimate": 0,
        "error": None,
    }

    return {
        "risk_assessments": assessments,
        "recommendations": baseline_recommendations,
        "risk_breakdown": risk_counts,
        "has_high_or_medium_risk": has_high_or_med,
        "traces": [trace],
    }


# ============================================================================
# 6. Review Condition (Conditional Edge Logic)
# ============================================================================


def review_condition(state: WorkflowState) -> str:
    """
    Bounded review loop:
    If low-confidence classifications exceed 30% and retry counter < 2,
    loops back to refine search queries; otherwise proceeds to recommendation check.
    """
    if state.get("review_needed", False) and state.get("review_loop_count", 0) < 2:
        return "refine_and_collect"
    return "check_recommend"


def refine_loop_increment(state: WorkflowState) -> dict[str, Any]:
    """Increment review loop counter and narrow search keywords."""
    curr = state.get("review_loop_count", 0) + 1
    plan = state.get("plan", {})
    # Narrow queries with specific terms
    refined_keywords = [f"urgent {k}" for k in plan.get("search_keywords", [])]
    return {
        "review_loop_count": curr,
        "review_needed": False,
        "plan": {**plan, "search_keywords": refined_keywords},
    }


def recommendation_condition(state: WorkflowState) -> str:
    """
    Conditional branching:
    Only invokes LLM recommendations if shipments exhibit HIGH or MEDIUM risk.
    Bypasses LLM for nominal/SAFE shipments to conserve quota and minimize latency.
    """
    if state.get("has_high_or_medium_risk", False):
        return "recommend"
    return "persist_finish"


# ============================================================================
# 7. Recommend Node (Batch LLM with Rule Template Fallback)
# ============================================================================


async def recommend_node(state: WorkflowState) -> dict[str, Any]:
    """
    Recommendation Step:
    Runs ONLY for shipments with HIGH or MEDIUM risk.
    Batches prompts to respect quota; falls back to deterministic rule templates.
    """
    t0 = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    assessments = state.get("risk_assessments", [])

    at_risk = [a for a in assessments if a["risk_level"] in ("HIGH", "MEDIUM")]
    safe_or_low = [a for a in assessments if a["risk_level"] not in ("HIGH", "MEDIUM")]

    recommendations = []
    used_llm = False
    fallback_used = False

    # Batch prompt Gemini for at-risk shipments
    prompt_payload = [
        {
            "shipment_id": a["shipment_id"],
            "origin": a["origin"],
            "destination": a["destination"],
            "route_highway": a["route_highway"],
            "risk_level": a["risk_level"],
            "disruption_type": a["disruption_type"],
            "distance_km": a.get("distance_to_disruption_km"),
        }
        for a in at_risk
    ]

    llm_recs = None
    if at_risk:
        prompt = f"""Provide proactive rerouting advice for these at-risk shipments in India:
{json.dumps(prompt_payload, indent=2)}

Return a JSON array of objects:
[
  {{
    "shipment_id": "<id>",
    "suggested_action": "<Clear operational directive, e.g. Reroute via NH48>",
    "alternate_route": "<Alternate highway corridor or None>",
    "estimated_delay_hours": <integer>,
    "customer_message": "<Professional 1-sentence customer notification>"
  }}
]"""
        try:
            raw = await generate_gemini_json(prompt, system_instruction="Output valid JSON array.")
            if isinstance(raw, list):
                llm_recs = {r["shipment_id"]: r for r in raw if "shipment_id" in r}
                used_llm = True
        except Exception as exc:
            print(f"[RecommendNode] LLM recommendation failed: {exc}. Using rule templates.")

    # Assemble recommendations
    for a in at_risk:
        sid = a["shipment_id"]
        if llm_recs and sid in llm_recs:
            rec_item = {
                **a,
                **llm_recs[sid],
                "recommendation_by": "gemini_batch",
            }
        else:
            fallback_used = True
            rec_item = {
                **a,
                "suggested_action": "Activate emergency corridor detour" if a["risk_level"] == "HIGH" else "Proceed with 20% speed reduction and monitor",
                "alternate_route": "NH48 Detour" if a["risk_level"] == "HIGH" else None,
                "estimated_delay_hours": 6 if a["risk_level"] == "HIGH" else 2,
                "customer_message": f"Notice: Expected delay on corridor {a['route_highway']} due to {a['disruption_type'] or 'transit advisory'}.",
                "recommendation_by": "rule_templates",
            }
        recommendations.append(rec_item)

    # Add standard recommendations for SAFE / LOW shipments without LLM
    for a in safe_or_low:
        recommendations.append({
            **a,
            "suggested_action": "Continue route on nominal schedule",
            "alternate_route": None,
            "estimated_delay_hours": 0,
            "customer_message": "Shipment on schedule for on-time delivery.",
            "recommendation_by": "deterministic_rules",
        })

    duration_ms = round((time.time() - t0) * 1000, 2)
    trace: WorkflowTrace = {
        "node": "recommend",
        "started_at": started_at,
        "duration_ms": duration_ms,
        "input_hash": _hash_input([a["shipment_id"] for a in at_risk]),
        "output_summary": f"Generated advice for {len(at_risk)} at-risk targets ({len(recommendations)} total)",
        "used_llm": used_llm,
        "fallback_used": fallback_used,
        "tokens_estimate": 300 if used_llm else 0,
        "error": None,
    }

    return {"recommendations": recommendations, "traces": [trace]}


# ============================================================================
# 8. Persist / Finish Node
# ============================================================================


async def persist_finish_node(state: WorkflowState) -> dict[str, Any]:
    """
    Finalize Workflow:
    Closes the pipeline run state, compiles trace log, and marks status COMPLETED.
    """
    t0 = time.time()
    started_at = datetime.now(timezone.utc).isoformat()

    duration_ms = round((time.time() - t0) * 1000, 2)
    trace: WorkflowTrace = {
        "node": "persist_finish",
        "started_at": started_at,
        "duration_ms": duration_ms,
        "input_hash": state.get("run_id", "run_id"),
        "output_summary": f"Finalized stateful workflow run {state.get('run_id')}",
        "used_llm": False,
        "fallback_used": False,
        "tokens_estimate": 0,
        "error": None,
    }

    return {"pipeline_status": "COMPLETED", "traces": [trace]}
