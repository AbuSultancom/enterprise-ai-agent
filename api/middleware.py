"""FastAPI middleware: security headers, CORS, rate limiting, request logging."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# ─── Rate Limiter ────────────────────────────────────────────────────────────

# requests per (key, window) → count
_rate_store: dict[str, list[float]] = defaultdict(list)

# Limits: requests per minute per role
RATE_LIMITS: dict[str, int] = {
    "admin": 300,
    "user": 60,
    "anonymous": 10,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter based on X-API-Key header."""

    WINDOW = 60  # seconds

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for static files and health
        if request.url.path in ("/health", "/") or request.url.path.startswith("/static"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "anonymous")
        from api.dependencies import API_KEYS  # avoid circular import
        role = API_KEYS.get(api_key, "anonymous")
        limit = RATE_LIMITS.get(role, RATE_LIMITS["anonymous"])

        now = time.time()
        window_start = now - self.WINDOW

        # Clean old requests
        _rate_store[api_key] = [t for t in _rate_store[api_key] if t > window_start]

        if len(_rate_store[api_key]) >= limit:
            retry_after = int(self.WINDOW - (now - _rate_store[api_key][0]))
            return Response(
                content='{"detail":"Rate limit exceeded. Please slow down."}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": str(max(retry_after, 1)),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        _rate_store[api_key].append(now)
        response = await call_next(request)
        remaining = limit - len(_rate_store[api_key])
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        return response


# ─── Security Headers ─────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Only add HSTS in production (not localhost)
        host = request.headers.get("host", "")
        if "localhost" not in host and "127.0.0.1" not in host:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# ─── Request Timing ───────────────────────────────────────────────────────────

class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Adds X-Process-Time header to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{(time.perf_counter() - start) * 1000:.1f}ms"
        return response


# ─── Registration helper ──────────────────────────────────────────────────────

def register_middleware(app: FastAPI, allowed_origins: list[str] | None = None) -> None:
    """Register all middleware on the FastAPI app (order matters: last added = outermost)."""
    # CORS
    origins = allowed_origins or ["http://localhost:8000", "http://localhost:3001"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "PUT", "PATCH"],
        allow_headers=["*"],
    )
    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)
    # Request timing
    app.add_middleware(RequestTimingMiddleware)
    # Rate limiting
    app.add_middleware(RateLimitMiddleware)
