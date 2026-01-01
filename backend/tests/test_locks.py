# from fastapi.testclient import TestClient
# from app.main import app
from app.storage.notes_store import _safe_user_dir, _note_path


# client = TestClient(app)


def test_update_requires_lock(client):
    # create note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userA"},
        json={"title": "t1", "content": "c1"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # update without lock -> 409
    r = client.put(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userA"},
        json={"title": "t2", "content": "c2", "lock_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 409

    # acquire lock -> 200
    r = client.post(f"/notes/{note_id}/lock", headers={"X-User-Id": "userA"})
    assert r.status_code == 200
    lock_id = r.json()["lock_id"]

    # update with valid lock -> 200 and version increments
    r = client.put(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userA"},
        json={"title": "t2", "content": "c2", "lock_id": lock_id},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["title"] == "t2"
    assert updated["content"] == "c2"
    assert updated["version"] == 2


def test_lock_and_update_are_isolated_per_user(client):
    # userA creates
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userA"},
        json={"title": "ta", "content": "ca"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # userB cannot lock or update (should get 404, no leakage)
    r = client.post(f"/notes/{note_id}/lock", headers={"X-User-Id": "userB"})
    assert r.status_code == 404

    r = client.put(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userB"},
        json={"title": "x", "content": "y", "lock_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404

def test_released_lock_cannot_be_reused(client):
    r = client.post("/notes", headers={"X-User-Id": "userA"}, json={"title": "t", "content": "c"})
    note_id = r.json()["id"]

    r = client.post(f"/notes/{note_id}/lock", headers={"X-User-Id": "userA"})
    lock_id = r.json()["lock_id"]

    # release lock
    r = client.delete(f"/notes/{note_id}/lock", headers={"X-User-Id": "userA"})
    assert r.status_code == 204

    # update with old lock_id must fail
    r = client.put(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userA"},
        json={"title": "t2", "content": "c2", "lock_id": lock_id},
    )
    assert r.status_code == 409

def test_wrong_lock_id_is_rejected(client):
    r = client.post("/notes", headers={"X-User-Id": "userA"}, json={"title": "t", "content": "c"})
    note_id = r.json()["id"]

    r = client.post(f"/notes/{note_id}/lock", headers={"X-User-Id": "userA"})
    assert r.status_code == 200

    # use a random lock_id instead of the real one
    r = client.put(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userA"},
        json={"title": "t2", "content": "c2", "lock_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert r.status_code == 409

def test_invalid_note_id_is_rejected_for_lock_routes(client):
    r = client.post("/notes/not-a-uuid/lock", headers={"X-User-Id": "userA"})
    assert r.status_code == 422

    r = client.delete("/notes/not-a-uuid/lock", headers={"X-User-Id": "userA"})
    assert r.status_code == 422
