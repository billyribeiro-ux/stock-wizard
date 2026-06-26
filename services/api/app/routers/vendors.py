"""Vendor API-key management — encrypted at rest, masked on read."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.crypto import SecretBox
from engine.data import KNOWN_VENDORS
from engine.data.schwab_source import SchwabAuth, SchwabCreds

from ..db import get_session
from ..repositories import repo
from ..security import get_secret_box, require_token

router = APIRouter(tags=["vendors"], dependencies=[Depends(require_token)])


class AddKeyRequest(BaseModel):
    vendor: str
    label: str = ""
    api_key: str = Field(min_length=1)
    scopes: list[str] = Field(default_factory=list)


class EnableRequest(BaseModel):
    enabled: bool


class RotateRequest(BaseModel):
    api_key: str = Field(min_length=1)


class LabelRequest(BaseModel):
    label: str = Field(min_length=1)


class SchwabConnectRequest(BaseModel):
    app_key: str = Field(min_length=1)
    app_secret: str = Field(min_length=1)
    redirect_uri: str = "https://127.0.0.1:8182"
    label: str = "Charles Schwab"


class SchwabTokenRequest(BaseModel):
    key_id: UUID
    code: str = ""
    redirect_url: str = ""  # paste the full returned URL; we extract ?code=…


def _extract_code(req: SchwabTokenRequest) -> str:
    if req.code:
        return req.code
    if req.redirect_url:
        from urllib.parse import parse_qs, urlparse

        code = parse_qs(urlparse(req.redirect_url).query).get("code", [""])[0]
        if code:
            return code
    raise HTTPException(400, "missing authorization code")


def _serialize(row) -> dict:
    return {
        "id": str(row.id),
        "vendor": row.vendor,
        "label": row.label,
        "masked_key": row.masked,
        "enabled": row.enabled,
        "scopes": row.scopes,
        "key_version": row.key_version,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
    }


@router.get("/vendors/catalog")
async def vendor_catalog() -> list[dict]:
    return [
        {
            "vendor": v.vendor,
            "label": v.label,
            "requires_key": v.requires_key,
            "capabilities": v.capabilities,
            "docs_url": v.docs_url,
            "notes": v.notes,
        }
        for v in KNOWN_VENDORS
    ]


@router.get("/vendors")
async def list_keys(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = await repo.list_vendor_keys(session)
    return [_serialize(r) for r in rows]


@router.post("/vendors/keys", status_code=201)
async def add_key(
    req: AddKeyRequest,
    session: AsyncSession = Depends(get_session),
    box: SecretBox = Depends(get_secret_box),
) -> dict:
    try:
        ciphertext = box.encrypt(req.api_key)
    except ValueError as exc:
        raise HTTPException(500, f"encryption unavailable: {exc}") from exc
    row = await repo.add_vendor_key(
        session,
        vendor=req.vendor,
        label=req.label or req.vendor,
        ciphertext=ciphertext,
        masked=SecretBox.mask(req.api_key),
        scopes=req.scopes,
        key_version=box.key_version,
    )
    return {"id": str(row.id)}


@router.patch("/vendors/keys/{key_id}")
async def set_enabled(
    key_id: UUID, req: EnableRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    row = await repo.set_vendor_key_enabled(session, key_id, req.enabled)
    if row is None:
        raise HTTPException(404, "key not found")
    return {"id": str(row.id), "enabled": row.enabled}


@router.post("/vendors/keys/{key_id}/rotate")
async def rotate_key(
    key_id: UUID,
    req: RotateRequest,
    session: AsyncSession = Depends(get_session),
    box: SecretBox = Depends(get_secret_box),
) -> dict:
    """Replace a key's secret in place (rotate) — same id/label/scopes, new ciphertext."""
    try:
        ciphertext = box.encrypt(req.api_key)
    except ValueError as exc:
        raise HTTPException(500, f"encryption unavailable: {exc}") from exc
    row = await repo.rotate_vendor_key(
        session,
        key_id,
        ciphertext=ciphertext,
        masked=SecretBox.mask(req.api_key),
        key_version=box.key_version,
    )
    if row is None:
        raise HTTPException(404, "key not found")
    return {"id": str(row.id), "masked_key": row.masked, "key_version": row.key_version}


@router.patch("/vendors/keys/{key_id}/label")
async def rename_key(
    key_id: UUID, req: LabelRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    row = await repo.update_vendor_key_label(session, key_id, req.label)
    if row is None:
        raise HTTPException(404, "key not found")
    return {"id": str(row.id), "label": row.label}


@router.delete("/vendors/keys/{key_id}", status_code=204)
async def delete_key(key_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    ok = await repo.delete_vendor_key(session, key_id)
    if not ok:
        raise HTTPException(404, "key not found")


# --- Charles Schwab OAuth2 (3-legged) -----------------------------------------------
@router.post("/vendors/schwab/connect", status_code=201)
async def schwab_connect(
    req: SchwabConnectRequest,
    session: AsyncSession = Depends(get_session),
    box: SecretBox = Depends(get_secret_box),
) -> dict:
    """Step 1: store the app key/secret bundle (disabled until tokens arrive) and return
    the Schwab authorize URL. The user consents in a browser, then pastes the returned
    URL/code back to ``/vendors/schwab/token``.
    """
    creds = SchwabCreds(
        app_key=req.app_key, app_secret=req.app_secret, redirect_uri=req.redirect_uri
    )
    try:
        ciphertext = box.encrypt(creds.to_json())
    except ValueError as exc:
        raise HTTPException(500, f"encryption unavailable: {exc}") from exc
    row = await repo.add_vendor_key(
        session,
        vendor="schwab",
        label=req.label,
        ciphertext=ciphertext,
        masked=SecretBox.mask(req.app_key),
        scopes=[],
        key_version=box.key_version,
    )
    # Not usable until the code is exchanged — keep it disabled so scans don't pick it up.
    await repo.set_vendor_key_enabled(session, row.id, False)
    return {
        "id": str(row.id),
        "authorize_url": SchwabAuth.authorize_url(req.app_key, req.redirect_uri),
    }


@router.post("/vendors/schwab/token")
async def schwab_token(
    req: SchwabTokenRequest,
    session: AsyncSession = Depends(get_session),
    box: SecretBox = Depends(get_secret_box),
) -> dict:
    """Step 2: exchange the authorization code for access + refresh tokens, persist the
    updated bundle, and enable the key so scans can use it.
    """
    code = _extract_code(req)
    row = await repo.get_vendor_key(session, req.key_id)
    if row is None or row.vendor != "schwab":
        raise HTTPException(404, "schwab credential not found")
    try:
        creds = SchwabCreds.from_json(box.decrypt(row.ciphertext))
        creds = SchwabAuth.exchange_code(creds, code)
    except Exception as exc:
        raise HTTPException(400, f"token exchange failed: {exc}") from exc
    await repo.update_vendor_key_ciphertext(session, row.id, box.encrypt(creds.to_json()))
    await repo.set_vendor_key_enabled(session, row.id, True)
    return {"id": str(row.id), "enabled": True, "connected": True}
