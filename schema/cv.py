from uuid import UUID
from pydantic import BaseModel
from typing import Any


class UploadCVResponse(BaseModel):
    file_id: UUID
    filename: str
    content_type: str
    file_path: str
    cv_data: Any
