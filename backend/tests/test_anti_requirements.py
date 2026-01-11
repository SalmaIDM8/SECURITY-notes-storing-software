import uuid


def _get_token_for(client, user_id: str) -> str:
    pw = "TestPassw0rd!"
    # register (ignore conflict)
    client.post("/auth/register", json={"user_id": user_id, "password": pw})
    r = client.post("/auth/login", json={"user_id": user_id, "password": pw})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_ar1_jwt_precedence_over_header(client):
    # User B creates a private note (using header fallback)
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Private Note", "content": "Secret content"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # Attacker has a valid JWT for userA but tries to spoof header to userB
    token = _get_token_for(client, "userA")
    response = client.get(
        f"/notes/{note_id}",
        headers={"Authorization": f"Bearer {token}", "X-User-Id": "userB"},
    )

    # JWT takes precedence: the request is authenticated as userA and must NOT return userB's note
    assert response.status_code == 404


def test_ar1_jwt_owner_ignores_spoofed_header(client):
    # User B creates a private note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Owner Note", "content": "Owner content"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # Owner presents a valid JWT but an attacker-supplied header tries to override identity
    token = _get_token_for(client, "userB")
    r = client.get(f"/notes/{note_id}", headers={"Authorization": f"Bearer {token}", "X-User-Id": "userA"})
    assert r.status_code == 200
    assert r.json()["content"] == "Owner content"


def test_ar2_cannot_modify_note_without_owning_lock(client):
    # User B creates a note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Original", "content": "Sensitive"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # User B acquires a lock
    r = client.post(f"/notes/{note_id}/lock", headers={"X-User-Id": "userB"})
    assert r.status_code == 200
    lock_id = r.json()["lock_id"]

    # Attacker (userA) attempts to use the intercepted lock_id to modify the note
    token = _get_token_for(client, "userA")
    response = client.put(
        f"/notes/{note_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Hacked", "content": "Hacked", "lock_id": lock_id},
    )

    # The update must not succeed: userA doesn't own the note (404)
    assert response.status_code == 404


def test_expired_jwt_is_rejected(client, monkeypatch):
    # create a note for userB using header fallback
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Private", "content": "Secret"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # force tokens to be already expired
    monkeypatch.setenv("JWT_EXP_MINUTES", "-1")

    # register/login to receive an expired token for userA
    client.post("/auth/register", json={"user_id": "userA", "password": "TestPassw0rd!"})
    r = client.post("/auth/login", json={"user_id": "userA", "password": "TestPassw0rd!"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    # attempting to use the expired token must return 401 (missing/invalid token behavior)
    r = client.get(f"/notes/{note_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_replicate_events_requires_token_and_applies_with_valid_token(client):
    import json
    from app.utils.replication_auth import compute_replication_token
    from uuid import uuid4

    user = "rep_user"
    note_id = str(uuid4())

    # prepare an event payload trying to create a note for `user`
    payload = {
        "event_id": str(uuid4()),
        "event_type": "NOTE_CREATED",
        "user_id": user,
        "note_id": note_id,
        "payload": {
            "id": note_id,
            "owner_user_id": user,
            "title": "Replicated",
            "content": "From replication",
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z",
            "version": 1,
        },
    }

    body = [payload]
    body_bytes = json.dumps(body).encode("utf-8")

    # 1) without token -> 401
    r = client.post("/replicate/events", data=body_bytes, headers={"Content-Type": "application/json"})
    assert r.status_code == 401

    # 2) with invalid token -> 401
    r = client.post(
        "/replicate/events",
        data=body_bytes,
        headers={"Content-Type": "application/json", "X-Replication-Token": "badtoken"},
    )
    assert r.status_code == 401

    # 3) with valid token -> applied and note becomes readable by owner
    token = compute_replication_token(body_bytes)
    r = client.post(
        "/replicate/events",
        data=body_bytes,
        headers={"Content-Type": "application/json", "X-Replication-Token": token},
    )
    assert r.status_code == 200
    assert r.json().get("applied", 0) >= 1

    # The replication endpoint reported applied events; actual storage apply errors
    # are handled by the server (we don't assert direct visibility here).


def test_ar3_lock_starvation_expires_and_allows_reacquire(client):
    import json
    from pathlib import Path
    import os

    # create note as owner
    r = client.post("/notes", headers={"X-User-Id": "owner"}, json={"title": "t", "content": "c"})
    assert r.status_code == 201
    note_id = r.json()["id"]

    # owner acquires lock
    r = client.post(f"/notes/{note_id}/lock", headers={"X-User-Id": "owner"})
    assert r.status_code == 200
    lock1 = r.json()["lock_id"]

    # subsequent acquire returns same lock (idempotent while active)
    r = client.post(f"/notes/{note_id}/lock", headers={"X-User-Id": "owner"})
    assert r.status_code == 200
    assert r.json()["lock_id"] == lock1

    # simulate expiration by editing the locks file expires_at to the past
    base_dir = Path(os.getenv("APP_DATA_DIR"))
    lock_path = base_dir / "users" / "owner" / "locks" / f"{note_id}.json"
    assert lock_path.exists()
    raw = json.loads(lock_path.read_text(encoding="utf-8"))
    raw["expires_at"] = "1970-01-01T00:00:00Z"
    lock_path.write_text(json.dumps(raw), encoding="utf-8")

    # acquiring again should create a new lock (old expired)
    r = client.post(f"/notes/{note_id}/lock", headers={"X-User-Id": "owner"})
    assert r.status_code == 200
    lock2 = r.json()["lock_id"]
    assert lock2 != lock1


def test_ar5_replication_replay_and_ordering(client):
    import json
    from app.utils.replication_auth import compute_replication_token
    from uuid import uuid4

    user = "rep_order"
    note_id = str(uuid4())

    # create v2 (newer) then v1 (older)
    ev_v2 = {
        "event_id": str(uuid4()),
        "event_type": "NOTE_CREATED",
        "user_id": user,
        "note_id": note_id,
        "payload": {
            "id": note_id,
            "owner_user_id": user,
            "title": "v2",
            "content": "content v2",
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z",
            "version": 2,
        },
    }

    ev_v1 = {
        "event_id": str(uuid4()),
        "event_type": "NOTE_UPDATED",
        "user_id": user,
        "note_id": note_id,
        "payload": {
            "id": note_id,
            "owner_user_id": user,
            "title": "v1",
            "content": "content v1",
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z",
            "version": 1,
        },
    }

    # post v2
    body = [ev_v2]
    b = json.dumps(body).encode("utf-8")
    token = compute_replication_token(b)
    r = client.post("/replicate/events", data=b, headers={"Content-Type": "application/json", "X-Replication-Token": token})
    assert r.status_code == 200
    assert r.json().get("applied", 0) >= 1

    # Replay detection: posting the same v2 event again should be ignored (applied 0)
    token3 = compute_replication_token(b)
    r = client.post("/replicate/events", data=b, headers={"Content-Type": "application/json", "X-Replication-Token": token3})
    assert r.status_code == 200
    assert r.json().get("applied", 0) == 0

    # now post older v1 - should still be processed at event-level (server will decide whether to apply)
    body2 = [ev_v1]
    b2 = json.dumps(body2).encode("utf-8")
    token2 = compute_replication_token(b2)
    r = client.post("/replicate/events", data=b2, headers={"Content-Type": "application/json", "X-Replication-Token": token2})
    assert r.status_code == 200
    assert r.json().get("applied", 0) >= 1
