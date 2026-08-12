"""FastAPI middleware: CORS, request logging, basic hardening headers."""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

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
