from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from pathlib import Path

from fastapi.responses import RedirectResponse
from sqlalchemy import select
from schema.attachments import AttachmentUploadResponse, GetFileURLRequest, GetFileURLResponse
from db.models import Attachment
from fastapi import Depends
from db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
import boto3
from botocore.exceptions import ClientError
from util.s3 import get_s3_client
from util.app_config import config
import uuid

router = APIRouter()


@router.post("/upload", response_model=AttachmentUploadResponse)
async def upload_file_to_s3( # Renamed function for clarity and consistency
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    s3 = Depends(get_s3_client) # Inject S3 client dependency
):
    """
    Uploads a generic file to S3 and saves metadata to the database.
    """
    # --- 1. Validate Filename ---
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided."
        )

    # --- 2. Get S3 Bucket Configuration ---
    bucket_name = config.AWS_S3_BUCKET_NAME
    if not bucket_name:

         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Server configuration error [S3 Bucket]."
         )

    # --- 3. Generate Unique S3 Object Key ---
    file_extension = Path(file.filename).suffix
    file_uuid = str(uuid.uuid4())
    s3_object_key = f"general_uploads/{file_uuid}{file_extension}"

    try:
        # --- 4. Upload File Object Directly to S3 ---
        # upload_fileobj is efficient as it streams directly from the UploadFile
        s3.upload_fileobj(
            file.file,  # The file-like object provided by FastAPI's UploadFile
            bucket_name,
            s3_object_key,
            ExtraArgs={
                # Set the ContentType for proper handling by browsers/clients
                'ContentType': file.content_type or 'application/octet-stream'
            }
        )

    except ClientError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not upload file to storage."
        )
    except Exception:
        # Catch unexpected errors during upload

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during file upload."
        )

    db_file = None # Initialize in case DB operation fails before assignment
    try:
         # --- 5. Save Metadata to Database ---
        db_file = Attachment(
            id = file_uuid,
            filename=file.filename,
            file_path=s3_object_key, # IMPORTANT: Store the S3 Object Key, not a local path
            content_type=file.content_type or 'application/octet-stream',
        )
        db.add(db_file)
        await db.commit()
        await db.refresh(db_file) # To get the auto-generated ID


        # --- 6. Prepare and Return Response ---
        # Note: The 'file_path' in the response now contains the S3 Object Key.
        # The client will need a separate endpoint (like /download_file_url/{id})
        # to get an actual downloadable URL if needed.
        return AttachmentUploadResponse(
            filename=db_file.filename,
            content_type=db_file.content_type,
            file_path=db_file.file_path, # S3 Object Key
            uuid=db_file.id,             # Database primary key ID
        )
    except Exception:
        try:
            s3.delete_object(Bucket=bucket_name, Key=s3_object_key)
        except ClientError:
            pass

        raise HTTPException(
            status_code=500,
            detail="Failed to save file metadata after successful upload. Upload rolled back."
        )
    finally:
        pass




@router.get("/downloadresumeurl/{file_id}",
            
            summary="Get a pre-signed URL to download a resume",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def get_resume_download_url(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    s3 = Depends(get_s3_client)
):
    """
    Retrieves a temporary, pre-signed URL for downloading a specific resume file.
    """
    # 1. Fetch file metadata from the database
    db_file = await db.get(Attachment, file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found.")

    # 2. Get necessary info
    bucket_name = config.AWS_S3_BUCKET_NAME
    s3_object_key = db_file.file_path # This is the key stored during upload
    original_filename = db_file.filename # Good to have for the download

    if not bucket_name:
         raise HTTPException(status_code=500, detail="S3 bucket configuration missing.")
    if not s3_object_key:
         raise HTTPException(status_code=404, detail="File path (S3 key) not found in database record.")


    # 3. Generate the pre-signed URL
    try:
        # You can customize the expiration time (in seconds)
        expiration = 3600 # e.g., 1 hour

        # Add ResponseContentDisposition to suggest filename to browser
        presigned_url:str = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': s3_object_key,
                'ResponseContentDisposition': f'attachment; filename="{original_filename}"'
            },
            ExpiresIn=expiration
        )
    except ClientError:
        raise HTTPException(status_code=500, detail="Could not generate download link.")
    except Exception:
         raise HTTPException(status_code=500, detail="An unexpected error occurred.")

    # 4. Return a RedirectResponse
    if not presigned_url:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate download URL.")

    return RedirectResponse(url=presigned_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)




@router.post("/batch_download", response_model=List[GetFileURLResponse])
async def batch_download_files(
    request_body: GetFileURLRequest,
    db: AsyncSession = Depends(get_db),
    s3 = Depends(get_s3_client)):
    """
    Retrieves a list of pre-signed URLs for downloading multiple files.
    """
 
    bucket_name = config.AWS_S3_BUCKET_NAME
    if not bucket_name:
        raise HTTPException(status_code=500, detail="S3 bucket configuration missing.")
    
    stmt = select(Attachment).where(Attachment.id.in_(request_body.attachments_ids))
    result = await db.execute(stmt)
    db_files = result.scalars().all()

    if not db_files:
        raise HTTPException(status_code=404, detail="No files found for the provided IDs.")
    
    # Helper function to determine content type
    def get_content_type(filename):
        """Get the content type based on the file extension."""
        extension = filename.split('.')[-1].lower() if '.' in filename else ''
        content_types = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
            'webp': 'image/webp',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'txt': 'text/plain',
            'csv': 'text/csv',
            'html': 'text/html',
            'htm': 'text/html',
            'xml': 'application/xml',
            'json': 'application/json',
            'zip': 'application/zip',
            'rar': 'application/x-rar-compressed',
            'tar': 'application/x-tar',
            'gz': 'application/gzip',
        }
        return content_types.get(extension, 'application/octet-stream')
    
    # 2. Generate pre-signed URLs for each file
    file_urls = []
    for db_file in db_files:
        s3_object_key = db_file.file_path
        original_filename = db_file.filename
        content_type = get_content_type(original_filename)
        
        # Determine content disposition based on file type
        # Use 'inline' for PDFs and images to display in browser
        # Use 'attachment' for other files to download
        disposition_type = 'inline' if content_type.startswith(('application/pdf', 'image/')) else 'attachment'

        try:
            expiration = 3600  # e.g., 1 hour
            presigned_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': s3_object_key,
                    'ResponseContentType': content_type,
                    'ResponseContentDisposition': f'inline; filename="{original_filename}"',
                    # Add CORS headers
                    'ResponseCacheControl': 'no-cache',
                    'ResponseExpires': '0',
                },
                ExpiresIn=expiration
            )
        except ClientError:
            raise HTTPException(status_code=500, detail="Could not generate download link.")
        except Exception:
            raise HTTPException(status_code=500, detail="An unexpected error occurred.")

        file_urls.append(GetFileURLResponse(
            download_url=presigned_url,
            filename=db_file.filename,
            file_id=db_file.id
        ))
    # 3. Return the list of file URLs
    return file_urls