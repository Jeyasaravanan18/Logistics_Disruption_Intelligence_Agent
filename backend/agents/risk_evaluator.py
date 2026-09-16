"""
Agent 3: Shipment Risk Evaluation Agent
Responsibility: Matches analyzed disruptions to shipments and assigns risk levels with reasoning.
"""

import json
import os
from services.geo_matcher import match_disruptions_to_shipments, compute_risk_score

SHIPMENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "shipments.json")


def evaluate_shipment_risks(analyzed_disruptions: list[dict], shipments: list[dict]) -> list[dict]:
    """
    Agent 3 main function: Evaluate risk for every shipment against all disruptions.
    Produces a risk record per affected shipment.
    """
    print("[RiskEvaluatorAgent] Evaluating risks for shipments...")

    matches = match_disruptions_to_shipments(analyzed_disruptions, shipments, radius_km=150)

    # Build per-shipment worst-case risk (a shipment may be near multiple disruptions)
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
            radius_km=150,
        )

        highway = shipment.get("route_highway", "")
        reason = (
            f"{disruption.get('subtype', 'Disruption')} detected {distance_km}km from shipment origin "
            f"({shipment['origin']}). {disruption.get('description', '')} "
            f"Highway {highway} potentially impacted. "
            f"Cargo: {shipment.get('cargo_type', 'Unknown')} | Priority: {shipment['delivery_priority']}."
        )

        # Keep the highest-risk disruption per shipment
        if sid not in shipment_risks or score > shipment_risks[sid]["risk_score"]:
            shipment_risks[sid] = {
                "shipment_id": sid,
                "origin": shipment["origin"],
                "destination": shipment["destination"],
                "route_highway": highway,
                "cargo_type": shipment.get("cargo_type", ""),
                "delivery_priority": shipment["delivery_priority"],
                "estimated_delivery_time": shipment.get("estimated_delivery_time", ""),
                "latitude": shipment.get("latitude"),
                "longitude": shipment.get("longitude"),
                "risk_level": risk_level,
                "risk_score": score,
                "disruption_id": disruption.get("id", ""),
                "disruption_type": disruption.get("subtype", ""),
                "disruption_location": disruption.get("location", ""),
                "distance_to_disruption_km": distance_km,
                "reason": reason,
                "impact_duration_hours": disruption.get("impact_duration_hours", 4),
                "agent": "RiskEvaluatorAgent",
            }

    # Add safe shipments
    all_results = list(shipment_risks.values())
    affected_ids = set(shipment_risks.keys())
    for s in shipments:
        if s["shipment_id"] not in affected_ids:
            all_results.append(
                {
                    "shipment_id": s["shipment_id"],
                    "origin": s["origin"],
                    "destination": s["destination"],
                    "route_highway": s.get("route_highway", ""),
                    "cargo_type": s.get("cargo_type", ""),
                    "delivery_priority": s["delivery_priority"],
                    "estimated_delivery_time": s.get("estimated_delivery_time", ""),
                    "latitude": s.get("latitude"),
                    "longitude": s.get("longitude"),
                    "risk_level": "SAFE",
                    "risk_score": 0,
                    "disruption_id": None,
                    "disruption_type": None,
                    "disruption_location": None,
                    "distance_to_disruption_km": None,
                    "reason": "No active disruptions detected within 150km of this route.",
                    "impact_duration_hours": 0,
                    "agent": "RiskEvaluatorAgent",
                }
            )

    # Sort: HIGH first, then MEDIUM, LOW, SAFE
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "SAFE": 3}
    all_results.sort(key=lambda x: order.get(x["risk_level"], 4))

    print(
        f"[RiskEvaluatorAgent] Done. {len(affected_ids)} shipments at risk, "
        f"{len(shipments) - len(affected_ids)} safe."
    )
    return all_results
