from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, user_id: str, password: str) -> None:
    r = client.post("/auth/register", json={"user_id": user_id, "password": password})
    # idempotent for local runs
    assert r.status_code in (201, 409)


def test_ar4_cookie_is_httponly_and_cors_is_strict_allowlist(monkeypatch):
    """
    AR-4: Cross-Origin Token Theft (Interception – Perturbation)

    We mitigate v4 = {uJWT, uCORS} by:
    - uJWT: using HttpOnly auth cookie (JS can't read it)
    - uCORS: strict allowlist (legit origin allowed, malicious origin not allowed)
    """
    # Ensure JWT secret exists for token generation in tests
    monkeypatch.setenv("JWT_SECRET", os.getenv("JWT_SECRET", "test-secret"))

    client = TestClient(app)

    # Arrange: register a user
    _register(client, "user_ar4", "password123")

    # ---- uJWT mitigation: token must be in HttpOnly cookie ----
    r = client.post("/auth/login_cookie", json={"user_id": "user_ar4", "password": "password123"})
    assert r.status_code == 200, r.text

    # TestClient stores cookies + exposes Set-Cookie header
    set_cookie = r.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=strict" in set_cookie.lower()

    # ---- uCORS mitigation: allow legitimate origin, block evil origin ----
    # Legit origin should be echoed back
    r_legit = client.get("/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert r_legit.status_code == 200
    assert r_legit.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert r_legit.headers.get("access-control-allow-credentials") == "true"

    # Evil origin must NOT be allowed (no ACAO header)
    r_evil = client.get("/health", headers={"Origin": "https://evil.example"})
    assert r_evil.status_code == 200
    assert "access-control-allow-origin" not in r_evil.headers
