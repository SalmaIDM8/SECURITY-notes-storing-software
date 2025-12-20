from fastapi import Header, HTTPException


def get_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id")
    return x_user_id
