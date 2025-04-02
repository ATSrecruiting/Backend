from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pathlib import Path
import shutil
from db.models import Attachment
from db.session import get_db
from helpers.cv import process_cv_async
import json
from schema.cv import UploadCVResponse
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()


@router.post("/upload_resume")
async def upload_file(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)

        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided.")
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
        cv_content = await process_cv_async(str(file_path))

        json_str = cv_content.replace("```json\n", "").replace("\n```", "")
        cv_data = json.loads(json_str)
        res = UploadCVResponse(
            file_id = file.id,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            file_path=str(file_path),
            cv_data=cv_data,
        )

        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
