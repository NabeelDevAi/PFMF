"""Request-id middleware. Every response carries X-Request-Id (backend-plan/07
§5) so a client-reported bug can be traced back to one request without ever
needing to log a financial value or PII. Also sets the request_id contextvar
(app.core.logging) so every log line during this request is correlated, and
emits one access-log line per request -- method, path, status, duration; no
query params, no body, no user-identifying value beyond the id already
attached elsewhere.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_var

logger = logging.getLogger("pfmf.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            # Logged before the reset below, deliberately: the access-log
            # line itself must still carry this request's id.
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            return response
        finally:
            request_id_var.reset(token)
