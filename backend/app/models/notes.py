from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=50_000)


class NoteOut(BaseModel):
    id: str
    owner_user_id: str
    title: str
    content: str
    created_at: str
    updated_at: str
    version: int
