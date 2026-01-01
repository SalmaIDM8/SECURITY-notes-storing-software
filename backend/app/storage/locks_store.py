import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.storage.notes_store import _safe_user_dir, _note_path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(path)


def _locks_dir(base_dir: Path, user_id: str) -> Path:
    # data/users/<user>/locks
    notes_dir = _safe_user_dir(base_dir, user_id)  # .../notes
    return notes_dir.parent / "locks"


def _lock_path(base_dir: Path, user_id: str, note_id: uuid.UUID) -> Path:
    return _locks_dir(base_dir, user_id) / f"{note_id}.json"


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


@dataclass(frozen=True)
class Lock:
    lock_id: uuid.UUID
    note_id: uuid.UUID
    owner_user_id: str
    created_at: str
    expires_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "lock_id": str(self.lock_id),
            "note_id": str(self.note_id),
            "owner_user_id": self.owner_user_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


class LocksStore:
    def __init__(self, base_dir: Path, default_ttl_seconds: int = 300):
        self.base_dir = base_dir
        self.default_ttl_seconds = default_ttl_seconds

    def _is_expired(self, raw: dict[str, Any]) -> bool:
        return _utc_now() >= _parse_dt(raw["expires_at"])

    def acquire_lock(self, user_id: str, note_id: uuid.UUID) -> Lock | None:
        # no leak: lock only if note exists for this user
        if not _note_path(self.base_dir, user_id, note_id).exists():
            return None

        p = _lock_path(self.base_dir, user_id, note_id)
        if p.exists():
            raw = json.loads(p.read_text(encoding="utf-8"))
            if not self._is_expired(raw):
                # idempotent: return existing active lock
                return Lock(
                    lock_id=uuid.UUID(raw["lock_id"]),
                    note_id=uuid.UUID(raw["note_id"]),
                    owner_user_id=raw["owner_user_id"],
                    created_at=raw["created_at"],
                    expires_at=raw["expires_at"],
                )
            # expired -> overwrite below

        now = _utc_now()
        lock = Lock(
            lock_id=uuid.uuid4(),
            note_id=note_id,
            owner_user_id=user_id,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self.default_ttl_seconds)).isoformat(),
        )
        _atomic_write_json(p, lock.to_dict())
        return lock

    def release_lock(self, user_id: str, note_id: uuid.UUID) -> bool:
        # no leak: require note exists for this user
        if not _note_path(self.base_dir, user_id, note_id).exists():
            return False

        p = _lock_path(self.base_dir, user_id, note_id)
        if not p.exists():
            return False

        raw = json.loads(p.read_text(encoding="utf-8"))
        if self._is_expired(raw):
            try:
                p.unlink()
            except OSError:
                pass
            return False

        try:
            p.unlink()
        except OSError:
            pass
        return True

    def require_valid_lock(self, user_id: str, note_id: uuid.UUID, lock_id: uuid.UUID) -> bool:
        p = _lock_path(self.base_dir, user_id, note_id)
        if not p.exists():
            return False

        raw = json.loads(p.read_text(encoding="utf-8"))
        if self._is_expired(raw):
            try:
                p.unlink()
            except OSError:
                pass
            return False

        return raw.get("owner_user_id") == user_id and raw.get("lock_id") == str(lock_id)
