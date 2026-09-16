from datetime import datetime

from agents.data_collector import collect_disruptions
from agents.disruption_analyzer import analyze_disruptions
from agents.recommendation import generate_recommendations
from agents.risk_evaluator import evaluate_shipment_risks


def serialize_shipment(doc: dict) -> dict:
    edt = doc.get("estimated_delivery_time")
    if isinstance(edt, datetime):
        edt = edt.isoformat()
    return {
        "shipment_id": doc.get("shipment_id"),
        "origin": doc.get("origin"),
        "destination": doc.get("destination"),
        "route_highway": doc.get("route_highway"),
        "cargo_type": doc.get("cargo_type"),
        "delivery_priority": doc.get("delivery_priority"),
        "estimated_delivery_time": edt,
        "latitude": doc.get("latitude"),
        "longitude": doc.get("longitude"),
        "weight_kg": doc.get("weight_kg"),
    }


async def run_pipeline(shipments_raw: list[dict]) -> dict:
    collected = await collect_disruptions()
    analyzed = await analyze_disruptions(collected["disruptions"])
    shipments = [serialize_shipment(s) for s in shipments_raw]
    risk_records = evaluate_shipment_risks(analyzed, shipments)
    recommendations = await generate_recommendations(risk_records)

    risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "SAFE": 0}
    for rec in recommendations:
        level = rec.get("risk_level", "SAFE")
        risk_counts[level] = risk_counts.get(level, 0) + 1

    return {
        "pipeline": {
            "disruptions_collected": len(analyzed),
            "shipments_evaluated": len(recommendations),
            "risk_breakdown": risk_counts,
            "collector_reasoning": collected.get("reasoning", ""),
        },
        "recommendations": recommendations,
    }
