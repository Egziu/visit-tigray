"""HTTP hardening: security headers, request-size limit, rate limiting, request ids, metrics."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

log = logging.getLogger("visit_tigray.http")

HTTP_LATENCY = Histogram("vt_http_request_seconds", "HTTP request latency", ["method", "route", "status"],
                         buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1, 2, 5, 10, 30))
RATE_LIMITED = Counter("vt_rate_limited_total", "Requests rejected by rate limiting", ["bucket"])

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        HTTP_LATENCY.labels(request.method, route_path, str(response.status_code)).observe(elapsed)
        h = response.headers
        h.setdefault("X-Request-ID", rid)
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("Cross-Origin-Resource-Policy", "same-site")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if not request.url.path.startswith("/api/docs") and not request.url.path.startswith("/api/openapi"):
            h.setdefault("Content-Security-Policy", API_CSP)
        if not get_settings().is_dev:
            h.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        if request.method == "GET" and "cache-control" not in h:
            h["Cache-Control"] = "no-store" if request.url.path.startswith(("/api/auth", "/api/me", "/api/bureau")) else "private, max-age=0"
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        limit = get_settings().max_request_bytes
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > limit:
            return JSONResponse({"error": {"code": "payload_too_large", "message": "Request body too large",
                                           "details": {"limit_bytes": limit}}}, status_code=413)
        return await call_next(request)


class RateLimiter:
    """Sliding-window limiter. Uses Redis when REDIS_URL is set, otherwise process memory.

    The in-memory backend is per-process: with several workers the effective limit is
    multiplied, which is documented in docs/THREAT_MODEL.md.
    """

    def __init__(self) -> None:
        self._mem: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._redis = None
        url = get_settings().redis_url
        if url:
            try:
                import redis

                self._redis = redis.Redis.from_url(url, socket_timeout=0.5)
                self._redis.ping()
            except Exception:  # pragma: no cover - depends on infra
                log.warning("redis unavailable; falling back to in-memory rate limiting")
                self._redis = None

    def hit(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.time()
        if self._redis is not None:  # pragma: no cover - exercised in integration env
            pipe = self._redis.pipeline()
            rk = f"rl:{key}"
            pipe.zremrangebyscore(rk, 0, now - window)
            pipe.zadd(rk, {f"{now}:{uuid.uuid4().hex[:6]}": now})
            pipe.zcard(rk)
            pipe.expire(rk, int(window) + 1)
            _, _, count, _ = pipe.execute()
            return int(count) <= limit
        with self._lock:
            q = self._mem[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._mem.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    # Behind the reverse proxy, uvicorn --proxy-headers populates request.client from X-Forwarded-For
    # only for trusted proxies (FORWARDED_ALLOW_IPS). We never parse the header ourselves.
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, per_minute: int | None = None):
    """FastAPI dependency factory: ``Depends(rate_limit("auth"))``."""
    from app.core.errors import AppError

    def _dep(request: Request) -> None:
        s = get_settings()
        limit = per_minute or {"auth": s.rate_limit_auth, "write": s.rate_limit_write, "ai": s.rate_limit_ai}.get(
            bucket, s.rate_limit_default)
        if not limiter.hit(f"{bucket}:{client_ip(request)}", limit):
            RATE_LIMITED.labels(bucket).inc()
            raise AppError(429, "rate_limited", "Too many requests — please slow down and try again shortly.")

    return _dep
