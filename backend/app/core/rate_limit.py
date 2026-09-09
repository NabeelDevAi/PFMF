"""In-memory, per-process rate limiting. See backend-plan/07 §6: sufficient
for a single local process, explicitly not sufficient the moment there's
more than one -- upgrading to a shared (e.g. Redis-backed) limiter is
tracked in backend-plan/12 as a hardening-milestone item, not forgotten.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    """Fixed key -> sliding window of recent attempt timestamps. One
    instance is shared across all requests in this process; a lock guards
    it since sync FastAPI routes run in a threadpool."""

    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, *, max_attempts: int, window_seconds: float) -> bool:
        """Record one attempt for `key`. Returns True if it's within the
        limit, False if this attempt should be rejected."""
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] > window_seconds:
                attempts.popleft()
            if len(attempts) >= max_attempts:
                return False
            attempts.append(now)
            return True

    def reset(self) -> None:
        """Test-only: clear all recorded attempts. TestClient reuses one
        fake client host across every request in a process, so without
        this, rate-limit counters would leak between otherwise-unrelated
        tests that happen to share a route."""
        with self._lock:
            self._attempts.clear()


# One shared limiter per process, for every rate-limited route.
limiter = InMemoryRateLimiter()
