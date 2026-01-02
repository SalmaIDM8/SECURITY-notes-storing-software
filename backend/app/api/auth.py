from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.models.auth import LoginRequest, RegisterRequest, TokenResponse
from app.storage.users_store import UsersStore
from app.utils.auth_hash import hash_password, verify_password
from app.utils.jwt_auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DATA_DIR = Path(os.getenv("APP_DATA_DIR", str(DEFAULT_DATA_DIR)))
users = UsersStore(DATA_DIR)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    if users.get(req.user_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User exists")

    hpw = hash_password(req.password)  # corect: nu stoca niciodată plaintext
    users.create(req.user_id, hpw)
    return {"user_id": req.user_id}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    rec = users.get(req.user_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(req.password, rec.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=req.user_id)
    return TokenResponse(access_token=token)
