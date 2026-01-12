import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.notes import router as notes_router
from app.api.replication import router as replication_router
from app.api.auth import router as auth_router
from app.api.shares import router as shares_router

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="Secure Notes API")

# CORS: strict allowlist
# If CORS_ALLOW_ORIGINS is set, use it (comma-separated). Otherwise allow common dev origins.
origins_env = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()] if origins_env else [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CORS: strict allowlist (for cases where frontend is on another domain)
origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()]

if allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(auth_router)
app.include_router(notes_router)
app.include_router(replication_router)
app.include_router(shares_router)

@app.get("/health")
def health():
    return {"ok": True}
