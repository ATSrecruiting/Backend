
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
from schema.attachments import AttachmentUploadResponse
from db.models import Attachment
from fastapi import Depends
from db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()


@router.post("/upload", response_model=AttachmentUploadResponse)
async def upload_file(file: UploadFile = File(...), db:AsyncSession=Depends(get_db)):
    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)

        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename must not be empty")
        file_path = upload_dir / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file = Attachment(
            filename=file.filename,
            file_path=str(file_path),
            content_type=file.content_type
        )
        db.add(file)
        await db.commit()

        return AttachmentUploadResponse(
            filename=file.filename,
            content_type=file.content_type,
            file_path=str(file_path),
            uuid=file.id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    



