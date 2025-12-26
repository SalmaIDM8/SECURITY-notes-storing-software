from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_event_log_emitted_on_create_update_lock(tmp_path, monkeypatch):
    # OPTIONAL: dacă vrei izolare totală, trebuie ca DATA_DIR să fie configurabil.
    # Dacă nu ai încă DATA_DIR config, poți face testul fără tmp_path și doar verifica fișierul real.
    # Pentru moment, verificăm fișierul real:
    user = "userA"
    headers = {"X-User-Id": user}

    # create note
    r = client.post("/notes", headers=headers, json={"title": "t", "content": "c"})
    assert r.status_code == 201
    note_id = r.json()["id"]

    # lock
    r = client.post(f"/notes/{note_id}/lock", headers=headers)
    assert r.status_code == 200
    lock_id = r.json()["lock_id"]

    # update
    r = client.put(f"/notes/{note_id}", headers=headers, json={"title": "t2", "content": "c2", "lock_id": lock_id})
    assert r.status_code == 200

    # check event log exists and contains expected event types
    # repo_root/data/users/userA/events/events.log
    repo_root = Path(__file__).resolve().parents[2]  # backend/
    data_dir = repo_root / "data"
    p = data_dir / "users" / user / "events" / "events.log"
    assert p.exists()

    text = p.read_text(encoding="utf-8")
    assert "NOTE_CREATED" in text
    assert "LOCK_ACQUIRED" in text
    assert "NOTE_UPDATED" in text
