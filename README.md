**Group 17 – Abuse Frames–Based Security Requirements Analysis**  
- IDMANSOUR Salma  
- GARTANI Othmane  
- CRISTEA Ana  
- ILIESCU Miruna-Elena  

This repository contains a secure replicated note storage system (REST API + file-based storage + web front-end) and a security requirements analysis using **Abuse Frames** (Lin et al., 2003). The implementation is validated through automated security tests and reproducible browser demonstrations.

## Security Analysis

This project includes a full security analysis using the Abuse Frames methodology, covering threat modeling, anti-requirements, and security validation tests.

📄 Full report: [Security Analysis Report](security-analysis-report.pdf)

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

This project is developed and tested primarily on Windows (PowerShell). The instructions below show a reliable, repeatable way to start the backend and frontend for development and for manual security testing (AR scenarios).

### Prerequisites
- Python 3.10+ installed and on PATH
- Git
- (Optional, for frontend) Node.js 18+ and npm

### Backend — quick start (recommended)
1. Open PowerShell, change to the `backend` folder and create/activate a virtual environment:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install Python dependencies (use the provided `requirements.txt`):

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
# If you see a ModuleNotFoundError for dotenv, install it explicitly:
python -m pip install python-dotenv
```

3. Create `backend/.env` (example values are placeholders — replace secrets for realistic testing):

```ini
JWT_SECRET=replace-with-a-long-random-secret
REPL_SECRET=replace-with-repl-secret
CORS_ALLOW_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
COOKIE_SECURE=0
```

### Start helper: `start-dev.ps1` 

The helper script `start-dev.ps1` is located at `backend\start-dev.ps1`.

What it does:
- Loads `backend/.env` into the current PowerShell session (using the Env: provider),
- Prints which variables were set,
- Starts the uvicorn dev server (`uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`).

You can run it from the `backend` folder (recommended):

```powershell
# from backend\
.\.venv\Scripts\Activate.ps1
.\start-dev.ps1
```


If you prefer to start the server manually without the helper, set the env vars in your session then start uvicorn:

```powershell
$env:JWT_SECRET = "your-secret"
$env:REPL_SECRET = "your-repl-secret"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

5. Quick health check (PowerShell):

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
# expected: {"ok": true}
```

If you need to set an environment variable just for the current session use:

```powershell
$env:JWT_SECRET = "your-secret"
# then start uvicorn manually if not using start-dev.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

To persist a variable across new terminals use `setx` (requires reopening terminals):

```powershell
setx JWT_SECRET "your-secret"
```

### Backend — common troubleshooting
- If you see `ModuleNotFoundError: No module named 'dotenv'`, install `python-dotenv` in the venv as shown above.
- If you see a `passlib`/`bcrypt` warning, installing `bcrypt` will remove it:

```powershell
python -m pip install bcrypt
# If building bcrypt fails on Windows, either install the Microsoft C++ Build Tools or allow passlib to fall back to pbkdf2_sha256 (safe for tests).
```

### Frontend — serve the UI

```powershell
# from the repository root or the frontend folder
cd frontend
# serve the current folder at port 5173
python -m http.server 5173
# open http://127.0.0.1:5173/
```

### Running tests
From the project root (with backend venv active):

```powershell
backend\.venv\Scripts\python.exe -m pytest -q
```
To run only the anti requirements tests:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_anti_requirements.py -q
```

Notes: `backend/tests/conftest.py` configures test-time env vars (`JWT_SECRET`, `REPL_SECRET`, `APP_DATA_DIR`) so tests run isolated and usually don't need manual `.env` setup.

### Example API quick actions (PowerShell)
Register a user:

```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/auth/register -ContentType 'application/json' -Body '{"user_id":"userA","password":"password123"}'
```

Login (token):

```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/auth/login -ContentType 'application/json' -Body '{"user_id":"userA","password":"password123"}'
```

Login (cookie mode, useful for AR-4 checks):

```powershell
# Use curl if you want to inspect headers; PowerShell's Invoke-RestMethod hides Set-Cookie
curl -i -X POST http://127.0.0.1:8000/auth/login_cookie -H "Content-Type: application/json" -d '{"user_id":"userA","password":"password123"}'
```

The cookie-based login sets an `HttpOnly` cookie with `SameSite=Strict` by design.



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
