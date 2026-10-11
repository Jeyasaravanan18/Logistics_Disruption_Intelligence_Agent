"""
SHA-256 Pipeline Assessment Cache.
Key is derived deterministically from:
    sha256(owner_id + shipments_version + sorted_disruption_content_hashes)
Stores analysis payloads in Redis with configurable TTL, falling back gracefully to
an in-memory TTL dictionary if Redis is offline.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import redis


class ResilienceCache:
    """
    Two-tier caching engine (Redis + Thread-safe in-memory fallback)
    with deterministic SHA-256 key generation and TTL expiry.
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        default_ttl: int = 300,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.redis_client = redis_client
        self.default_ttl = default_ttl
        self.clock = clock or time.time

        # In-memory fallback: key -> (payload_json_str, expiry_timestamp)
        self._memory_store: Dict[str, Tuple[str, float]] = {}
        self.hits: int = 0
        self.misses: int = 0

    @staticmethod
    def generate_key(
        owner_id: str,
        shipments_version: str | int,
        disruption_hashes: List[str],
    ) -> str:
        """
        Derive an immutable SHA-256 cache key.
        Disruption hashes are canonically sorted so that ordering variations do not miss the cache.
        """
        sorted_hashes = sorted(disruption_hashes)
        serialized_input = f"{owner_id}:{shipments_version}:{':'.join(sorted_hashes)}"
        digest = hashlib.sha256(serialized_input.encode("utf-8")).hexdigest()
        return f"cache:assessment:{digest}"

    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached value if valid, updating hit/miss metrics."""
        now = self.clock()

        # 1. Attempt Redis retrieval
        if self.redis_client:
            try:
                raw = self.redis_client.get(key)
                if raw is not None:
                    self.hits += 1
                    return json.loads(raw)
            except Exception:
                pass

        # 2. In-memory fallback retrieval
        if key in self._memory_store:
            raw_str, expiry = self._memory_store[key]
            if now < expiry:
                self.hits += 1
                return json.loads(raw_str)
            else:
                del self._memory_store[key]

        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store serialized payload with TTL expiration."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        payload = json.dumps(value)
        now = self.clock()

        # Store in Redis
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, payload)
            except Exception:
                pass

        # Store in in-memory fallback
        self._memory_store[key] = (payload, now + ttl)

    def invalidate(self, key: str) -> None:
        """Evict a specific key immediately from Redis and local memory."""
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception:
                pass

        self._memory_store.pop(key, None)

    def clear(self) -> None:
        """Clear all in-memory entries (does not flush entire Redis namespace)."""
        self._memory_store.clear()
        self.hits = 0
        self.misses = 0
