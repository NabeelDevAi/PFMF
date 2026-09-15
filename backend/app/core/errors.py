"""The error code registry and APIError -- moved here from app.api.errors
(Tier 2 #5) because services raising APIError directly is exactly what
they've always done, but `from app.api.errors import ...` from a service
violates the api -> services -> repositories -> db layering both docs
commit to: services must never import from api. import-linter caught
this on its very first run, which is the whole point of adding it.

app/api/errors.py keeps the genuinely HTTP-specific half: the envelope
shape and the FastAPI exception handlers that turn an APIError raised
anywhere below into a response. This module -- core, sitting below both
api and services -- is what both of them are allowed to depend on.

This table is a contract with the mobile client as much as an internal
reference (backend-plan/07 §4) -- every code needs an Arabic and English
string on the Flutter side. Adding a code without telling mobile ships an
untranslated error, so new codes belong in a reviewed change, not a
one-off raise somewhere in a service.

Additions beyond the original registry are called out at their entry
below -- same kind of gap as the missing refresh_tokens table each time:
a flow the plan already committed to needed a code it never defined,
fixed by naming it here, not working around it silently.
"""

from __future__ import annotations

ERROR_STATUS: dict[str, int] = {
    "auth.invalid_credentials": 401,
    "auth.email_taken": 409,
    "auth.token_expired": 401,
    "auth.token_invalid": 401,
    "auth.weak_password": 422,
    "auth.reset_token_invalid": 422,  # addition: invalid/expired/already-used reset token
    "balance.as_of_in_future": 422,
    "balance.as_of_too_old": 422,
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
    "overlay.scenario_is_base": 422,  # addition: overlays can't target the Base scenario itself
    "category.in_use": 409,  # addition: can't delete a user category still referenced
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
