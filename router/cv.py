import tempfile
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pathlib import Path
import shutil
from db.models import Attachment
from db.session import get_db
from helpers.cv import process_cv_async
import json
from schema.cv import UploadCVResponse
from sqlalchemy.ext.asyncio import AsyncSession
from util.app_config import config # config has the env variable like this config.SQLALCHEMY_DATABASE_URI and all others
import boto3
from botocore.exceptions import ClientError
from botocore.client import ClientCreator
from util.s3 import get_s3_client
import uuid
import os


router = APIRouter()


@router.post("/upload_resume", response_model=UploadCVResponse)
async def upload_resume_to_s3(
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db),
    s3: ClientCreator = Depends(get_s3_client) # Inject S3 client here!
):
    # Now use the injected 's3' variable instead of the global 's3_client'
    
    # No need for this check, dependency injection handles failure
    # if not s3: 
    #     raise HTTPException(status_code=500, detail="S3 client not initialized.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    # --- Get Bucket Name ---
    bucket_name = config.AWS_S3_BUCKET_NAME
    if not bucket_name:
        raise HTTPException(status_code=500, detail="S3 bucket configuration missing.")

    # --- Generate Unique S3 Object Key ---
    file_extension = Path(file.filename).suffix
    file_uuid = str(uuid.uuid4())
    s3_object_key = f"resumes/{file_uuid}{file_extension}" 

    temp_file_path = None
    try:
        # --- Save to Temporary File for Processing ---
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name

        print(f"Temporary file created at: {temp_file_path}")
        
        cv_content_str = await process_cv_async(temp_file_path)
        
        # ... (rest of CV parsing logic remains the same) ...
        try:
            json_str = cv_content_str.replace("```json\n", "").replace("\n```", "")
            cv_data = json.loads(json_str)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Error parsing processed CV data.")


        # --- Upload Temporary File to S3 ---
        try:
             # Use the injected 's3' client
             s3.upload_file(  # type: ignore
                 temp_file_path, 
                 bucket_name, 
                 s3_object_key,
                 ExtraArgs={'ContentType': file.content_type or 'application/octet-stream'} 
             )
        except ClientError:
            raise HTTPException(status_code=500, detail="Could not upload file to storage.")
        except Exception:
            raise HTTPException(status_code=500, detail="An unexpected error occurred during file upload.")

        # --- Save Metadata to Database ---
        # ... (database logic remains the same, using db_file = Attachment(...) etc) ...
        db_file = Attachment(
            id=file_uuid,
            filename=file.filename, 
            file_path=s3_object_key, 
            content_type=file.content_type or 'application/octet-stream',
        )
        db.add(db_file)
        await db.commit()
        await db.refresh(db_file)
        


        # --- Prepare Response ---
        # ... (response preparation remains the same) ...
        res = UploadCVResponse(
            file_id=db_file.id,
            filename=db_file.filename,
            content_type=db_file.content_type,
            file_path=db_file.file_path, # S3 Key
            cv_data=cv_data,
        )
        return res

    except HTTPException:
         # Re-raise HTTPException to ensure FastAPI handles it correctly
         raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal server error occurred. {str(e)}")
    finally:
        # --- Clean up Temporary File ---
        # ... (temp file cleanup logic remains the same) ...
        if temp_file_path and Path(temp_file_path).exists():
            os.remove(temp_file_path)
        await file.seek(0)