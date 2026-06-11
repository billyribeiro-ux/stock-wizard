"""API authentication + vendor-key encryption."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from common.crypto import SecretBox
from common.settings import get_settings

_settings = get_settings()


def get_secret_box() -> SecretBox:
    return SecretBox(
        current_key=_settings.master_key,
        previous_key=_settings.master_key_previous or None,
    )


async def require_token(authorization: str | None = Header(default=None)) -> str:
    """Validate the internal bearer token the SvelteKit server sends."""
    expected = _settings.internal_api_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid token")
    return token
