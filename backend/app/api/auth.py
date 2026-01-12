from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, Response

from app.models.auth import LoginRequest, RegisterRequest, TokenResponse
from app.storage.users_store import UsersStore
from app.utils.auth_hash import hash_password, verify_password
from app.utils.jwt_auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data"

def _users_store() -> UsersStore:
    data_dir = Path(os.getenv("APP_DATA_DIR", str(DEFAULT_DATA_DIR)))
    return UsersStore(data_dir)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    users = _users_store()
    if users.get(req.user_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User exists")
    hpw = hash_password(req.password)
    users.create(req.user_id, hpw)
    return {"user_id": req.user_id}



@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    users = _users_store()
    rec = users.get(req.user_id)
    if rec is None or not verify_password(req.password, rec.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=req.user_id)
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/login_cookie")
def login_cookie(req: LoginRequest, response: Response):
    users = _users_store()
    rec = users.get(req.user_id)
    if rec is None or not verify_password(req.password, rec.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=req.user_id)

    cookie_secure = os.getenv("COOKIE_SECURE", "0") == "1"  # keep 0 in local HTTP
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=cookie_secure,
        path="/",
    )
    return {"status": "ok"}



@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"status": "ok"}
