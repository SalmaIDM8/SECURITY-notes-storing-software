from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _safe_user_dir(base_dir: Path, user_id: str) -> Path:
    # evitat path traversal
    if not user_id or any(ch in user_id for ch in ["/", "\\"]) or ".." in user_id:
        raise ValueError("Invalid user_id")
    return base_dir / "users" / user_id


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    hashed_password: str
    created_at: str


class UsersStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def _user_path(self, user_id: str) -> Path:
        return _safe_user_dir(self.base_dir, user_id) / "user.json"

    def get(self, user_id: str) -> Optional[UserRecord]:
        p = self._user_path(user_id)
        if not p.exists():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        return UserRecord(
            user_id=raw["user_id"],
            hashed_password=raw["hashed_password"],
            created_at=raw["created_at"],
        )

    def create(self, user_id: str, hashed_password: str) -> UserRecord:
        p = self._user_path(user_id)
        if p.exists():
            raise FileExistsError("User exists")

        p.parent.mkdir(parents=True, exist_ok=True)
        rec = UserRecord(
            user_id=user_id,
            hashed_password=hashed_password,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
        return rec
