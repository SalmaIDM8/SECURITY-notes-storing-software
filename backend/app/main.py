from fastapi import FastAPI

app = FastAPI(title="Secure Notes API")

@app.get("/health")
def health():
    return {"ok": True}

