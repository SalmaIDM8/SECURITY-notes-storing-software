import os
import sys
import importlib
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Add backend directory to Python path so 'app' module can be imported
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # isolate data dir per test
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOCK_TTL_SECONDS", "300")
    monkeypatch.setenv("REPL_SECRET", "test-repl-secret")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-testing")

    # reload modules so that api/notes.py picks up new env vars
    import app.api.notes
    import app.api.shares
    import app.main

    importlib.reload(app.api.notes)
    importlib.reload(app.api.shares)
    importlib.reload(app.main)

    return TestClient(app.main.app)
