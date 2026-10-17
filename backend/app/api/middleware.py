import hmac
import logging
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

log = logging.getLogger("app.http")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_EXEMPT_PREFIXES = ("/api/webhooks/",)  # authenticated by provider signature instead


class SecurityMiddleware(BaseHTTPMiddleware):
    """Request id, CSRF double-submit check for state-changing requests, security headers."""

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        settings = get_settings()

        if request.method not in SAFE_METHODS and not request.url.path.startswith(
            CSRF_EXEMPT_PREFIXES
        ):
            cookie = request.cookies.get(settings.csrf_cookie_name, "")
            header = request.headers.get("x-csrf-token", "")
            if not cookie or not header or not hmac.compare_digest(cookie, header):
                return JSONResponse(
                    status_code=403,
                    content={"error": {"code": "csrf_failed",
                                       "message": "Sessão expirada. Recarregue a página."}},
                    headers={"X-Request-ID": request_id},
                )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
