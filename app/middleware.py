"""HTTP middleware: request logging (with a per-request id) + security headers."""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("wiora.request")

# Standard hardening headers. HSTS is safe because the app is served over HTTPS
# (Render terminates TLS); harmless for the mobile client either way.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Log method, path, status and duration; tag each request with an id so a
    log line and any Sentry event can be correlated."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            dur = (time.perf_counter() - start) * 1000
            logger.exception("rid=%s %s %s -> 500 (%.0fms)", request_id, request.method, request.url.path, dur)
            raise
        dur = (time.perf_counter() - start) * 1000
        logger.info(
            "rid=%s %s %s -> %s (%.0fms)",
            request_id, request.method, request.url.path, response.status_code, dur,
        )
        response.headers["X-Request-ID"] = request_id
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response
