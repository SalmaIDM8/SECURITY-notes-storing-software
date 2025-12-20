from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_note_access_is_isolated_per_user():
    # userA creates a note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userA"},
        json={"title": "t1", "content": "c1"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # userA can list and see the note
    r = client.get("/notes", headers={"X-User-Id": "userA"})
    assert r.status_code == 200
    assert any(n["id"] == note_id for n in r.json())

    # userB cannot access userA's note (IDOR protection)
    r = client.get(f"/notes/{note_id}", headers={"X-User-Id": "userB"})
    assert r.status_code == 404


def test_invalid_note_id_is_rejected():
    # malformed identifier is rejected before business logic
    r = client.get("/notes/not-a-uuid", headers={"X-User-Id": "userA"})
    assert r.status_code == 422
