"""The error envelope and the error code registry.

This table is a contract with the mobile client as much as an internal
reference (backend-plan/07 §4) -- every code needs an Arabic and English
string on the Flutter side. Adding a code without telling mobile ships an
untranslated error, so new codes belong in a reviewed change, not a
one-off raise somewhere in a router.

Two additions beyond the original registry, both because the underlying
flow (password reset) was already committed to in backend-plan/09 without
its own error code being defined there -- same kind of gap as the missing
refresh_tokens table, fixed the same way: named here, not worked around
silently.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ERROR_STATUS: dict[str, int] = {
    "auth.invalid_credentials": 401,
    "auth.email_taken": 409,
    "auth.token_expired": 401,
    "auth.token_invalid": 401,
    "auth.weak_password": 422,
    "auth.reset_token_invalid": 422,  # addition: invalid/expired/already-used reset token
    "validation.required": 422,
    "validation.invalid": 422,
    "transaction.amount_not_positive": 422,
    "transaction.end_before_start": 422,
    "transaction.one_time_has_end_date": 422,
    "transaction.direction_immutable": 422,
    "transaction.limit_reached": 422,
    "scenario.base_immutable": 409,
    "scenario.name_taken": 409,
    "scenario.limit_reached": 422,
    "overlay.target_not_in_base": 422,
    "overlay.already_exists": 409,
    "compare.same_scenario": 422,
    "forecast.invalid_horizon": 422,
    "resource.not_found": 404,
    "rate_limited": 429,
    "internal": 500,
}


class APIError(Exception):
    """Raise this from a service or router; the code's HTTP status is
    looked up from the registry above so callers never have to repeat it
    (and can't accidentally pair a code with the wrong status)."""

    def __init__(self, code: str, params: dict | None = None) -> None:
        if code not in ERROR_STATUS:
            raise ValueError(f"unregistered error code: {code!r}")
        self.code = code
        self.status_code = ERROR_STATUS[code]
        self.params = params or {}
        super().__init__(code)


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
    return JSONResponse(status_code=500, content=_envelope(request, "internal", {}))


def register_exception_handlers(app) -> None:
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
