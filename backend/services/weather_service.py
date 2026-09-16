"""
Weather Service — fetches live real-time weather disruptions across Indian hubs via OpenWeatherMap API.
Strictly real-time data only (synthetic data disabled for production).
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# Key Indian logistics hubs to monitor
MONITORED_CITIES = [
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    {"name": "Delhi", "lat": 28.6139, "lon": 77.2090},
    {"name": "Bangalore", "lat": 12.9716, "lon": 77.5946},
    {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    {"name": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
    {"name": "Pune", "lat": 18.5204, "lon": 73.8567},
    {"name": "Ahmedabad", "lat": 23.0225, "lon": 72.5714},
    {"name": "Nagpur", "lat": 21.1458, "lon": 79.0882},
    {"name": "Kochi", "lat": 9.9312, "lon": 76.2673},
]

WEATHER_SEVERITY_MAP = {
    "Thunderstorm": "HIGH",
    "Drizzle": "MEDIUM",
    "Rain": "MEDIUM",
    "Snow": "HIGH",
    "Fog": "MEDIUM",
    "Mist": "LOW",
    "Haze": "LOW",
    "Dust": "MEDIUM",
    "Sand": "MEDIUM",
    "Ash": "HIGH",
    "Squall": "HIGH",
    "Tornado": "HIGH",
    "Extreme": "HIGH",
    "Smoke": "MEDIUM",
    "Clear": "LOW",
    "Clouds": "LOW",
}


def _map_weather_to_disruption(city: dict, weather_data: dict) -> dict | None:
    """Convert OpenWeatherMap API response to unified disruption dict with meteorological thresholds."""
    from datetime import datetime, timezone
    
    main = weather_data.get("weather", [{}])[0].get("main", "Clear")
    desc = weather_data.get("weather", [{}])[0].get("description", "")
    
    temp = weather_data.get("main", {}).get("temp", 25)
    humidity = weather_data.get("main", {}).get("humidity", 50)
    wind_speed = weather_data.get("wind", {}).get("speed", 0)

    # Dynamic severity adjustment based on live atmospheric data
    severity = WEATHER_SEVERITY_MAP.get(main, "LOW")
    subtype = f"{main} / {desc.title()}"

    if wind_speed >= 12.0:
        severity = "HIGH"
        subtype = f"High Winds ({wind_speed} m/s) / {main}"
    elif isinstance(temp, (int, float)) and temp >= 40.0:
        severity = "MEDIUM"
        subtype = f"Extreme Heat ({temp}°C) / {main}"

    dt_val = weather_data.get("dt")
    if dt_val:
        ts = datetime.fromtimestamp(dt_val, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    else:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    is_nominal = main in ["Clear", "Clouds"] and severity == "LOW"
    description = (
        f"{desc.title()} in {city['name']}. "
        f"Temp: {temp}°C, Humidity: {humidity}%, Wind: {wind_speed} m/s. "
        f"{'Transit conditions normal.' if is_nominal else 'Potential impact on road freight transit.'}"
    )

    return {
        "id": f"W-{city['name'][:3].upper()}",
        "type": "weather",
        "subtype": subtype,
        "location": city["name"],
        "lat": city["lat"],
        "lon": city["lon"],
        "latitude": city["lat"],
        "longitude": city["lon"],
        "radius_km": 40,
        "severity": severity,
        "description": description,
        "source": "OpenWeatherMap (Live)",
        "timestamp": ts,
    }


async def fetch_weather_disruptions() -> list[dict]:
    """Fetch weather disruptions for all monitored cities."""
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip(' "\'')
    if not api_key or api_key == "your_openweather_api_key_here":
        raise ValueError("Missing OpenWeatherMap API Key. Synthetic data is disabled for production.")

    disruptions = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for city in MONITORED_CITIES:
            try:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "lat": city["lat"],
                        "lon": city["lon"],
                        "appid": api_key,
                        "units": "metric",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    disruption = _map_weather_to_disruption(city, data)
                    if disruption:
                        disruptions.append(disruption)
            except Exception as e:
                print(f"[WeatherService] Error fetching {city['name']}: {e}")

    return disruptions
