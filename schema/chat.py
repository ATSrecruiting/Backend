from typing import List
from uuid import UUID
from pydantic import BaseModel


class CreateTempSessionRequest(BaseModel):
    candidates: List[int]


class CreateTempSessionResponse(BaseModel):
    session_id: UUID


class SendMessageRequest(BaseModel):
    model: str
    message: str
    session_id: str
