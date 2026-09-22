"""Pure unit tests for the bilingual message registries (no DB, no HTTP) --
the fast, exhaustive counterpart to the handful of real-HTTP checks in
tests/api/test_auth.py and friends that confirm the wiring actually
reaches a response.
"""

from __future__ import annotations

from app.core.errors import ERROR_MESSAGES, ERROR_STATUS
from app.core.messages import SUCCESS_MESSAGES


def test_every_error_code_has_a_message_pair() -> None:
    """The import-time parity check in app.core.errors already enforces
    this (a mismatch crashes on import), but pin it as an explicit,
    readable test too rather than relying only on "the app failed to
    start" as the signal."""
    assert set(ERROR_MESSAGES) == set(ERROR_STATUS)


def test_no_error_message_is_blank() -> None:
    for code, (en, ar) in ERROR_MESSAGES.items():
        assert en.strip(), f"{code} has a blank English message"
        assert ar.strip(), f"{code} has a blank Arabic message"


def test_no_success_message_is_blank() -> None:
    for key, (en, ar) in SUCCESS_MESSAGES.items():
        assert en.strip(), f"{key} has a blank English message"
        assert ar.strip(), f"{key} has a blank Arabic message"


def test_error_messages_are_not_placeholder_duplicates() -> None:
    """Every code's English text must be genuinely distinct -- a copy-paste
    across entries would silently make several errors indistinguishable
    to the user even though their `code`s differ."""
    english_texts = [en for en, _ in ERROR_MESSAGES.values()]
    assert len(english_texts) == len(set(english_texts))
