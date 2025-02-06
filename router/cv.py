from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
from helpers.cv import process_cv_async
import json
from schema.cv import UploadCVResponse


router = APIRouter()


async def upload_file(file: UploadFile = File(...)):
    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)

        file_path = upload_dir / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        cv_content = await process_cv_async(str(file_path))

        json_str = cv_content.replace("```json\n", "").replace("\n```", "")
        cv_data = json.loads(json_str)
        res = UploadCVResponse(
            filename=file.filename,
            content_type=file.content_type,
            file_path=str(file_path),
            cv_data=cv_data,
        )

        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
