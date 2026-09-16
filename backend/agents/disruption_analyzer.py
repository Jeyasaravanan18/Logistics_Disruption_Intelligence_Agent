"""
Agent 2: Disruption Analysis Agent
Responsibility: Interprets each disruption, enriches severity, and extracts key attributes.

UPGRADED: Now uses LangChain LCEL pipeline with ChatGoogleGenerativeAI + JsonOutputParser
for structured, reliable AI reasoning with automatic fallback.
"""

import os
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Impact duration estimates per disruption subtype (hours)
IMPACT_DURATION_MAP = {
    "Heavy Rain": 6, "Thunderstorm": 4, "Dense Fog": 3,
    "Cyclonic Rain": 12, "Highway Closure": 8, "Flooding": 24,
    "Port Congestion": 48, "Road Block": 5, "Accident": 4,
    "Snow": 12, "Dust Storm": 3,
}

TRANSPORT_IMPACT_MAP = {
    "Heavy Rain": ["road", "rail"], "Thunderstorm": ["road", "air"],
    "Dense Fog": ["road", "air"], "Cyclonic Rain": ["road", "rail", "sea"],
    "Highway Closure": ["road"], "Flooding": ["road", "rail"],
    "Port Congestion": ["sea", "road"], "Road Block": ["road"],
}


def _rule_based_analysis(disruption: dict) -> dict:
    """Enrich disruption with rule-based impact estimates (fallback)."""
    subtype = disruption.get("subtype", "")
    severity = disruption.get("severity", "LOW")
    location = disruption.get("location", "Unknown")
    impact_duration = IMPACT_DURATION_MAP.get(subtype, 4)
    affected_transport = TRANSPORT_IMPACT_MAP.get(subtype, ["road"])
    severity_text = {
        "HIGH": "severe operational disruptions expected",
        "MEDIUM": "moderate delays and rerouting possible",
        "LOW": "minor impact, monitoring recommended",
    }.get(severity, "impact unknown")
    reasoning = (
        f"Disruption type '{subtype}' at {location} classified as {severity} severity. "
        f"Expected to impact {', '.join(affected_transport)} transport modes for ~{impact_duration}h. "
        f"Analysis: {severity_text}."
    )
    return {
        **disruption,
        "impact_duration_hours": impact_duration,
        "affected_transport_modes": affected_transport,
        "analysis_reasoning": reasoning,
        "analyzed_by": "rule-based",
    }


from services.gemini_service import generate_gemini_json


async def analyze_disruptions(disruptions: list[dict]) -> list[dict]:
    """
    Agent 2 main function: Analyze and enrich disruptions using Gemini 3.6 Flash.
    Uses batch JSON prompt: 1 single API call for all disruptions to strictly respect free quota.
    """
    if not disruptions:
        return []

    print(f"[DisruptionAnalyzerAgent] Analyzing {len(disruptions)} disruptions via Gemini AI (Single Batch Call)...", flush=True)

    has_gemini = bool(GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here")
    if not has_gemini:
        return [_rule_based_analysis(d) for d in disruptions]

    prompt_items = []
    for d in disruptions:
        prompt_items.append({
            "id": d.get("id"),
            "subtype": d.get("subtype"),
            "location": d.get("location"),
            "severity": d.get("severity"),
            "description": d.get("description"),
        })

    system_instruction = (
        "You are an expert logistics disruption analyst for Indian highway freight. "
        "Analyze the provided disruption events and return a JSON object with a key 'analyzed_disruptions' "
        "containing an array of objects matching each disruption."
    )
    prompt = f"""Analyze these active logistics disruptions:
{json.dumps(prompt_items, indent=2)}

Respond ONLY with this exact JSON structure:
{{
  "analyzed_disruptions": [
    {{
      "id": "<matching disruption id>",
      "impact_duration_hours": <integer 1-72>,
      "affected_transport_modes": ["road", "rail", "air", "sea"],
      "risk_factors": ["risk 1", "risk 2"],
      "analysis_reasoning": "<2-3 sentence expert analysis specific to the disruption>"
    }}
  ]
}}"""

    try:
        result = await generate_gemini_json(prompt, system_instruction)
        if result and "analyzed_disruptions" in result and isinstance(result["analyzed_disruptions"], list):
            lookup = {item["id"]: item for item in result["analyzed_disruptions"] if "id" in item}
            enriched = []
            for d in disruptions:
                ai_data = lookup.get(d.get("id"))
                if ai_data and "analysis_reasoning" in ai_data:
                    enriched.append({**d, **ai_data, "analyzed_by": "gemini-1.5-flash"})
                else:
                    enriched.append(_rule_based_analysis(d))
            print(f"[DisruptionAnalyzerAgent] Batch complete. {len(enriched)} disruptions enriched with Gemini AI.", flush=True)
            return enriched
        else:
            print("[DisruptionAnalyzerAgent] Gemini batch format unexpected or unauthenticated, applying rule fallback", flush=True)
            return [_rule_based_analysis(d) for d in disruptions]
    except Exception as e:
        print(f"[DisruptionAnalyzerAgent] Gemini batch call failed ({e}), applying rule fallback", flush=True)
        return [_rule_based_analysis(d) for d in disruptions]

