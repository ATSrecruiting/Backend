from typing import List
from pydantic import BaseModel
from uuid import UUID


class AttachmentUploadResponse(BaseModel):
    uuid: UUID
    filename: str
    content_type: str
    file_path: str


class ListAttachments(BaseModel):
    uuid: UUID
    name: str
    type: str


class GetFileURLRequest(BaseModel):
    attachments_ids: List[UUID]



class GetFileURLResponse(BaseModel):
    download_url: str
    filename: str
    file_id: UUID