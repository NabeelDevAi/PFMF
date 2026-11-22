"""Response shapes shared across more than one router."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from app.core.messages import SUCCESS_MESSAGES

# Sanity bounds for any user-entered transaction date (UAT-008). Not a
# business rule: they only stop absurd values (year 0001, 9999) reaching the
# engine. A date outside them is a 422 validation.invalid on that field.
MIN_TXN_DATE = date(2000, 1, 1)
MAX_TXN_DATE = date(2100, 12, 31)
TxnDate = Annotated[date, Field(ge=MIN_TXN_DATE, le=MAX_TXN_DATE)]


class ActionResult(BaseModel):
    """A bilingual confirmation for an action endpoint that has no
    resource of its own to return (see app.core.messages). Replaces a
    bare 204 No Content -- a 204 response can't carry a body at all."""

    message_en: str
    message_ar: str

    @classmethod
    def from_key(cls, key: str) -> ActionResult:
        en, ar = SUCCESS_MESSAGES[key]
        return cls(message_en=en, message_ar=ar)
