import pdfplumber
from sqlalchemy import update
from sqlalchemy.sql.expression import select
from db.models import Candidate
from db.models import Attachment
import json
from sentence_transformers import SentenceTransformer
from db.session import SessionLocal



async def embed_candidates_data(candidate_id: int):
    # Create a new database session for the background task
    async with SessionLocal() as db:
        try:
            # Query candidate and resume data
            query = await db.execute(
                select(
                    Candidate.id,
                    Candidate.user_id,
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
                    Candidate.resume_id,
                    Attachment.file_path.label('resume_path')
                )
                .join(Attachment, Candidate.resume_id == Attachment.id, isouter=True)
                .where(Candidate.id == candidate_id)
            )
            result = query.one_or_none()

            if result is None or result.resume_path is None:
                raise ValueError("Candidate not found or resume path is missing.")

            # Extract resume text using pdfplumber
            with pdfplumber.open(result.resume_path) as pdf:
                resume_text = "\n\n".join(page.extract_text() for page in pdf.pages)

            # Aggregate candidate data into a single string.
            candidate_details = f"""
            First Name: {result.first_name}
            Last Name: {result.last_name}
            Email: {result.email}
            Phone Number: {result.phone_number}
            Address: {json.dumps(result.address)}
            Date of Birth: {result.date_of_birth}
            Years of Experience: {result.years_of_experience}
            Job Title: {result.job_title}
            Work Experience: {json.dumps(result.work_experience)}
            Education: {json.dumps(result.education)}
            Skills: {json.dumps(result.skills)}
            Certifications: {json.dumps(result.certifications)}
            Resume Text: {resume_text}
            """

            # Generate embedding
            model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
            embedding_vector = model.encode(candidate_details).tolist()

            # Update the candidate record with the embedding
            stmt = (
                update(Candidate)
                .where(Candidate.id == candidate_id)
                .values(embedding=embedding_vector, is_embedding_ready=True)
            )
            await db.execute(stmt)
            await db.commit()

        except Exception as e:
            # Rollback the transaction in case of an error
            await db.rollback()
            raise e
        finally:
            # Ensure the session is closed
            await db.close()
    
    