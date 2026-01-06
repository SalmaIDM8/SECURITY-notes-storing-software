from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

bearer = HTTPBearer(auto_error=False)


def _secret() -> str:
    s = os.getenv("JWT_SECRET", "")
    if not s:
        # pentru teste/dev poți seta în env; în prod e obligatoriu
        raise RuntimeError("JWT_SECRET is not set")
    return s


def _algo() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def _exp_minutes() -> int:
    try:
        return int(os.getenv("JWT_EXP_MINUTES", "15"))
    except ValueError:
        return 15


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=_exp_minutes())
    payload = {"sub": subject, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, _secret(), algorithm=_algo())


def decode_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[_algo()])


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    """
    FINAL behavior:
    - Prefer JWT (Authorization: Bearer ...)
    - Fallback to X-User-Id (compatibility with existing tests/demo)
    """
    if creds is not None and creds.scheme.lower() == "bearer":
        try:
            payload = decode_token(creds.credentials)
            sub = payload.get("sub")
            if not sub:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            return str(sub)
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # fallback (tests + demo)
    if x_user_id:
        return x_user_id

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")
