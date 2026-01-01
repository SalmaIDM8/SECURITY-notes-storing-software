import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.storage.notes_store import _safe_user_dir


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _events_dir(base_dir: Path, user_id: str) -> Path:
    # _safe_user_dir returns .../users/<user_id>/notes
    notes_dir = _safe_user_dir(base_dir, user_id)
    return notes_dir.parent / "events"


def _events_path(base_dir: Path, user_id: str) -> Path:
    return _events_dir(base_dir, user_id) / "events.log"


@dataclass(frozen=True)
class Event:
    event_type: str
    user_id: str
    note_id: Optional[str] = None
    lock_id: Optional[str] = None
    meta: Optional[dict[str, Any]] = None

    def to_json_line(self) -> str:
        obj = {
            "event_id": str(uuid.uuid4()),
            "event_type": self.event_type,
            "ts": _utc_now_iso(),
            "user_id": self.user_id,
            "note_id": self.note_id,
            "lock_id": self.lock_id,
            "meta": self.meta or {},
        }
        return json.dumps(obj, ensure_ascii=False)


class EventLog:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def emit(self, event: Event) -> None:
        path = _events_path(self.base_dir, event.user_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        # append-only, durable write
        with path.open("a", encoding="utf-8") as f:
            f.write(event.to_json_line() + "\n")
            f.flush()
            os.fsync(f.fileno())
