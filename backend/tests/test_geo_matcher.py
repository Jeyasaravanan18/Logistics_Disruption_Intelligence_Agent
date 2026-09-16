from services.geo_matcher import compute_risk_score, haversine_km, match_disruptions_to_shipments


def test_haversine_same_point_is_zero():
    assert haversine_km(13.08, 80.27, 13.08, 80.27) == 0


def test_haversine_chennai_madurai_reasonable():
    dist = haversine_km(13.0827, 80.2707, 9.9252, 78.1198)
    assert 350 < dist < 500


def test_high_priority_close_disruption_is_high_risk():
    level, score = compute_risk_score("HIGH", "HIGH", distance_km=5, radius_km=150)
    assert level == "HIGH"
    assert score >= 4.5


def test_far_disruption_is_low_risk():
    level, score = compute_risk_score("LOW", "LOW", distance_km=140, radius_km=150)
    assert level == "LOW"
    assert score < 1.8


def test_match_uses_corridor_not_origin_only():
    shipments = [
        {
            "shipment_id": "S1",
            "origin": "Chennai",
            "destination": "Madurai",
            "latitude": 13.0827,
            "longitude": 80.2707,
        }
    ]
    disruptions = [
        {
            "id": "d1",
            "lat": 11.0,
            "lon": 79.2,
            "subtype": "Rain",
        }
    ]
    matches = match_disruptions_to_shipments(disruptions, shipments, radius_km=150)
    assert len(matches) == 1
    assert matches[0]["shipment"]["shipment_id"] == "S1"
