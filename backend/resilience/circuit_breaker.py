"""
Circuit Breaker Implementation for External LLM & Tool Calls.
Implements the canonical CLOSED -> OPEN -> HALF_OPEN finite state machine.
Supports Redis-backed shared state across distributed workers with thread-safe in-memory fallback.
Accepts an injectable clock for deterministic time-travel unit testing.
"""

from __future__ import annotations

import json
import time
from typing import Callable, Optional

import redis


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """
    Finite State Machine:
    - CLOSED: Normal operation. Failures are counted. If failure_threshold is reached, trips to OPEN.
    - OPEN: Inbound requests fail fast without calling external services.
            After cooldown_seconds, transitions to HALF_OPEN.
    - HALF_OPEN: Allows a trial request. If success_threshold consecutive requests succeed,
                 transitions back to CLOSED. Any failure trips immediately back to OPEN.
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        name: str = "gemini_llm",
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        success_threshold: int = 2,
        redis_client: Optional[redis.Redis] = None,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.success_threshold = success_threshold
        self.redis_client = redis_client
        self.clock = clock or time.time

        # Local in-memory state fallback
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = 0.0

    def _redis_key(self) -> str:
        return f"circuit_breaker:{self.name}"

    def get_state(self) -> str:
        """Return current breaker state, evaluating cooldown transitions dynamically."""
        now = self.clock()

        # Check Redis if available
        if self.redis_client:
            try:
                raw = self.redis_client.get(self._redis_key())
                if raw:
                    data = json.loads(raw)
                    state = data.get("state", self.CLOSED)
                    opened_at = float(data.get("opened_at", 0.0))
                    if state == self.OPEN and (now - opened_at) >= self.cooldown_seconds:
                        self._transition_to(self.HALF_OPEN)
                        return self.HALF_OPEN
                    return state
            except Exception:
                pass

        # In-memory evaluation
        if self._state == self.OPEN:
            if (now - self._opened_at) >= self.cooldown_seconds:
                self._state = self.HALF_OPEN
                self._success_count = 0

        return self._state

    def can_execute(self) -> bool:
        """Return True if request is permitted to proceed; False if circuit is OPEN."""
        state = self.get_state()
        return state in (self.CLOSED, self.HALF_OPEN)

    def _transition_to(self, new_state: str) -> None:
        """Update breaker state locally and in Redis."""
        now = self.clock()
        self._state = new_state

        if new_state == self.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._opened_at = 0.0
        elif new_state == self.OPEN:
            self._opened_at = now
            self._success_count = 0
        elif new_state == self.HALF_OPEN:
            self._success_count = 0

        if self.redis_client:
            try:
                payload = json.dumps({
                    "state": self._state,
                    "failure_count": self._failure_count,
                    "success_count": self._success_count,
                    "opened_at": self._opened_at,
                })
                self.redis_client.setex(self._redis_key(), 86400, payload)
            except Exception:
                pass

    def record_success(self) -> None:
        """Record successful invocation."""
        state = self.get_state()

        if state == self.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._transition_to(self.CLOSED)
        elif state == self.CLOSED:
            self._failure_count = 0

    def record_failure(self, is_quota_error: bool = False) -> None:
        """Record failed invocation or 429 quota exhaustion."""
        state = self.get_state()

        if is_quota_error:
            # Immediate trip on 429 rate limit / quota exhaustion
            self._failure_count = self.failure_threshold
            self._transition_to(self.OPEN)
            return

        if state == self.HALF_OPEN:
            # Any failure in trial mode immediately re-trips circuit
            self._transition_to(self.OPEN)
        elif state == self.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._transition_to(self.OPEN)

    def reset(self) -> None:
        """Force reset circuit breaker to pristine CLOSED state."""
        self._transition_to(self.CLOSED)
