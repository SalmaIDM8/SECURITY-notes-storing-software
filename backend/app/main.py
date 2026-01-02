from fastapi import FastAPI

from app.api.notes import router as notes_router
from app.api.replication import router as replication_router
from app.api.auth import router as auth_router
from app.api.shares import router as shares_router

app = FastAPI(title="Secure Notes API")

app.include_router(auth_router)
app.include_router(notes_router)
app.include_router(replication_router)
app.include_router(shares_router)

@app.get("/health")
def health():
    return {"ok": True}
