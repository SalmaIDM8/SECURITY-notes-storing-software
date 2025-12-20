from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.models.notes import NoteCreate, NoteOut
from app.storage.notes_store import NotesStore
from app.utils.auth_stub import get_user_id

router = APIRouter(prefix="/notes", tags=["notes"])

# Base data dir: repository_root/data (we are in backend/)
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
store = NotesStore(DATA_DIR)


@router.post("", response_model=NoteOut, status_code=201)
def create_note(payload: NoteCreate, user_id: str = Depends(get_user_id)) -> NoteOut:
    note = store.create_note(user_id=user_id, title=payload.title, content=payload.content)
    return NoteOut(**note.to_dict())


@router.get("", response_model=list[NoteOut])
def list_notes(user_id: str = Depends(get_user_id)) -> list[NoteOut]:
    notes = store.list_notes(user_id=user_id)
    return [NoteOut(**n.to_dict()) for n in notes]


@router.get("/{note_id}", response_model=NoteOut)
def get_note(note_id: UUID, user_id: str = Depends(get_user_id)) -> NoteOut:
    note = store.get_note(user_id=user_id, note_id=note_id)
    if note is None:
        # Important: return 404, not 403, because in MVP we can’t know
        # if it exists for another user (prevents info leakage).
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteOut(**note.to_dict())
