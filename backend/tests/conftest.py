import os
import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # isolate data dir per test
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOCK_TTL_SECONDS", "300")
    monkeypatch.setenv("REPL_SECRET", "test-repl-secret")

    # reload modules so that api/notes.py picks up new env vars
    import app.api.notes
    import app.api.shares
    import app.main

    importlib.reload(app.api.notes)
    importlib.reload(app.api.shares)
    importlib.reload(app.main)

    return TestClient(app.main.app)
