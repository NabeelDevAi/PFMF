"""Local-disk avatar storage backing PATCH /me/settings' optional
`avatar_base64` field (screen-flow F2, Profile). Deliberately no separate
upload endpoint -- folded into the same call that already handles
display_name/currency_code/locale, by explicit product decision.

Storage is local disk under `media_root/avatars/`, served back through a
static mount (app/main.py) at `/static/avatars/<filename>` -- unauthenticated,
same security model as any public avatar host (Gravatar and similar):
filenames are random UUIDs, never sequential or derived from the user id,
so knowing one is equivalent to having a shareable link, not a way to
enumerate other users' photos.

Explicitly acknowledged as throwaway infrastructure, not a permanent
architecture: the moment this runs anywhere with an ephemeral or
non-shared filesystem (most real hosting), it needs to move to real
object storage. See 12-open-questions-and-future-hardening.md.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import APIError


def avatars_dir() -> Path:
    path = get_settings().media_root / "avatars"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _detect_extension(data: bytes) -> str | None:
    """Sniffs actual file bytes -- never trusts a claimed extension or
    MIME type, which prove nothing about what's actually inside."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_avatar(base64_data: str) -> str:
    """Decodes, validates, and writes a new avatar file, returning its
    filename (never a full URL -- UserSettings.avatar_url builds that).
    Deliberately does not delete any previous file -- the caller
    (SettingsService) does that only after this succeeds, so a bad
    upload never destroys a working photo."""
    # Tolerate a data: URI prefix (how a browser/file picker often hands
    # back an image) rather than rejecting an otherwise-valid payload
    # over formatting.
    if base64_data.strip().lower().startswith("data:") and "," in base64_data:
        base64_data = base64_data.split(",", 1)[1]

    try:
        data = base64.b64decode(base64_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise APIError("avatar.invalid_image", {"field": "avatar_base64"}) from exc

    if len(data) > get_settings().avatar_max_bytes:
        raise APIError("avatar.too_large", {"field": "avatar_base64"})

    extension = _detect_extension(data)
    if extension is None:
        raise APIError("avatar.invalid_image", {"field": "avatar_base64"})

    filename = f"{uuid.uuid4()}.{extension}"
    (avatars_dir() / filename).write_bytes(data)
    return filename


def delete_avatar(filename: str | None) -> None:
    """Best-effort -- a file that's already gone (or storage that's
    moved) is not an error worth failing the caller's own operation
    over."""
    if filename is None:
        return
    (avatars_dir() / filename).unlink(missing_ok=True)
