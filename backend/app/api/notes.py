from pathlib import Path
from uuid import UUID
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException

from app.models.notes import NoteCreate, NoteOut, NoteUpdate
from app.storage.notes_store import NotesStore
from app.storage.locks_store import LocksStore
from app.storage.event_log import EventLog, Event
from app.utils.auth_stub import get_user_id

router = APIRouter(prefix="/notes", tags=["notes"])

# Base data dir: repository_root/data (we are in backend/)
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
store = NotesStore(DATA_DIR)

# TTL config (now via env)
LOCK_TTL_SECONDS = int(os.getenv("LOCK_TTL_SECONDS", "300"))

# Day 4: event log + pass it into LocksStore for LOCK_EXPIRED
event_log = EventLog(DATA_DIR)
locks = LocksStore(DATA_DIR, default_ttl_seconds=LOCK_TTL_SECONDS, event_log=event_log)


@router.post("", response_model=NoteOut, status_code=201)
def create_note(payload: NoteCreate, user_id: str = Depends(get_user_id)) -> NoteOut:
    note = store.create_note(user_id=user_id, title=payload.title, content=payload.content)

    event_log.emit(Event(
        event_type="NOTE_CREATED",
        user_id=user_id,
        note_id=str(note.id),
        meta={"version": note.version},
    ))

    return NoteOut(**note.to_dict())


@router.get("", response_model=list[NoteOut])
def list_notes(user_id: str = Depends(get_user_id)) -> list[NoteOut]:
    notes = store.list_notes(user_id=user_id)
    return [NoteOut(**n.to_dict()) for n in notes]


@router.get("/{note_id}", response_model=NoteOut)
def get_note(note_id: UUID, user_id: str = Depends(get_user_id)) -> NoteOut:
    note = store.get_note(user_id=user_id, note_id=uuid.UUID(str(note_id)))
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteOut(**note.to_dict())


# Day 3: Locking
@router.post("/{note_id}/lock")
def acquire_lock(note_id: UUID, user_id: str = Depends(get_user_id)) -> dict:
    nid = uuid.UUID(str(note_id))
    lock = locks.acquire_lock(user_id=user_id, note_id=nid)
    if lock is None:
        raise HTTPException(status_code=404, detail="Note not found")

    event_log.emit(Event(
        event_type="LOCK_ACQUIRED",
        user_id=user_id,
        note_id=str(note_id),
        lock_id=str(lock.lock_id),
        meta={"expires_at": lock.expires_at},
    ))

    return lock.to_dict()


# Day 4 stabilization: make DELETE idempotent (recommended)
@router.delete("/{note_id}/lock", status_code=204)
def release_lock(note_id: UUID, user_id: str = Depends(get_user_id)) -> None:
    nid = uuid.UUID(str(note_id))
    locks.release_lock(user_id=user_id, note_id=nid)

    event_log.emit(Event(
        event_type="LOCK_RELEASED",
        user_id=user_id,
        note_id=str(note_id),
    ))

    return None


# Day 3: Update (requires lock)
@router.put("/{note_id}", response_model=NoteOut)
def update_note(note_id: UUID, payload: NoteUpdate, user_id: str = Depends(get_user_id)) -> NoteOut:
    nid = uuid.UUID(str(note_id))

    existing = store.get_note(user_id=user_id, note_id=nid)
    if existing is None:
        raise HTTPException(status_code=404, detail="Note not found")

    if not locks.require_valid_lock(user_id=user_id, note_id=nid, lock_id=uuid.UUID(str(payload.lock_id))):
        raise HTTPException(status_code=409, detail="Valid lock required")

    updated = store.update_note(user_id=user_id, note_id=nid, title=payload.title, content=payload.content)
    if updated is None:
        raise HTTPException(status_code=404, detail="Note not found")

    event_log.emit(Event(
        event_type="NOTE_UPDATED",
        user_id=user_id,
        note_id=str(note_id),
        lock_id=str(payload.lock_id),
        meta={"version": updated.version},
    ))

    return NoteOut(**updated.to_dict())
