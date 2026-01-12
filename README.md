**Group 17 – Abuse Frames–Based Security Requirements Analysis**  
- IDMANSOUR Salma  
- GARTANI Othmane  
- CRISTEA Ana  
- ILIESCU Miruna-Elena  

This repository contains a secure replicated note storage system (REST API + file-based storage + web front-end) and a security requirements analysis using **Abuse Frames** (Lin et al., 2003). The implementation is validated through automated security tests and reproducible browser demonstrations.

---

## Project Context

The system allows multiple users to store private textual notes with:
- strict user isolation,
- controlled sharing (read-only / read-write),
- a lock mechanism required for updates,
- replication across two servers through an event-based log.

Because the web front-end is hosted on a different origin/domain than the API, the project explicitly addresses cross-origin security threats (CORS + token handling).

---

## Base Problem Frame (Summary)

**Domains**
- **Machine (M):** RESTful Note Server (FastAPI) handling requests, access control, locks, and storage.
- **Lexical Domain (X):** File storage containing notes, metadata, locks, shares, and event logs.
- **Biddable Domain (B):** Users issuing note actions (create/read/update/share).
- **Causal Domains (C):** Supporting modules (authentication, replication).

**Functional Requirements**
- Users can create/read/update/delete their own notes.
- Users cannot access notes belonging to other users.
- Notes can be shared with other users in RO/RW mode.
- Updates require an explicit lock.
- Notes remain available despite single-server failures.

---

## Abuse Frames and Anti-Requirements (AR)

| Anti-Requirement | Threat Class | Summary |
|---|---|---|
| **AR-1** Unauthorized Note Disclosure | Interception | Spoof identity / bypass ownership checks |
| **AR-2** Unauthorized Note Modification | Modification | Modify without owning lock or permissions |
| **AR-3** Lock Starvation Attack | Denial of Access | Hold/reacquire locks indefinitely |
| **AR-4** Cross-Origin Token Theft (Perturbation) | Interception | Malicious front-end steals token and reads notes |
| **AR-5** Replication Desynchronization | Modification / DoA | Replay/inject/omit replication events |

---

## Security Machine (Countermeasures)

### Authentication & Authorization
- JWT authentication for strong identity binding.
- Legacy `X-User-Id` fallback for demo/tests, with **JWT precedence** (header spoofing prevented).
- ACL-style enforcement for ownership and sharing.

### Locking
- Exclusive lock required for note updates.
- Locks include TTL to prevent indefinite lock starvation.

### Cross-Origin Security (AR-4)
Mitigates \(v_4=\{uJWT, uCORS\}\):

- **HttpOnly cookie authentication (mitigates uJWT):**  
  `POST /auth/login_cookie` sets a cookie with:
  - `HttpOnly` (not accessible to JavaScript),
  - `SameSite=Strict`,
  - `Path=/`.

- **Strict CORS allowlist (mitigates uCORS):**  
  API allows only explicit trusted origins (e.g., `http://127.0.0.1:5173`).  
  Malicious origins do not receive `Access-Control-Allow-Origin`, so browsers block them.

### Replication Integrity (AR-5)
- Replication messages authenticated (HMAC token).
- Idempotency/replay protection and ordering checks.

---

## Security Tests

Two complementary test suites validate the Security Machine against the identified abuse frames:

- `test_security_interception.py`  
  Integration-level validation of access control and confidentiality (unauthorized reads/listing/share misuse, etc.).

- `test_anti_requirements.py`  
  Requirements-driven tests that directly refute AR-1, AR-2, AR-3, and AR-5 (JWT precedence, token expiry rejection, lock reuse prevention, lock TTL, replication replay/order).

- **AR-4 test added:**  
  `test_ar4_cookie_is_httponly_and_cors_is_strict_allowlist`  
  Validates:
  - `Set-Cookie` includes `HttpOnly` + `SameSite=Strict`,
  - legit origin is allowed by CORS,
  - malicious origin is not allowed by CORS.

---

## How to Run

### Prerequisites
- Python 3.x
- Virtual environment activated

### Backend configuration (`backend/.env`)
Create a `.env` file in `backend/`:

```env
JWT_SECRET=change-me-to-a-long-random-secret
CORS_ALLOW_ORIGINS=http://127.0.0.1:5173,http://localhost:5173

> Do not commit `.env` (add `backend/.env` to `.gitignore`).

### Start the backend (FastAPI)
From `backend/`:

```bash
uvicorn app.main:app --reload --port 8000

### Sanity check

```bash
curl http://127.0.0.1:8000/health
# {"ok": true}

### Start the frontend:
From the frontend folder:
 ```bash
python -m http.server 5173
```

Open:
```bash
http://127.0.0.1:5173/
```


## Create a Test User (API)

### Register
```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"user_id":"userA","password":"password123"}'
```

### Login
```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"userA","password":"password123"}'
```

```bash
curl -i -X POST http://127.0.0.1:8000/auth/login_cookie \
  -H "Content-Type: application/json" \
  -d '{"user_id":"userA","password":"password123"}'
```

Expected: a Set-Cookie header containing HttpOnly and SameSite=Strict.