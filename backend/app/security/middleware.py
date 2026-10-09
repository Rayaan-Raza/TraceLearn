"""HTTP hardening middleware: security headers and request size limits."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.config import settings

# Content-Security-Policy for the API (JSON only) and for the bundled SPA.
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
SPA_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    # React sets style attributes; Monaco injects <style> tags.
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "worker-src 'self' blob:; "
    "connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
DOCS_CSP = (
    # Swagger UI loads its assets from jsDelivr; only used when docs are enabled.
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if path in ("/docs", "/redoc") or path.startswith("/docs/"):
            h.setdefault("Content-Security-Policy", DOCS_CSP)
        elif path.startswith("/api/") or path == "/health" or path == "/openapi.json":
            h.setdefault("Content-Security-Policy", API_CSP)
            # Authenticated JSON must never be cached by shared caches.
            h.setdefault("Cache-Control", "no-store")
        else:
            h.setdefault("Content-Security-Policy", SPA_CSP)
        if settings.effective_cookie_secure:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class BodySizeLimitMiddleware:
    """Reject request bodies larger than ``max_bytes`` without buffering them."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        too_large = JSONResponse({"detail": "Request body too large"}, status_code=413)
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        await too_large(scope, receive, send)
                        return
                except ValueError:
                    await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
                    return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await too_large(scope, receive, send)


class _BodyTooLarge(Exception):
    pass
