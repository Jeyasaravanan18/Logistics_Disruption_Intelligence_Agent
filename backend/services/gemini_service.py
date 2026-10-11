"""
Gemini Service — LLM client with native JSON generation and Circuit Breaker resilience.
Tracks call health and transitions through CLOSED -> OPEN -> HALF_OPEN states to prevent
cascading timeouts and preserve quota during upstream degradation.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
import redis

try:
    from backend.resilience.circuit_breaker import CircuitBreaker
except ImportError:
    from resilience.circuit_breaker import CircuitBreaker

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

def _get_redis_client() -> Optional[redis.Redis]:
    """Provide a Redis client with fast connection timeout if available."""
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        return client
    except Exception:
        return None

# Global circuit breaker instance protecting Gemini calls
gemini_circuit_breaker = CircuitBreaker(
    name="gemini_llm",
    failure_threshold=3,
    cooldown_seconds=30.0,
    success_threshold=2,
    redis_client=_get_redis_client(),
)

MODELS_TO_TRY = [
    os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


async def generate_gemini_json(prompt: str, system_instruction: str = "") -> dict | None:
    """
    Call Google Gemini API with native JSON output.
    Guarded by CircuitBreaker: fast-fails immediately if the breaker is OPEN.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip(' "\'')
    if not api_key or api_key == "your_gemini_api_key_here":
        return None

    if not gemini_circuit_breaker.can_execute():
        print(f"[GeminiService] Circuit Breaker is {gemini_circuit_breaker.get_state()}; skipping remote call.", flush=True)
        return None

    full_prompt = f"System Instruction: {system_instruction}\n\n{prompt}" if system_instruction else prompt
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    }

    for model in MODELS_TO_TRY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text)
                    gemini_circuit_breaker.record_success()
                    return parsed
                elif resp.status_code == 429:
                    print(f"[GeminiService] Rate limit / Quota exceeded (429) on {model}.", flush=True)
                    gemini_circuit_breaker.record_failure(is_quota_error=True)
                    break
                elif resp.status_code in (500, 502, 503, 504):
                    print(f"[GeminiService] Upstream 5xx on {model} ({resp.status_code}).", flush=True)
                    gemini_circuit_breaker.record_failure(is_quota_error=False)
                    break
                elif resp.status_code in (403, 404):
                    print(f"[GeminiService] Model {model} unavailable ({resp.status_code}), trying next.", flush=True)
                    continue
                else:
                    gemini_circuit_breaker.record_failure(is_quota_error=False)
                    break
        except Exception as e:
            print(f"[GeminiService] Call to {model} failed with exception: {e}", flush=True)
            gemini_circuit_breaker.record_failure(is_quota_error=False)
            break

    return None
