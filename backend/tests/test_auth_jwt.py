import os
import importlib
import pytest
from fastapi.testclient import TestClient

def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOCK_TTL_SECONDS", "300")
    monkeypatch.setenv("JWT_SECRET", "dev-secret-for-tests")
    monkeypatch.setenv("JWT_EXP_MINUTES", "15")

    import app.api.notes
    import app.api.auth
    import app.main
    importlib.reload(app.api.notes)
    importlib.reload(app.api.auth)
    importlib.reload(app.main)
    return TestClient(app.main.app)

def test_register_login_token_returned(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    r = client.post("/auth/register", json={"user_id": "userA", "password": "StrongPassw0rd!"})
    assert r.status_code == 201

    r = client.post("/auth/login", json={"user_id": "userA", "password": "StrongPassw0rd!"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_wrong_password(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    client.post("/auth/register", json={"user_id": "userA", "password": "StrongPassw0rd!"})
    r = client.post("/auth/login", json={"user_id": "userA", "password": "wrongwrongwrong"})
    assert r.status_code == 401

def test_protected_requires_token_or_header(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    # no auth at all
    r = client.get("/notes")
    assert r.status_code == 401

    # fallback header still works (compat with existing tests)
    r = client.get("/notes", headers={"X-User-Id": "userA"})
    assert r.status_code == 200
