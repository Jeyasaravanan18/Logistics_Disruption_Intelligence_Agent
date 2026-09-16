"""
Agent 4: Recommendation Agent
Responsibility: Generates actionable recommendations for each at-risk shipment.

UPGRADED: Now uses LangChain LCEL pipeline with ChatGoogleGenerativeAI + JsonOutputParser.
Uses a tailor prompt with full shipment and disruption context. Falls back to rule templates.
"""

import os
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Rule-based recommendation templates per (risk_level, disruption_type)
RULE_TEMPLATES = {
    ("HIGH", "Heavy Rain"): (
        "Halt shipment and wait for weather clearance. "
        "Reroute via nearest alternative highway. "
        "Notify customer of 6-12 hour delay."
    ),
    ("HIGH", "Thunderstorm"): (
        "Suspend convoy movement immediately. Seek covered shelter at nearest truck bay. "
        "Inform customer of weather-induced delay. Resume only after storm advisory is lifted."
    ),
    ("HIGH", "Highway Closure"): (
        "Reroute via alternate highway immediately. "
        "Coordinate with fleet manager for updated ETAs. "
        "Notify customer with revised delivery window."
    ),
    ("HIGH", "Flooding"): (
        "Do NOT attempt flooded routes. Hold shipment at nearest secure facility. "
        "Activate emergency rerouting protocol. Notify customer with HIGH-priority delay alert."
    ),
    ("HIGH", "Cyclonic Rain"): (
        "Activate emergency reroute immediately. Do not operate vehicles in high-wind zones. "
        "Issue customer delay notification with cyclone advisory reference."
    ),
    ("HIGH", "Port Congestion"): (
        "Switch to road/rail alternative mode where possible. "
        "Escalate to senior logistics manager. Notify customer of 48-hour port delay."
    ),
    ("MEDIUM", "Dense Fog"): (
        "Reduce convoy speed and increase following distance. Enable additional lighting. "
        "Monitor visibility conditions every hour. Notify customer of possible 2-4 hour delay."
    ),
    ("MEDIUM", "Road Block"): (
        "Contact local transport authority for diversion details. "
        "Identify and pre-clear alternate route. Update customer ETA with 3-5 hour buffer."
    ),
    ("MEDIUM", "Port Congestion"): (
        "Monitor port status updates hourly. Explore pre-lodgment of documentation. "
        "Notify customer of possible 24-hour delay."
    ),
}

DEFAULT_TEMPLATES = {
    "HIGH": (
        "Immediate action required: Halt shipment and activate emergency reroute protocol. "
        "Notify customer immediately with revised ETA. Escalate to senior logistics manager."
    ),
    "MEDIUM": (
        "Monitor situation closely. Prepare alternate route options. "
        "Notify customer proactively with possible delay warning."
    ),
    "LOW": "Continue with caution. Monitor route conditions. No immediate customer notification required.",
    "SAFE": "No action required. Shipment is on track for on-time delivery.",
}

HIGHWAY_ALTERNATES = {
    "NH44": "NH75 or NH48", "NH48": "NH19 or NH27", "NH16": "NH16B or coastal route",
    "NH27": "NH30 or rail", "NH65": "NH765 or NH163", "NH544": "NH66 coastal route",
    "NH62": "SH25 via Barmer", "NH60": "NH61 or NH753A", "NH46": "NH347 or SH21",
    "NH19": "NH31 or rail",
}
DELAY_MAP = {"HIGH": 8, "MEDIUM": 3, "LOW": 1, "SAFE": 0}


def _rule_based_recommendation(risk_record: dict) -> dict:
    """Generate recommendation from rule templates (fallback)."""
    risk_level = risk_record.get("risk_level", "SAFE")
    disruption_type = risk_record.get("disruption_type", "")
    action = RULE_TEMPLATES.get(
        (risk_level, disruption_type), DEFAULT_TEMPLATES.get(risk_level, "Monitor shipment.")
    )
    delay = DELAY_MAP.get(risk_level, 0)
    return {
        **risk_record,
        "suggested_action": action,
        "alternate_route": HIGHWAY_ALTERNATES.get(risk_record.get("route_highway", ""), "Contact regional coordinator"),
        "estimated_delay_hours": delay,
        "customer_message": (
            f"Your shipment {risk_record.get('shipment_id')} from {risk_record.get('origin')} to "
            f"{risk_record.get('destination')} may experience a delay of ~{delay} hours "
            f"due to {risk_record.get('disruption_type', 'route disruption')} near "
            f"{risk_record.get('disruption_location', 'your route')}. We are monitoring the situation."
            if risk_level != "SAFE"
            else f"Your shipment {risk_record.get('shipment_id')} is on track for on-time delivery."
        ),
        "recommendation_by": "rule-based",
    }


from services.gemini_service import generate_gemini_json


async def generate_recommendations(risk_records: list[dict]) -> list[dict]:
    """
    Agent 4 main function: Generate recommendations for all risk records.
    Uses a single batch JSON prompt to Gemini 3.6 Flash for all at-risk shipments.
    100% quota-safe (1 API call total) and delivers rich, context-aware AI recommendations.
    SAFE shipments receive an on-track confirmation immediately.
    """
    if not risk_records:
        return []

    print(f"[RecommendationAgent] Processing recommendations for {len(risk_records)} shipments...", flush=True)

    has_gemini = bool(GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here")

    safe_records = [r for r in risk_records if r.get("risk_level") == "SAFE"]
    at_risk_records = [r for r in risk_records if r.get("risk_level") != "SAFE"]

    # Safe shipments get immediate confirmation
    results = [_rule_based_recommendation(r) for r in safe_records]

    if not at_risk_records or not has_gemini:
        results.extend([_rule_based_recommendation(r) for r in at_risk_records])
        return results

    print(f"[RecommendationAgent] Generating batch recommendations for {len(at_risk_records)} at-risk shipments via Gemini AI...", flush=True)

    prompt_items = []
    for r in at_risk_records:
        prompt_items.append({
            "shipment_id": r.get("shipment_id"),
            "route": f"{r.get('origin')} -> {r.get('destination')} via {r.get('route_highway')}",
            "cargo": f"{r.get('cargo_type')} ({r.get('delivery_priority')} priority)",
            "risk_level": r.get("risk_level"),
            "disruption": f"{r.get('disruption_type')} at {r.get('disruption_location')} ({r.get('distance_to_disruption_km')} km away)",
            "reason": r.get("reason"),
        })

    system_instruction = (
        "You are a senior logistics operations manager AI for Indian freight networks. "
        "Generate specific, actionable route recommendations for each at-risk shipment. "
        "Respond ONLY with valid JSON containing a key 'recommendations' with an array of objects."
    )
    prompt = f"""Generate expert route recommendations for these at-risk shipments:
{json.dumps(prompt_items, indent=2)}

Respond ONLY with this exact JSON structure:
{{
  "recommendations": [
    {{
      "shipment_id": "<matching shipment_id>",
      "suggested_action": "<specific 2-4 sentence action steps for the driver and operations team>",
      "alternate_route": "<specific alternate highway or diversion route, or 'No reroute needed'>",
      "estimated_delay_hours": <integer 1-72>,
      "customer_message": "<professional 1-2 sentence customer notification message>"
    }}
  ]
}}"""

    try:
        result = await generate_gemini_json(prompt, system_instruction)
        if result and "recommendations" in result and isinstance(result["recommendations"], list):
            lookup = {item["shipment_id"]: item for item in result["recommendations"] if "shipment_id" in item}
            for r in at_risk_records:
                ai_data = lookup.get(r.get("shipment_id"))
                if ai_data and "suggested_action" in ai_data:
                    results.append({**r, **ai_data, "recommendation_by": "gemini-1.5-flash"})
                else:
                    results.append(_rule_based_recommendation(r))
            print(f"[RecommendationAgent] Batch complete. {len(lookup)} recommendations generated by Gemini AI.", flush=True)
        else:
            print("[RecommendationAgent] Gemini batch format unexpected or unauthenticated, using rule fallback", flush=True)
            results.extend([_rule_based_recommendation(r) for r in at_risk_records])
    except Exception as e:
        print(f"[RecommendationAgent] Gemini batch failed ({e}), using rule fallback", flush=True)
        results.extend([_rule_based_recommendation(r) for r in at_risk_records])

    # Sort results: HIGH, MEDIUM, LOW, SAFE
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "SAFE": 3}
    results.sort(key=lambda x: order.get(x.get("risk_level"), 4))

    print(f"[RecommendationAgent] Done. {len(results)} total recommendations generated.", flush=True)
    return results

