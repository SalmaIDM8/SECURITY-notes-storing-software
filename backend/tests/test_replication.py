import importlib
from pathlib import Path
import os
from fastapi.testclient import TestClient


def make_client(tmp_path):
    # helper to create an isolated TestClient with APP_DATA_DIR=tmp_path
    os.environ["APP_DATA_DIR"] = str(tmp_path)
    # reload modules so they pick up env
    import app.api.notes
    import app.api.replication
    import app.main
    importlib.reload(app.api.notes)
    importlib.reload(app.api.replication)
    importlib.reload(app.main)
    return TestClient(app.main.app)


def test_replicate_create_and_update(tmp_path):
    # Create two isolated servers (A and B)
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()

    client_a = make_client(a_dir)
    client_b = make_client(b_dir)

    user = "userA"

    # create note on A
    r = client_a.post("/notes", headers={"X-User-Id": user}, json={"title": "t1", "content": "c1"})
    assert r.status_code == 201
    note_id = r.json()["id"]

    # get events from A
    r = client_a.get(f"/replicate/events?user_id={user}")
    assert r.status_code == 200
    events = r.json()
    assert any(e.get("event_type") == "NOTE_CREATED" for e in events)

    # post events to B
    r = client_b.post("/replicate/events", json=events)
    assert r.status_code == 200
    assert r.json().get("applied", 0) >= 1

    # confirm B has the note
    r = client_b.get(f"/notes/{note_id}", headers={"X-User-Id": user})
    assert r.status_code == 200

    # update on A (requires lock)
    r = client_a.post(f"/notes/{note_id}/lock", headers={"X-User-Id": user})
    assert r.status_code == 200
    lock_id = r.json()["lock_id"]

    r = client_a.put(f"/notes/{note_id}", headers={"X-User-Id": user}, json={"title": "t2", "content": "c2", "lock_id": lock_id})
    assert r.status_code == 200

    # replicate update
    events = client_a.get(f"/replicate/events?user_id={user}").json()
    r = client_b.post("/replicate/events", json=events)
    assert r.status_code == 200

    # confirm B sees version 2
    r = client_b.get(f"/notes/{note_id}", headers={"X-User-Id": user})
    assert r.status_code == 200
    assert r.json().get("version") == 2
