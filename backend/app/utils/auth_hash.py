"""Password hashing helpers using passlib.

Provides two simple functions used by the auth/register flow:
- hash_password(plain: str) -> str
- verify_password(plain: str, hashed: str) -> bool

Uses bcrypt via passlib's CryptContext. The bcrypt rounds (cost) can be configured
by the environment variable `BCRYPT_ROUNDS` (int). Default rounds are left to passlib/bcrypt
if not provided.
"""
from __future__ import annotations

import os
import warnings
from passlib.context import CryptContext

# Configure CryptContext with bcrypt when possible. Allow optional rounds from env.
bcrypt_rounds = os.environ.get("BCRYPT_ROUNDS")
if bcrypt_rounds is not None:
    try:
        rounds = int(bcrypt_rounds)
    except ValueError:
        rounds = None
else:
    rounds = None

_pwd_context = None
try:
    if rounds:
        _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=rounds)
    else:
        _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    try:
        _pwd_context.hash("test")
    except Exception:
        raise
except Exception as exc:
    warnings.warn(
        "bcrypt backend not available or failed to initialize; falling back to pbkdf2_sha256. "
        f"Original error: {exc}",
        RuntimeWarning,
    )
    if rounds:
        _pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto", pbkdf2_sha256__rounds=rounds)
    else:
        _pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

pwd_context = _pwd_context


def hash_password(plain: str) -> str:
    """Hash a plaintext password and return the encoded hash string."""
    if plain is None:
        raise ValueError("Password must not be None")
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored hash.

    Returns True if the password matches, False otherwise.
    """
    if plain is None or hashed is None:
        return False
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False
