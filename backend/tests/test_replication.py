import importlib
import os
import json
import hmac
import hashlib

from fastapi.testclient import TestClient


def make_client(tmp_path):
    """
    Helper to create an isolated TestClient with APP_DATA_DIR=tmp_path.
    Reloads modules so they pick up env vars.
    """
    os.environ["APP_DATA_DIR"] = str(tmp_path)

    import app.api.notes
    import app.api.replication
    import app.main

    importlib.reload(app.api.notes)
    importlib.reload(app.api.replication)
    importlib.reload(app.main)

    return TestClient(app.main.app)


def _replicate_events(sender_client: TestClient, receiver_client: TestClient, user_id: str) -> dict:
    """
    Pull events from sender via GET /replicate/events and push them to receiver via
    POST /replicate/events with HMAC auth.
    Returns receiver response JSON.
    """
    # Get events from sender
    r = sender_client.get(f"/replicate/events?user_id={user_id}")
    assert r.status_code == 200
    events = r.json()
    assert isinstance(events, list)

    # Compute HMAC over exact bytes that will be sent
    body = json.dumps(events, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    token = hmac.new(os.environ["REPL_SECRET"].encode("utf-8"), body, hashlib.sha256).hexdigest()

    # Post to receiver with raw content + token
    r = receiver_client.post(
        "/replicate/events",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Replication-Token": token,
        },
    )
    assert r.status_code == 200
    return r.json()


def test_replicate_create_and_update(tmp_path):
    # Create two isolated servers (A and B)
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()

    # Shared replication secret for HMAC
    os.environ["REPL_SECRET"] = "test-repl-secret"

    client_a = make_client(a_dir)
    client_b = make_client(b_dir)

    user = "userA"

    # 1) Create note on A
    r = client_a.post(
        "/notes",
        headers={"X-User-Id": user},
        json={"title": "t1", "content": "c1"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # 2) Replicate create to B
    resp = _replicate_events(client_a, client_b, user)
    assert resp.get("applied", 0) >= 1

    # 3) Confirm B has the note
    r = client_b.get(f"/notes/{note_id}", headers={"X-User-Id": user})
    assert r.status_code == 200
    assert r.json().get("title") == "t1"
    assert r.json().get("version") == 1

    # 4) Update note on A (requires lock)
    r = client_a.post(f"/notes/{note_id}/lock", headers={"X-User-Id": user})
    assert r.status_code == 200
    lock_id = r.json()["lock_id"]

    r = client_a.put(
        f"/notes/{note_id}",
        headers={"X-User-Id": user},
        json={"title": "t2", "content": "c2", "lock_id": lock_id},
    )
    assert r.status_code == 200

    # 5) Replicate update to B
    resp = _replicate_events(client_a, client_b, user)
    assert resp.get("applied", 0) >= 1

    # 6) Confirm B sees version 2 + updated title/content
    r = client_b.get(f"/notes/{note_id}", headers={"X-User-Id": user})
    assert r.status_code == 200
    assert r.json().get("version") == 2
    assert r.json().get("title") == "t2"
    assert r.json().get("content") == "c2"
