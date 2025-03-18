








import uuid
from pydantic import BaseModel
from uuid import UUID

class AttachmentUploadResponse(BaseModel):
    uuid: UUID
    filename: str
    content_type: str
    file_path: str


class ListAttachments(BaseModel):
    uuid: UUID
    name : str
    url : str