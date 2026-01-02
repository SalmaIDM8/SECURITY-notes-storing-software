from pathlib import Path
from uuid import UUID
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.utils.auth_stub import get_user_id
from app.storage.notes_store import NotesStore
from app.storage.shares_store import SharesStore
from app.storage.locks_store import LocksStore
from app.storage.event_log import EventLog, Event


router = APIRouter(prefix="/shares", tags=["shares"])

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DATA_DIR = Path(os.getenv("APP_DATA_DIR", str(DEFAULT_DATA_DIR)))

notes = NotesStore(DATA_DIR)
shares = SharesStore(DATA_DIR)

LOCK_TTL_SECONDS = int(os.getenv("LOCK_TTL_SECONDS", "300"))
event_log = EventLog(DATA_DIR)
locks = LocksStore(DATA_DIR, default_ttl_seconds=LOCK_TTL_SECONDS, event_log=event_log)


class ShareCreateIn(BaseModel):
    shared_with_user_id: str = Field(min_length=1, max_length=64)
    mode: str = Field(pattern="^(ro|rw)$")
    ttl_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 30)  # max 30 days


class SharedNoteUpdateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=0, max_length=100_000)
    lock_id: UUID


@router.post("/notes/{note_id}", status_code=201)
def create_share(note_id: UUID, payload: ShareCreateIn, user_id: str = Depends(get_user_id)):
    # owner creates share for their own note
    try:
        s = shares.create_share(
            owner_user_id=user_id,
            note_id=uuid.UUID(str(note_id)),
            shared_with_user_id=payload.shared_with_user_id,
            mode=payload.mode,
            ttl_minutes=payload.ttl_minutes,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid share data")

    event_log.emit(Event(
        event_type="SHARE_CREATED",
        user_id=user_id,
        note_id=str(note_id),
        meta={"share_id": str(s.share_id), "mode": s.mode, "shared_with": s.shared_with_user_id},
    ))

    return s.to_dict()


@router.post("/{share_id}/revoke", status_code=200)
def revoke_share(share_id: UUID, user_id: str = Depends(get_user_id)):
    ok = shares.revoke_share(owner_user_id=user_id, share_id=uuid.UUID(str(share_id)))
    if not ok:
        raise HTTPException(status_code=404, detail="Share not found")

    event_log.emit(Event(
        event_type="SHARE_REVOKED",
        user_id=user_id,
        meta={"share_id": str(share_id)},
    ))
    return {"revoked": True}


@router.get("/{share_id}")
def read_shared_note(share_id: UUID, user_id: str = Depends(get_user_id)):
    s = shares.find_share_for_user(share_id=uuid.UUID(str(share_id)), user_id=user_id)
    if s is None:
        # do not leak existence
        raise HTTPException(status_code=404, detail="Share not found")

    note = notes.get_note(user_id=s.owner_user_id, note_id=s.note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")

    return note.to_dict()


@router.post("/{share_id}/lock")
def acquire_shared_lock(share_id: UUID, user_id: str = Depends(get_user_id)):
    s = shares.find_share_for_user(share_id=uuid.UUID(str(share_id)), user_id=user_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Share not found")

    if s.mode != "rw":
        # AR2: RO share must never allow writes
        raise HTTPException(status_code=403, detail="Read-only share")

    lock = locks.acquire_lock_for_share(note_owner_user_id=s.owner_user_id, note_id=s.note_id, share_id=s.share_id)
    if lock is None:
        raise HTTPException(status_code=404, detail="Note not found")

    event_log.emit(Event(
        event_type="LOCK_ACQUIRED",
        user_id=user_id,
        note_id=str(s.note_id),
        lock_id=str(lock["lock_id"]),
        meta={"via_share": str(s.share_id)},
    ))

    return lock


@router.put("/{share_id}")
def update_shared_note(share_id: UUID, payload: SharedNoteUpdateIn, user_id: str = Depends(get_user_id)):
    s = shares.find_share_for_user(share_id=uuid.UUID(str(share_id)), user_id=user_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Share not found")

    if s.mode != "rw":
        raise HTTPException(status_code=403, detail="Read-only share")

    if not locks.require_valid_lock_for_share(
        note_owner_user_id=s.owner_user_id,
        note_id=s.note_id,
        share_id=s.share_id,
        lock_id=uuid.UUID(str(payload.lock_id)),
    ):
        raise HTTPException(status_code=409, detail="Valid lock required")

    updated = notes.update_note(
        user_id=s.owner_user_id,
        note_id=s.note_id,
        title=payload.title,
        content=payload.content,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Note not found")

    event_log.emit(Event(
        event_type="NOTE_UPDATED",
        user_id=user_id,
        note_id=str(s.note_id),
        lock_id=str(payload.lock_id),
        meta={"via_share": str(s.share_id), "version": updated.version},
    ))
    return updated.to_dict()
