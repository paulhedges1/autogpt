from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NoteCreate(BaseModel):
    contact_id: int
    body: str
    author: Optional[str] = None


class NoteRead(BaseModel):
    id: int
    contact_id: int
    body: str
    author: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
