"""HTTP auth API. Next.js sets cookies; this service is the authority."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from auth.passwords import (
    hash_password,
    password_policy_error,
    verify_dummy,
    verify_password,
)
from auth.rate_limit import get_rate_limiter
from auth.store import RefreshRecord, get_store
from auth.tokens import mint_access_token, verify_access_token
import config

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GENERIC_CREDENTIALS = "invalid_credentials"
GENERIC_CREATE = "could_not_create"


class SignUpBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class SignInBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RefreshBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=16, max_length=128)


class SignOutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str | None = Field(default=None, max_length=128)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return request.client.host
    return "unknown"


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return None
    return value.strip()


def _rate_or_429(key: str, *, limit: int, window_secs: int) -> None:
    if not get_rate_limiter().allow(key, limit=limit, window_secs=window_secs):
        raise HTTPException(status_code=429, detail="rate_limited")


async def _active_user_from_access(token: str | None) -> Any:
    claims = verify_access_token(token)
    if not claims:
        raise HTTPException(status_code=401, detail="unauthorized")
    user = await asyncio.to_thread(get_store().get_user_by_id, claims["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


def _token_payload(user_id: str, refresh_token: str) -> dict[str, Any]:
    return {
        "access_token": mint_access_token(user_id=user_id),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": config.ACCESS_TTL_SECS,
    }


@router.post("/signup")
async def signup(body: SignUpBody, request: Request) -> dict[str, Any]:
    ip = _client_ip(request)
    _rate_or_429(f"signup:ip:{ip}", limit=5, window_secs=3600)
    email = normalize_email(body.email)
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="invalid_email")
    _rate_or_429(f"signup:email:{email}", limit=5, window_secs=3600)
    if password_policy_error(body.password):
        raise HTTPException(status_code=400, detail="weak_password")
    password_hash = await asyncio.to_thread(hash_password, body.password)
    user = await asyncio.to_thread(
        get_store().create_user, email=email, password_hash=password_hash
    )
    if user is None:
        raise HTTPException(status_code=400, detail=GENERIC_CREATE)
    raw, _session = await asyncio.to_thread(
        get_store().create_refresh_session, user_id=user.id
    )
    return _token_payload(user.id, raw)


@router.post("/signin")
async def signin(body: SignInBody, request: Request) -> dict[str, Any]:
    ip = _client_ip(request)
    email = normalize_email(body.email)
    _rate_or_429(f"signin:ip:{ip}", limit=20, window_secs=900)
    _rate_or_429(f"signin:email:{email}", limit=10, window_secs=900)
    user = await asyncio.to_thread(get_store().get_user_by_email, email)
    if user is None:
        await asyncio.to_thread(verify_dummy, body.password)
        raise HTTPException(status_code=401, detail=GENERIC_CREDENTIALS)
    if not user.is_active:
        await asyncio.to_thread(verify_dummy, body.password)
        raise HTTPException(status_code=401, detail=GENERIC_CREDENTIALS)
    ok = await asyncio.to_thread(verify_password, user.password_hash, body.password)
    if not ok:
        raise HTTPException(status_code=401, detail=GENERIC_CREDENTIALS)
    raw, _session = await asyncio.to_thread(
        get_store().create_refresh_session, user_id=user.id
    )
    return _token_payload(user.id, raw)


@router.post("/refresh")
async def refresh(body: RefreshBody, request: Request) -> dict[str, Any]:
    ip = _client_ip(request)
    _rate_or_429(f"refresh:ip:{ip}", limit=60, window_secs=60)
    store = get_store()
    record = await asyncio.to_thread(store.get_refresh_by_token, body.refresh_token)
    now = time.time()
    if record is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    if record.revoked_at is not None:
        await asyncio.to_thread(store.revoke_family, record.family_id)
        raise HTTPException(status_code=401, detail="unauthorized")
    if record.expires_at < now:
        await asyncio.to_thread(store.revoke_session, record.id)
        raise HTTPException(status_code=401, detail="unauthorized")
    user = await asyncio.to_thread(store.get_user_by_id, record.user_id)
    if user is None or not user.is_active:
        await asyncio.to_thread(store.revoke_family, record.family_id)
        raise HTTPException(status_code=401, detail="unauthorized")
    await asyncio.to_thread(store.revoke_session, record.id)
    raw, _new = await asyncio.to_thread(
        store.create_refresh_session,
        user_id=user.id,
        family_id=record.family_id,
    )
    return _token_payload(user.id, raw)


@router.post("/signout")
async def signout(
    body: SignOutBody,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    store = get_store()
    if body.refresh_token:
        record: RefreshRecord | None = await asyncio.to_thread(
            store.get_refresh_by_token, body.refresh_token
        )
        if record is not None:
            await asyncio.to_thread(store.revoke_family, record.family_id)
    claims = verify_access_token(_bearer(authorization))
    if claims:
        # Access JWT remains valid until expiry; refresh family is revoked.
        pass
    return {"status": "ok"}


@router.get("/me")
async def me(authorization: str | None = Header(default=None)) -> dict[str, str]:
    user = await _active_user_from_access(_bearer(authorization))
    return {"id": user.id}


@router.post("/voice-ticket")
async def voice_ticket(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Mint a short-lived, single-use voice credential for the caller."""
    user = await _active_user_from_access(_bearer(authorization))
    ip = _client_ip(request)
    _rate_or_429(f"voice:ip:{ip}", limit=20, window_secs=60)
    _rate_or_429(f"voice:user:{user.id}", limit=10, window_secs=60)
    from security import mint_voice_ticket

    token = mint_voice_ticket(user_id=user.id)
    if not token:
        raise HTTPException(status_code=503, detail="not_ready")
    return {"token": token, "expires_in": config.VOICE_TICKET_TTL_SECS}
