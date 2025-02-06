from pydantic import BaseModel


class UploadCVResponse(BaseModel):
    filename: str
    content_type: str
    file_path: str
    cv_data: any
