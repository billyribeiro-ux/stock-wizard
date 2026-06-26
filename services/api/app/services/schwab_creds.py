"""Server-side Schwab credential lifecycle — read the encrypted bundle, refresh the
access token when stale, persist the rotated tokens, and hand back a ready token.

The vendor-key store holds a single ciphertext per row; for Schwab that ciphertext is
the JSON ``SchwabCreds`` bundle (app key/secret, redirect, access + refresh tokens,
expiry). This module keeps the OAuth refresh entirely server-side — plaintext tokens
never leave the API process.
"""

from __future__ import annotations

from engine.data.schwab_source import SchwabAuth, SchwabCreds


async def load_creds(session, key_row) -> SchwabCreds:
    """Decrypt the Schwab credential bundle stored on a vendor-key row."""
    from ..security import get_secret_box

    return SchwabCreds.from_json(get_secret_box().decrypt(key_row.ciphertext))


async def ensure_access_token(session, key_row) -> str:
    """Return a valid Schwab access token, refreshing + persisting it if stale.

    Raises ``MissingCredentials`` (from ``SchwabAuth.refresh``) if the refresh token is
    missing/expired so callers can fall back to another vendor.
    """
    from ..repositories import repo
    from ..security import get_secret_box

    creds = await load_creds(session, key_row)
    if creds.needs_refresh:
        creds = SchwabAuth.refresh(creds)
        box = get_secret_box()
        await repo.update_vendor_key_ciphertext(session, key_row.id, box.encrypt(creds.to_json()))
    return creds.access_token
