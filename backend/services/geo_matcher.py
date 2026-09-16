"""
Geospatial Matcher — uses Haversine formula and Route Corridor projection
to match disruptions to active shipment routes (origin, transit corridor, destination).
"""

import math

CITY_COORDINATES = {
    "Chennai": (13.0827, 80.2707),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Bangalore": (12.9716, 77.5946),
    "Bengaluru": (12.9716, 77.5946),
    "Kolkata": (22.5726, 88.3639),
    "Hyderabad": (17.3850, 78.4867),
    "Pune": (18.5204, 73.8567),
    "Nagpur": (21.1458, 79.0882),
    "Kochi": (9.9312, 76.2673),
    "Patna": (25.5941, 85.1376),
    "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873),
    "Lucknow": (26.8467, 80.9462),
    "Surat": (21.1702, 72.8311),
    "Indore": (22.7196, 75.8577),
    "Chandigarh": (30.7333, 76.7794),
    "Madurai": (9.9252, 78.1198),
    "Coimbatore": (11.0168, 76.9558),
    "Bhubaneswar": (20.2961, 85.8245),
    "Agra": (27.1767, 78.0081),
    "Kanpur": (26.4499, 80.3319),
    "Varanasi": (25.3176, 82.9739),
    "Bhopal": (23.2599, 77.4126),
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def min_distance_to_route_corridor(
    d_lat: float,
    d_lon: float,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    num_samples: int = 10
) -> float:
    """
    Calculate the minimum distance from a disruption point to a shipment route corridor
    by sampling waypoints along the route segment from origin to destination.
    """
    min_dist = float("inf")
    for step in range(num_samples + 1):
        t = step / float(num_samples)
        wp_lat = origin_lat + t * (dest_lat - origin_lat)
        wp_lon = origin_lon + t * (dest_lon - origin_lon)
        dist = haversine_km(d_lat, d_lon, wp_lat, wp_lon)
        if dist < min_dist:
            min_dist = dist
    return min_dist


def match_disruptions_to_shipments(
    disruptions: list[dict],
    shipments: list[dict],
    radius_km: float = 120.0,
) -> list[dict]:
    """
    Match each disruption to shipments within radius_km of their origin, destination,
    or active transit route corridor.
    """
    matches = []
    for disruption in disruptions:
        d_lat = disruption.get("latitude") if disruption.get("latitude") is not None else disruption.get("lat")
        d_lon = disruption.get("longitude") if disruption.get("longitude") is not None else disruption.get("lon")
        if d_lat is None or d_lon is None:
            continue

        for shipment in shipments:
            s_lat = shipment.get("latitude")
            s_lon = shipment.get("longitude")
            if s_lat is None or s_lon is None:
                continue

            destination_city = shipment.get("destination", "")
            dest_coords = CITY_COORDINATES.get(destination_city)
            
            if dest_coords:
                dest_lat, dest_lon = dest_coords
                distance = min_distance_to_route_corridor(
                    d_lat, d_lon, s_lat, s_lon, dest_lat, dest_lon, num_samples=8
                )
            else:
                distance = haversine_km(d_lat, d_lon, s_lat, s_lon)

            if distance <= radius_km:
                matches.append(
                    {
                        "shipment": shipment,
                        "disruption": disruption,
                        "distance_km": round(distance, 1),
                    }
                )

    return matches


def compute_risk_score(
    disruption_severity: str,
    delivery_priority: str,
    distance_km: float,
    radius_km: float = 120.0,
) -> tuple[str, float]:
    """
    Compute numeric risk score and label based on:
    - disruption severity (HIGH=3, MEDIUM=2, LOW=1)
    - delivery priority (HIGH=3, MEDIUM=2, LOW=1)
    - proximity to route corridor (closer = higher risk)
    Returns (risk_level, score).
    """
    severity_weight = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(disruption_severity, 1)
    priority_weight = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(delivery_priority, 1)
    
    clamped_dist = min(distance_km, radius_km)
    proximity_factor = max(0.0, 1.0 - (clamped_dist / radius_km))

    score = severity_weight * priority_weight * proximity_factor

    if score >= 4.5:
        risk_level = "HIGH"
    elif score >= 1.8:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return risk_level, round(score, 2)

