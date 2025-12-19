# Backend Contracts

## Identity
- During development, user identity is provided via `X-User-Id` HTTP header.
- In production, this will be injected by authentication middleware.

## Identifiers
- note_id, share_id, lock_id are UUIDs.

## Error Codes
- 401: unauthenticated
- 403: forbidden
- 404: not found
- 409: conflict (lock / version)
- 422: invalid input

## File Layout
- Notes: data/users/<user_id>/notes/<note_id>.json
- Locks: data/locks/<note_id>.json
- Shares: data/shares/<share_id>.json
- Events: data/events/events.jsonl
