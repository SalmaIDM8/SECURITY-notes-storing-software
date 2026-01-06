from __future__ import annotations

import hmac
import hashlib
import os


def compute_replication_token(body: bytes) -> str:
    secret = os.getenv("REPL_SECRET", "")
    if not secret:
        raise RuntimeError("REPL_SECRET is not set")
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return mac.hexdigest()


def verify_replication_token(body: bytes, token: str) -> bool:
    expected = compute_replication_token(body)
    # constant-time compare
    return hmac.compare_digest(expected, token)
