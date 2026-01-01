import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_user_dir(base_dir: Path, user_id: str) -> Path:
    # user_id is currently from header; keep it strict-ish to avoid path issues.
    # (Auth team will later provide a trusted user id.)
    if not user_id or any(ch in user_id for ch in "/\\.."):
        raise ValueError("Invalid user_id")
    return base_dir / "users" / user_id / "notes"


def _note_path(base_dir: Path, user_id: str, note_id: uuid.UUID) -> Path:
    return _safe_user_dir(base_dir, user_id) / f"{note_id}.json"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(path)


@dataclass(frozen=True)
class Note:
    id: uuid.UUID
    owner_user_id: str
    title: str
    content: str
    created_at: str
    updated_at: str
    version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "owner_user_id": self.owner_user_id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }


class NotesStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def create_note(self, user_id: str, title: str, content: str) -> Note:
        note_id = uuid.uuid4()
        now = _utc_now_iso()
        note = Note(
            id=note_id,
            owner_user_id=user_id,
            title=title,
            content=content,
            created_at=now,
            updated_at=now,
            version=1,
        )
        path = _note_path(self.base_dir, user_id, note_id)
        _atomic_write_json(path, note.to_dict())
        return note

    def list_notes(self, user_id: str) -> list[Note]:
        notes_dir = _safe_user_dir(self.base_dir, user_id)
        if not notes_dir.exists():
            return []
        out: list[Note] = []
        for p in sorted(notes_dir.glob("*.json")):
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                out.append(
                    Note(
                        id=uuid.UUID(raw["id"]),
                        owner_user_id=raw["owner_user_id"],
                        title=raw["title"],
                        content=raw["content"],
                        created_at=raw["created_at"],
                        updated_at=raw["updated_at"],
                        version=int(raw["version"]),
                    )
                )
            except Exception:
                # In MVP, ignore corrupted files (later: log + audit)
                continue
        return out

    def get_note(self, user_id: str, note_id: uuid.UUID) -> Note | None:
        path = _note_path(self.base_dir, user_id, note_id)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Note(
            id=uuid.UUID(raw["id"]),
            owner_user_id=raw["owner_user_id"],
            title=raw["title"],
            content=raw["content"],
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
            version=int(raw["version"]),
        )

    def update_note(self, user_id: str, note_id: uuid.UUID, title: str, content: str) -> Note | None:
        path = _note_path(self.base_dir, user_id, note_id)
        if not path.exists():
            return None

        raw = json.loads(path.read_text(encoding="utf-8"))
        now = _utc_now_iso()

        raw["title"] = title
        raw["content"] = content
        raw["updated_at"] = now
        raw["version"] = int(raw.get("version", 1)) + 1

        _atomic_write_json(path, raw)

        return Note(
            id=uuid.UUID(raw["id"]),
            owner_user_id=raw["owner_user_id"],
            title=raw["title"],
            content=raw["content"],
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
            version=int(raw["version"]),
        )
