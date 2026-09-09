"""The stub interface backend-plan/09-auth-and-security.md asks for: a
transactional email provider is an unresolved external dependency, so the
reset-token flow is built now behind this interface, with a trivial local
implementation. Swapping in a real provider later is a one-file change.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger("pfmf.password_reset")


class PasswordResetSender(Protocol):
    def send(self, *, email: str, token: str) -> None: ...


class ConsolePasswordResetSender:
    """Local-dev implementation: logs the token instead of emailing it.
    Never logs the recipient's email at anything above debug -- the token
    itself is already logged nowhere else, so this is the one place it's
    deliberately visible, for local testing only."""

    def send(self, *, email: str, token: str) -> None:
        logger.info("Password reset token issued for %s: %s", email, token)
