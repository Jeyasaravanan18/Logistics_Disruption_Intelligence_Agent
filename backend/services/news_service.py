"""
News Service — fetches logistics disruption events in India.
Primary: Live RSS feed for Indian logistics, expressways, and roadblocks.
Secondary: GNews API if key provided.
Fallback / Demo: Loads recorded fixtures from data/fixtures/news_fixtures.json
when external network feeds fail or in demo environments, tagging them with data_source: "demo_fixture".
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")

LOCATION_KEYWORDS = {
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
    "Ranchi": (23.3441, 85.3096),
    "Gurugram": (28.4595, 77.0266),
    "Gurgaon": (28.4595, 77.0266),
    "Agra": (27.1767, 78.0081),
    "Kanpur": (26.4499, 80.3319),
    "Varanasi": (25.3176, 82.9739),
    "Bhopal": (23.2599, 77.4126),
}

HIGHWAY_KEYWORDS = {
    "NH44": (17.3850, 78.4867),
    "NH48": (21.1702, 72.8311),
    "NH16": (17.6868, 83.2185),
    "Yamuna Expressway": (27.5000, 77.7000),
    "Mumbai-Pune Expressway": (18.7500, 73.4000),
    "Samruddhi": (19.8762, 75.3433),
}

SEVERITY_KEYWORDS = {
    "HIGH": ["flood", "closure", "closed", "blocked", "blockade", "accident", "cyclone", "severe", "landslide", "strangled", "protest"],
    "MEDIUM": ["delay", "congestion", "slow", "disruption", "affected", "jam", "diversion", "agitation", "warning"],
    "LOW": ["minor", "light", "possible", "expected", "plan", "advisory"],
}


def _parse_text_to_disruption(
    title: str,
    description: str,
    url: str,
    pub_date_str: str,
    source_name: str,
    idx: int,
    data_source: str = "live_api",
) -> dict:
    content = f"{title} {description}".lower()

    detected_location = None
    lat, lon = 20.5937, 78.9629

    for city, coords in LOCATION_KEYWORDS.items():
        if city.lower() in content:
            detected_location = city
            lat, lon = coords
            break

    if not detected_location:
        for hwy, coords in HIGHWAY_KEYWORDS.items():
            if hwy.lower() in content:
                detected_location = hwy
                lat, lon = coords
                break

    severity = "MEDIUM"
    for level, keywords in SEVERITY_KEYWORDS.items():
        if any(kw in content for kw in keywords):
            severity = level
            break

    iso_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    if pub_date_str:
        try:
            iso_timestamp = parsedate_to_datetime(pub_date_str).strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            try:
                iso_timestamp = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                pass

    return {
        "id": f"N{100 + idx}",
        "type": "news",
        "subtype": "Traffic / Route Incident" if "accident" in content or "crash" in content else "Logistics Disruption",
        "location": detected_location or "National Highway (India)",
        "lat": lat,
        "lon": lon,
        "latitude": lat,
        "longitude": lon,
        "radius_km": 50,
        "severity": severity,
        "description": title[:220],
        "source": source_name if data_source == "live_api" else f"{source_name} (Demo Fixture)",
        "data_source": data_source,
        "url": url,
        "timestamp": iso_timestamp,
    }


def _load_news_fixtures() -> list[dict]:
    """Load recorded news fixtures from data/fixtures/news_fixtures.json."""
    fixtures_path = (
        Path(__file__).resolve().parent.parent.parent / "data" / "fixtures" / "news_fixtures.json"
    )
    if not fixtures_path.exists():
        return []

    try:
        with open(fixtures_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        disruptions = []
        for idx, item in enumerate(records):
            disruptions.append({
                "id": f"N-FIX-{100 + idx}",
                "type": "news",
                "subtype": "Roadway Incident",
                "location": item.get("location", "National Highway"),
                "lat": item.get("lat", 20.5937),
                "lon": item.get("lon", 78.9629),
                "latitude": item.get("lat", 20.5937),
                "longitude": item.get("lon", 78.9629),
                "radius_km": 50,
                "severity": item.get("severity", "MEDIUM"),
                "description": item.get("title", ""),
                "source": f"{item.get('source', 'Recorded News')} (Demo Fixture)",
                "data_source": "demo_fixture",
                "url": item.get("url", ""),
                "timestamp": item.get("pub_date", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")),
            })
        return disruptions
    except Exception as e:
        print(f"[NewsService] Failed to parse news fixtures: {e}")
        return []


async def fetch_news_disruptions() -> list[dict]:
    """
    Fetch logistics disruption news.
    Queries live RSS and GNews API. If network is unreachable or results are empty,
    falls back cleanly to recorded fixtures marked as 'demo_fixture'.
    """
    if os.getenv("DEMO_MODE", "").lower() in ("true", "1"):
        return _load_news_fixtures()

    disruptions = []
    seen_titles = set()

    # 1. Fetch live RSS from Google News
    rss_queries = [
        "highway+closure+OR+traffic+OR+accident+India+when:3d",
        "expressway+jam+OR+landslide+OR+flood+road+India+when:3d",
    ]

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        for q in rss_queries:
            url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    items = root.findall(".//item")
                    for item in items[:6]:
                        title = item.find("title").text if item.find("title") is not None else ""
                        link = item.find("link").text if item.find("link") is not None else ""
                        pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                        source_elem = item.find("source")
                        source = source_elem.text if source_elem is not None else "Google News (Live)"

                        if not title or title in seen_titles:
                            continue
                        seen_titles.add(title)

                        d = _parse_text_to_disruption(
                            title=title,
                            description="",
                            url=link,
                            pub_date_str=pub_date,
                            source_name=source,
                            idx=len(disruptions),
                            data_source="live_api",
                        )
                        disruptions.append(d)
            except Exception as e:
                print(f"[NewsService] Error fetching RSS query '{q}': {e}", flush=True)

    # 2. GNews API if key provided
    api_key = os.getenv("GNEWS_API_KEY", "").strip(' "\'')
    if api_key and api_key != "your_gnews_api_key_here":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://gnews.io/api/v4/search",
                    params={
                        "q": "highway closure India",
                        "lang": "en",
                        "country": "in",
                        "max": 5,
                        "apikey": api_key,
                    },
                )
                if resp.status_code == 200:
                    articles = resp.json().get("articles", [])
                    for article in articles:
                        title = article.get("title", "")
                        if not title or title in seen_titles:
                            continue
                        seen_titles.add(title)

                        d = _parse_text_to_disruption(
                            title=title,
                            description=article.get("description", ""),
                            url=article.get("url", ""),
                            pub_date_str=article.get("publishedAt", ""),
                            source_name=article.get("source", {}).get("name", "GNews Live"),
                            idx=len(disruptions),
                            data_source="live_api",
                        )
                        disruptions.append(d)
        except Exception as e:
            print(f"[NewsService] GNews supplement notice: {e}", flush=True)

    # If external queries yielded no items, fallback to fixtures
    if not disruptions:
        return _load_news_fixtures()

    return disruptions
