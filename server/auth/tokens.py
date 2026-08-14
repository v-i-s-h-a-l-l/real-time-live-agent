"""Short-lived access JWTs. Refresh tokens are opaque (see store)."""

from __future__ import annotations

import time
import uuid
from typing import Any

import jwt

import config

ACCESS_TYP = "access"
ALGORITHM = "HS256"


def _secret() -> str:
    secret = config.auth_secret()
    if not secret:
        raise RuntimeError("AUTH_SECRET/SESSION_SECRET is not configured")
    return secret


def mint_access_token(*, user_id: str, now: float | None = None) -> str:
    issued = int(now if now is not None else time.time())
    payload = {
        "sub": user_id,
        "iss": config.JWT_ISSUER,
        "aud": config.JWT_AUDIENCE,
        "iat": issued,
        "exp": issued + config.ACCESS_TTL_SECS,
        "jti": uuid.uuid4().hex,
        "typ": ACCESS_TYP,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def verify_access_token(token: str | None, *, now: float | None = None) -> dict[str, Any] | None:
    if not token or not config.auth_secret():
        return None
    options = {
        "require": ["sub", "iss", "aud", "iat", "exp", "typ"],
        "verify_signature": True,
        "verify_exp": False,
        "verify_iss": True,
        "verify_aud": True,
    }
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            issuer=config.JWT_ISSUER,
            audience=config.JWT_AUDIENCE,
            options=options,
        )
    except jwt.InvalidTokenError:
        return None
    if claims.get("typ") != ACCESS_TYP:
        return None
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        return None
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return None
    moment = now if now is not None else time.time()
    if exp + 5 < moment:
        return None
    return claims
