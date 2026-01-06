def test_share_read_only_allows_read_denies_write(client):
    # owner creates note
    r = client.post("/notes", headers={"X-User-Id": "userA"}, json={"title": "t", "content": "c"})
    note_id = r.json()["id"]

    # create RO share for userB
    r = client.post(
        f"/shares/notes/{note_id}",
        headers={"X-User-Id": "userA"},
        json={"shared_with_user_id": "userB", "mode": "ro"},
    )
    assert r.status_code == 201
    share_id = r.json()["share_id"]

    # userB can read via share
    r = client.get(f"/shares/{share_id}", headers={"X-User-Id": "userB"})
    assert r.status_code == 200
    assert r.json()["title"] == "t"

    # userB cannot acquire lock (write path)
    r = client.post(f"/shares/{share_id}/lock", headers={"X-User-Id": "userB"})
    assert r.status_code == 403

    # userB cannot update via share
    r = client.put(
        f"/shares/{share_id}",
        headers={"X-User-Id": "userB"},
        json={"title": "x", "content": "y", "lock_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code in (403, 409)


def test_share_read_write_requires_lock(client):
    r = client.post("/notes", headers={"X-User-Id": "userA"}, json={"title": "t", "content": "c"})
    note_id = r.json()["id"]

    # create RW share for userB
    r = client.post(
        f"/shares/notes/{note_id}",
        headers={"X-User-Id": "userA"},
        json={"shared_with_user_id": "userB", "mode": "rw"},
    )
    share_id = r.json()["share_id"]

    # update without lock -> 409
    r = client.put(
        f"/shares/{share_id}",
        headers={"X-User-Id": "userB"},
        json={"title": "t2", "content": "c2", "lock_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 409

    # acquire lock
    r = client.post(f"/shares/{share_id}/lock", headers={"X-User-Id": "userB"})
    assert r.status_code == 200
    lock_id = r.json()["lock_id"]

    # update with lock -> 200, version increments on owner note
    r = client.put(
        f"/shares/{share_id}",
        headers={"X-User-Id": "userB"},
        json={"title": "t2", "content": "c2", "lock_id": lock_id},
    )
    assert r.status_code == 200
    assert r.json()["version"] == 2


def test_share_cannot_be_used_by_wrong_user(client):
    r = client.post("/notes", headers={"X-User-Id": "userA"}, json={"title": "t", "content": "c"})
    note_id = r.json()["id"]

    r = client.post(
        f"/shares/notes/{note_id}",
        headers={"X-User-Id": "userA"},
        json={"shared_with_user_id": "userB", "mode": "ro"},
    )
    share_id = r.json()["share_id"]

    # userC should not be able to use it -> 404 (no leak)
    r = client.get(f"/shares/{share_id}", headers={"X-User-Id": "userC"})
    assert r.status_code == 404
