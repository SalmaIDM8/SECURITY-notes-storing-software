from pathlib import Path
import os

def test_event_log_emitted_on_create_update_lock(client):
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
    r = client.put(
        f"/notes/{note_id}",
        headers=headers,
        json={"title": "t2", "content": "c2", "lock_id": lock_id},
    )
    assert r.status_code == 200

    # event log should be written under APP_DATA_DIR (set by the client fixture)
    data_dir = Path(os.environ["APP_DATA_DIR"])
    p = data_dir / "users" / user / "events" / "events.log"
    assert p.exists(), f"Expected event log at {p}, but it does not exist."

    text = p.read_text(encoding="utf-8")
    assert "NOTE_CREATED" in text
    assert "LOCK_ACQUIRED" in text
    assert "NOTE_UPDATED" in text
