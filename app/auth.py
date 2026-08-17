"""Authentication: verify Firebase ID tokens (blueprint §10). Optional in dev —
with no token the request runs as a demo user (mirrors the mobile app's flow).

Uses Google's public certs + RS256 verification via python-jose; no heavy
firebase-admin dependency."""
from __future__ import annotations

import time

import httpx
from fastapi import Depends, Header, HTTPException
from jose import jwt

from .config import get_settings
from .db import get_db
from .models import User
from sqlalchemy.orm import Session

settings = get_settings()

_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
_ISSUER = f"https://securetoken.google.com/{settings.firebase_project_id}"

_certs: dict[str, str] = {}
_certs_exp: float = 0.0


def _get_certs() -> dict[str, str]:
    global _certs, _certs_exp
    if _certs and time.time() < _certs_exp:
        return _certs
    resp = httpx.get(_CERTS_URL, timeout=10)
    resp.raise_for_status()
    _certs = resp.json()
    # Cache ~1h; good enough for token verification.
    _certs_exp = time.time() + 3600
    return _certs


def _verify(token: str) -> str | None:
    """Return the Firebase UID if valid, else None."""
    try:
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        certs = _get_certs()
        if kid not in certs:
            return None
        claims = jwt.decode(
            token,
            certs[kid],
            algorithms=["RS256"],
            audience=settings.firebase_project_id,
            issuer=_ISSUER,
        )
        return claims.get("user_id") or claims.get("sub")
    except Exception:
        return None


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> str:
    """Resolve the user id. Real Firebase UID when a valid token is sent, else a
    shared demo user in dev. Upserts the user row."""
    user_id = "demo-user"
    if authorization and authorization.lower().startswith("bearer "):
        uid = _verify(authorization[7:])
        if uid:
            user_id = uid
        elif settings.firebase_project_id:
            # A token was sent but failed verification — reject.
            raise HTTPException(status_code=401, detail="Invalid auth token")

    if db.get(User, user_id) is None:
        db.add(User(id=user_id))
        db.commit()
    return user_id
