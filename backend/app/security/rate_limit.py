"""Small in-memory sliding-window rate limiter.

Good enough for a single-process deployment. If you run several uvicorn
workers or replicas, each keeps its own counters, so put a shared limiter
(e.g. at the reverse proxy) in front as well.
"""
from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

from backend.app.config import settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> None:
        if not settings.rate_limit_enabled:
            return
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                retry = int(window_seconds - (now - q[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please slow down.",
                    headers={"Retry-After": str(retry)},
                )
            q.append(now)
            if len(self._hits) > 50_000:  # bound memory under key-spraying
                self._evict(now)

    def _evict(self, now: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or now - q[-1] > 3600]:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    # Deliberately ignores X-Forwarded-For: it is client-controlled unless a
    # trusted proxy rewrites it. Run uvicorn with --proxy-headers and
    # --forwarded-allow-ips set to your proxy if you deploy behind one; that
    # makes request.client reflect the real address.
    return request.client.host if request.client else "unknown"
