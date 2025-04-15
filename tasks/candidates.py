import pdfplumber
from sqlalchemy import update
from sqlalchemy.sql.expression import select
from db.models import Candidate
from db.models import Attachment
import json
from sentence_transformers import SentenceTransformer
from db.session import SessionLocal
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from util.app_config import config
import os
import io


async def embed_candidates_data(candidate_id: int):
    """
    Background task to fetch candidate data, download resume from S3,
    extract text, generate embedding, and update the database.
    """
    
    # --- Initialize S3 client within the task ---
    # We need a client instance here, separate from FastAPI's request lifecycle.
    s3_client = None
    print ("starting background task")
    try:
        aws_region = getattr(config, 'AWS_REGION')
        if aws_region:
            s3_client = boto3.client('s3', region_name=aws_region)
        else:
            # Rely on default config or IAM role
            s3_client = boto3.client('s3')
        
        bucket_name = getattr(config, 'AWS_S3_BUCKET_NAME')
        if not bucket_name:
             pass 

    except (BotoCoreError, ClientError, Exception) as e:
        raise ValueError(f"Failed to create S3 client: {e}")

    async with SessionLocal() as db:
        try:
            # Query candidate and resume data (resume_path is now the S3 key)
            query = await db.execute(
                select(
                    # ... (select all your Candidate fields) ...
                    Candidate.id,
                    Candidate.first_name,
                    Candidate.last_name,
                    Candidate.email,
                    Candidate.phone_number,
                    Candidate.address,
                    Candidate.date_of_birth,
                    Candidate.years_of_experience,
                    Candidate.job_title,
                    Candidate.work_experience,
                    Candidate.education,
                    Candidate.skills,
                    Candidate.certifications,
                    Attachment.file_path.label("s3_resume_key"), # Renamed label for clarity
                )
                .join(Attachment, Candidate.resume_id == Attachment.id, isouter=True)
                .where(Candidate.id == candidate_id)
            )
            result = query.mappings().one_or_none() # Use mappings() for dict-like access

            if result is None:
                 return 
            
            s3_key = result.get("s3_resume_key") # Use .get() for safety

            if not s3_key:
                # Decide action: maybe embed without resume text, or just mark as failed?
                # For now, let's try embedding without resume text
                resume_text = "No resume file associated."
                # Or raise an error if resume is mandatory:
                # raise ValueError("Resume S3 key is missing for candidate.")
            elif not s3_client or not bucket_name:
                # Decide action: Embed without resume? Mark as failed?
                resume_text = "Error: Could not access resume file storage."
                # Or raise an error:
                # raise ConnectionError("S3 client/config not available to download resume.")
            else:
                 # --- Download Resume from S3 ---
                try:
                    s3_response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                    # Read the PDF content into memory
                    pdf_content_bytes = s3_response['Body'].read()
                    # Create an in-memory file-like object
                    pdf_file_like_object = io.BytesIO(pdf_content_bytes)
                    
                    # --- Extract resume text using pdfplumber ---
                    # pdfplumber can open file-like objects
                    with pdfplumber.open(pdf_file_like_object) as pdf:
                        resume_text = "\n\n".join(page.extract_text() or "" for page in pdf.pages) # Handle None from extract_text

                except ClientError as e:
                    # Decide action: embed without resume, mark as error?
                    resume_text = f"Error: Could not download or process resume file from storage ({e})."
                    # Or re-raise or handle specific codes like NoSuchKey
                    # if e.response['Error']['Code'] == 'NoSuchKey': ...
                except Exception:
                     resume_text = "Error: Failed to process resume PDF content."


            candidate_details_list = []
            for key, value in result.items():
                 if key != "s3_resume_key": # Exclude the key itself
                     # Handle potential JSON fields if they are still strings
                     try:
                         if isinstance(value, str) and key in ['address', 'work_experience', 'education', 'skills', 'certifications']:
                              # Attempt to pretty-print if it's JSON-like string, otherwise use as is
                              try: 
                                   parsed_json = json.loads(value)
                                   formatted_value = json.dumps(parsed_json, indent=2)
                              except json.JSONDecodeError:
                                   formatted_value = value # Use original string if not valid JSON
                         else:
                              formatted_value = value
                         candidate_details_list.append(f"{key.replace('_', ' ').title()}: {formatted_value}")
                     except Exception:
                         candidate_details_list.append(f"{key.replace('_', ' ').title()}: {value}") # Fallback

            candidate_details_list.append(f"Resume Text: {resume_text}")
            candidate_details = "\n".join(candidate_details_list)
            
            print ("starting embedding")
            model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
            embedding_vector = model.encode(candidate_details).tolist()

            # --- Update the candidate record with the embedding ---
            stmt = (
                update(Candidate)
                .where(Candidate.id == candidate_id)
                .values(embedding=embedding_vector, is_embedding_ready=True) 
            )
            await db.execute(stmt)
            await db.commit()

        except Exception:
            
            await db.rollback()

