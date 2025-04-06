from datetime import datetime
from pydantic import BaseModel


class CreateVacancyRequest(BaseModel):
    title: str
    description: str
    location: str
    end_date: datetime


class CreateVacancyResponse(BaseModel):
    id: int
    recruiter_id: int
    title: str
    description: str
    location: str
    is_active: bool
    created_at: datetime
    end_date: datetime
