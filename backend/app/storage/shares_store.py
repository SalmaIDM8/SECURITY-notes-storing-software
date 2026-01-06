import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from app.storage.notes_store import _safe_user_dir, _note_path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _shares_dir(base_dir: Path, owner_user_id: str) -> Path:
    # data/users/<owner>/shares
    notes_dir = _safe_user_dir(base_dir, owner_user_id)  # .../notes
    return notes_dir.parent / "shares"


def _share_path(base_dir: Path, owner_user_id: str, share_id: uuid.UUID) -> Path:
    return _shares_dir(base_dir, owner_user_id) / f"{share_id}.json"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


@dataclass(frozen=True)
class Share:
    share_id: uuid.UUID
    owner_user_id: str
    shared_with_user_id: str
    note_id: uuid.UUID
    mode: str  # "ro" or "rw"
    created_at: str
    expires_at: Optional[str] = None
    revoked: bool = False

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= datetime.fromisoformat(self.expires_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "share_id": str(self.share_id),
            "owner_user_id": self.owner_user_id,
            "shared_with_user_id": self.shared_with_user_id,
            "note_id": str(self.note_id),
            "mode": self.mode,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
        }


class SharesStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def create_share(
        self,
        owner_user_id: str,
        note_id: uuid.UUID,
        shared_with_user_id: str,
        mode: str,
        ttl_minutes: Optional[int] = None,
    ) -> Share:
        # note must exist for owner (no leakage)
        if not _note_path(self.base_dir, owner_user_id, note_id).exists():
            raise FileNotFoundError("Note not found")

        if mode not in ("ro", "rw"):
            raise ValueError("Invalid share mode")

        share_id = uuid.uuid4()
        now = _utc_now_iso()
        expires_at = None
        if ttl_minutes is not None:
            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat()

        share = Share(
            share_id=share_id,
            owner_user_id=owner_user_id,
            shared_with_user_id=shared_with_user_id,
            note_id=note_id,
            mode=mode,
            created_at=now,
            expires_at=expires_at,
            revoked=False,
        )
        _atomic_write_json(_share_path(self.base_dir, owner_user_id, share_id), share.to_dict())
        return share

    def get_share(self, owner_user_id: str, share_id: uuid.UUID) -> Optional[Share]:
        p = _share_path(self.base_dir, owner_user_id, share_id)
        if not p.exists():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        return Share(
            share_id=uuid.UUID(raw["share_id"]),
            owner_user_id=raw["owner_user_id"],
            shared_with_user_id=raw["shared_with_user_id"],
            note_id=uuid.UUID(raw["note_id"]),
            mode=raw["mode"],
            created_at=raw["created_at"],
            expires_at=raw.get("expires_at"),
            revoked=bool(raw.get("revoked", False)),
        )

    def revoke_share(self, owner_user_id: str, share_id: uuid.UUID) -> bool:
        s = self.get_share(owner_user_id, share_id)
        if s is None:
            return False
        raw = s.to_dict()
        raw["revoked"] = True
        _atomic_write_json(_share_path(self.base_dir, owner_user_id, share_id), raw)
        return True

    def find_share_for_user(self, share_id: uuid.UUID, user_id: str) -> Optional[Share]:
        """
        Since shares are stored under owners, we search all users/*/shares for a matching share_id.
        This is ok for MVP. (Later: index file)
        """
        users_dir = self.base_dir / "users"
        if not users_dir.exists():
            return None

        for owner_dir in users_dir.iterdir():
            if not owner_dir.is_dir():
                continue
            p = owner_dir / "shares" / f"{share_id}.json"
            if not p.exists():
                continue
            raw = json.loads(p.read_text(encoding="utf-8"))
            if raw.get("shared_with_user_id") != user_id:
                continue
            s = Share(
                share_id=uuid.UUID(raw["share_id"]),
                owner_user_id=raw["owner_user_id"],
                shared_with_user_id=raw["shared_with_user_id"],
                note_id=uuid.UUID(raw["note_id"]),
                mode=raw["mode"],
                created_at=raw["created_at"],
                expires_at=raw.get("expires_at"),
                revoked=bool(raw.get("revoked", False)),
            )
            if s.revoked or s.is_expired():
                return None
            return s

        return None
