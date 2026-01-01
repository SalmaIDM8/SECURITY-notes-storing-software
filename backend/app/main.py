from fastapi import FastAPI

from app.api.notes import router as notes_router

app = FastAPI(title="Secure Notes API")

app.include_router(notes_router)


@app.get("/health")
def health():
    return {"ok": True}
