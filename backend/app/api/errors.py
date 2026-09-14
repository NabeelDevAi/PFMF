"""The HTTP-specific half of error handling: the response envelope shape
and the FastAPI exception handlers. The error code registry and APIError
itself live in app.core.errors -- see that module's docstring for why
this split exists (Tier 2 #5, import-linter).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import APIError

logger = logging.getLogger("pfmf.errors")


def _envelope(request: Request, code: str, params: dict) -> dict:
    return {
        "error": {
            "code": code,
            "params": params,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content=_envelope(request, exc.code, exc.params)
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic can report several problems at once; the first is enough to
    # give the client a field to point at. Never echo the raw pydantic
    # message -- the client owns all user-facing language.
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    code = "validation.required" if first.get("type") == "missing" else "validation.invalid"
    return JSONResponse(status_code=422, content=_envelope(request, code, {"field": field}))


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Routing-level 404s (no matching route) and similar Starlette-raised
    # HTTPExceptions that never went through APIError -- still same envelope.
    code = "resource.not_found" if exc.status_code == 404 else "internal"
    return JSONResponse(status_code=exc.status_code, content=_envelope(request, code, {}))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Previously this handler returned "internal" with zero server-side
    # trace of what actually broke -- a genuine bug (anything that isn't
    # a deliberate APIError) was silently swallowed. exc_info=exc works
    # whether or not we're inside an active except block, unlike
    # logger.exception() which relies on sys.exc_info() still being set.
    logger.error("unhandled exception", exc_info=exc)
    return JSONResponse(status_code=500, content=_envelope(request, "internal", {}))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
