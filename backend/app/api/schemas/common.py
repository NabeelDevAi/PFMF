"""Response shapes shared across more than one router."""

from __future__ import annotations

from pydantic import BaseModel

from app.core.messages import SUCCESS_MESSAGES


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
