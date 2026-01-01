from pathlib import Path
import json
import os
from typing import List

from fastapi import APIRouter, HTTPException, Request

from app.storage.event_log import Event
from app.storage.event_log import _events_path
from app.storage.notes_store import NotesStore

router = APIRouter(prefix="/replicate", tags=["replication"])

# DATA_DIR config via env var (consistent with other modules)
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DATA_DIR = Path(os.getenv("APP_DATA_DIR", str(DEFAULT_DATA_DIR)))
store = NotesStore(DATA_DIR)


def _read_events_for_user(base_dir: Path, user_id: str) -> List[dict]:
    p = _events_path(base_dir, user_id)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


@router.get("/events")
def get_events(user_id: str, since_event_id: str | None = None, limit: int = 100) -> List[dict]:
    """
    Return replication-ready events for a given user. For note-related events the result
    is enriched with a `payload` field containing the full note JSON (so the receiver can apply it).
    """
    events = _read_events_for_user(DATA_DIR, user_id)

    # find start index
    start = 0
    if since_event_id:
        for i, e in enumerate(events):
            if e.get("event_id") == since_event_id:
                start = i + 1
                break

    selected = events[start : start + limit]

    # enrich
    enriched = []
    for e in selected:
        ee = dict(e)
        note_id = ee.get("note_id")
        if ee.get("event_type") in ("NOTE_CREATED", "NOTE_UPDATED") and note_id:
            # attempt to include current note content from storage
            try:
                from uuid import UUID
                nid = UUID(str(note_id))
                note_obj = store.get_note(user_id=ee.get("user_id"), note_id=nid)
                if note_obj:
                    ee["payload"] = note_obj.to_dict()
            except Exception:
                pass
        enriched.append(ee)

    return enriched


def _ensure_replication_dir(base_dir: Path, user_id: str) -> Path:
    p = base_dir / "replication" / user_id
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.post("/events")
async def post_events(request: Request):
    """
    Accept a batch of enriched events and apply them idempotently.
    Payload: JSON array of event objects (as returned by GET /replicate/events).
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not isinstance(body, list):
        raise HTTPException(status_code=400, detail="Expected a JSON array")

    applied = 0
    for e in body:
        event_id = e.get("event_id")
        user_id = e.get("user_id")
        if not event_id or not user_id:
            continue

        rep_dir = _ensure_replication_dir(DATA_DIR, user_id)
        seen_file = rep_dir / "seen_events.txt"
        seen = set()
        if seen_file.exists():
            seen = set(x.strip() for x in seen_file.read_text(encoding="utf-8").splitlines() if x.strip())

        if event_id in seen:
            continue

        # apply event
        etype = e.get("event_type")
        if etype in ("NOTE_CREATED", "NOTE_UPDATED"):
            payload = e.get("payload") or {}
            try:
                # decide apply semantics using versions: naive policy -> accept if incoming version > local
                from uuid import UUID
                nid = UUID(str(payload.get("id"))) if payload.get("id") else None
                if nid is None:
                    # nothing to apply
                    pass
                else:
                    existing = store.get_note(user_id=user_id, note_id=nid)
                    incoming_version = int(payload.get("version", 1))
                    if existing is None:
                        store.apply_note_raw(payload)
                    else:
                        if incoming_version > existing.version:
                            store.apply_note_raw(payload)
                        else:
                            # ignore older or equal versions
                            pass
            except Exception:
                # ignore apply failures for now; in production log + alert
                pass

        # mark seen
        try:
            with seen_file.open("a", encoding="utf-8") as f:
                f.write(event_id + "\n")
        except Exception:
            pass

        applied += 1

    return {"applied": applied}
