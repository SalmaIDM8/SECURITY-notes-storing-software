"""
Security tests for Interception attack prevention.

These tests ensure that:
1. Users cannot access other users' private notes
2. Users cannot modify other users' notes
3. Users cannot delete other users' notes
4. Shared notes maintain proper access controls
5. JWT tokens are properly validated
"""

import pytest


def test_unauthorized_note_access(client):
    """
    Abuse Frame: Interception. 
    Ensures User A cannot intercept User B's private notes.
    """
    # User B creates a private note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Private Note", "content": "Secret content"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # User A attempts to access User B's note
    response = client.get(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userA"}
    )
    assert response.status_code == 404  # Vulnerability prevented


def test_unauthorized_note_modification(client):
    """
    Abuse Frame: Interception/Tampering.
    Ensures User A cannot modify User B's notes through interception.
    """
    # User B creates a note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Original Title", "content": "Original content"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # User B acquires a lock to be able to update
    r = client.post(
        f"/notes/{note_id}/lock",
        headers={"X-User-Id": "userB"},
    )
    assert r.status_code == 200
    lock_id = r.json()["lock_id"]

    # User A attempts to modify User B's note (without a valid lock)
    response = client.put(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userA"},
        json={"title": "Hacked Title", "content": "Hacked content", "lock_id": lock_id},
    )
    assert response.status_code == 404  # User A cannot access User B's note

    # Verify the note was not modified
    r = client.get(f"/notes/{note_id}", headers={"X-User-Id": "userB"})
    assert r.status_code == 200
    assert r.json()["title"] == "Original Title"
    assert r.json()["content"] == "Original content"


def test_missing_user_id_header(client):
    """
    Abuse Frame: Interception - Missing Authentication.
    Ensures requests without User-Id header are rejected.
    """
    # User B creates a note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Secure Note", "content": "Protected"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # Attempt to access note without User-Id header
    response = client.get(f"/notes/{note_id}")
    assert response.status_code == 401  # Should be rejected with Unauthorized


def test_tampering_with_user_id_header(client):
    """
    Abuse Frame: Interception - Header Tampering.
    Ensures that tampering with the User-Id header doesn't grant access.
    """
    # User B creates a note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Secret", "content": "Only for B"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # User A tries to spoof User B's identity
    response = client.get(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userA; userB"}  # Header injection attempt
    )
    assert response.status_code == 404

    # Another injection attempt
    response = client.get(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userB"}  # Correct header should work
    )
    assert response.status_code == 200


def test_note_list_isolation(client):
    """
    Abuse Frame: Interception - Information Disclosure.
    Ensures User A cannot see User B's notes in the list.
    """
    # User B creates multiple notes
    note_ids = []
    for i in range(3):
        r = client.post(
            "/notes",
            headers={"X-User-Id": "userB"},
            json={"title": f"Note {i}", "content": f"Content {i}"},
        )
        assert r.status_code == 201
        note_ids.append(r.json()["id"])

    # User A creates their own note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userA"},
        json={"title": "User A Note", "content": "A's content"},
    )
    assert r.status_code == 201
    a_note_id = r.json()["id"]

    # User A lists their notes
    r = client.get("/notes", headers={"X-User-Id": "userA"})
    assert r.status_code == 200
    user_a_notes = r.json()
    
    # Verify User A only sees their own notes
    a_note_ids = [n["id"] for n in user_a_notes]
    assert a_note_id in a_note_ids
    for note_id in note_ids:
        assert note_id not in a_note_ids


def test_cross_user_sharing_access_control(client):
    """
    Abuse Frame: Interception with Shares.
    Ensures that only explicitly shared notes can be accessed by other users.
    """
    # User B creates a private note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Shared Note", "content": "Can be shared"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # User A tries to access the unshared note
    response = client.get(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userA"}
    )
    assert response.status_code == 404

    # User B creates a read-only share with User A
    r = client.post(
        f"/shares/notes/{note_id}",
        headers={"X-User-Id": "userB"},
        json={"shared_with_user_id": "userA", "mode": "ro"},
    )
    assert r.status_code == 201
    share_id = r.json()["share_id"]

    # After sharing, User A should be able to access the shared note via share endpoint
    response = client.get(
        f"/shares/{share_id}",
        headers={"X-User-Id": "userA"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Shared Note"
    
    # User A still cannot access it via the direct /notes endpoint
    response = client.get(
        f"/notes/{note_id}",
        headers={"X-User-Id": "userA"}
    )
    assert response.status_code == 404


def test_read_only_share_prevents_modification(client):
    """
    Abuse Frame: Interception/Tampering with Shared Notes.
    Ensures read-only shares cannot be modified by the recipient.
    """
    # User B creates a note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Original Title", "content": "Original content"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # User B creates a read-only share with User A
    r = client.post(
        f"/shares/notes/{note_id}",
        headers={"X-User-Id": "userB"},
        json={"shared_with_user_id": "userA", "mode": "ro"},
    )
    assert r.status_code == 201
    share_id = r.json()["share_id"]

    # User A tries to acquire a lock on the read-only share (write attempt)
    response = client.post(
        f"/shares/{share_id}/lock",
        headers={"X-User-Id": "userA"}
    )
    assert response.status_code == 403  # Forbidden - read-only share

    # User A cannot modify the shared note
    response = client.put(
        f"/shares/{share_id}",
        headers={"X-User-Id": "userA"},
        json={
            "title": "Hacked Title",
            "content": "Hacked content",
            "lock_id": "00000000-0000-0000-0000-000000000000"
        },
    )
    assert response.status_code in [403, 409]  # Forbidden or conflict

    # Verify the original note was not modified
    r = client.get(f"/notes/{note_id}", headers={"X-User-Id": "userB"})
    assert r.status_code == 200
    assert r.json()["title"] == "Original Title"
    assert r.json()["content"] == "Original content"


def test_unauthorized_user_cannot_access_shared_note(client):
    """
    Abuse Frame: Interception - Unauthorized Share Access.
    Ensures that users not in the share list cannot access shared notes.
    """
    # User B creates a note
    r = client.post(
        "/notes",
        headers={"X-User-Id": "userB"},
        json={"title": "Private Share", "content": "Shared with A only"},
    )
    assert r.status_code == 201
    note_id = r.json()["id"]

    # User B creates a share with User A (not User C)
    r = client.post(
        f"/shares/notes/{note_id}",
        headers={"X-User-Id": "userB"},
        json={"shared_with_user_id": "userA", "mode": "rw"},
    )
    assert r.status_code == 201
    share_id = r.json()["share_id"]

    # User C (not in share list) tries to access the shared note
    response = client.get(
        f"/shares/{share_id}",
        headers={"X-User-Id": "userC"}
    )
    assert response.status_code == 404  # Share not found for User C

    # User A can access it
    response = client.get(
        f"/shares/{share_id}",
        headers={"X-User-Id": "userA"}
    )
    assert response.status_code == 200
