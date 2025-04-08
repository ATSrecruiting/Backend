from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.Oth2 import get_current_user
from auth.password import hash_password

from schema.candidates import (
    Address,
    GetCandidatePersonalInfo,
    GetCandidateWorkExperience,
    ListCandidatesFromSessionIdResponse,
    RegisterCandidateRequest,
    RegisterCandidateResponse,
    CVData,
    ListCandidatesResponse,
    VerifyWorkExperienceResponse,
    WorkExpAttachment,
    WorkExperience,
    VerificationDetail,
    VerificationDetailResponse,
    UnverifyWorkExperienceResponse,
)
from schema.pagination import Pagination

from db.models import Attachment, Candidate, User, TempChatSession, Recruiter
from db.session import get_db

from tasks.candidates import embed_candidates_data
import json
from typing import Dict
from uuid import UUID
from sqlalchemy import update


router = APIRouter(prefix="/candidates")


@router.post("/register", response_model=RegisterCandidateResponse)
async def create_candidate_account(
    account_data: RegisterCandidateRequest, db: AsyncSession = Depends(get_db)
):
    try:
        password_hash = hash_password(account_data.password)
        user = User(
            username=account_data.username,
            email=account_data.email,
            password=password_hash,
            account_type="candidate",
        )
        db.add(user)
        await db.commit()
        return RegisterCandidateResponse(
            user_id=user.id, username=user.username, email=user.email
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/personal_info")
async def update_personal_info(
    candidate_data: CVData,
    background_tasks: BackgroundTasks,
    user_id: int = Query(..., description="User ID of the candidate"),
    db: AsyncSession = Depends(get_db),
):
    try:
        candidate = Candidate(
            user_id=user_id,
            first_name=candidate_data.first_name,
            last_name=candidate_data.last_name,
            email=candidate_data.email,
            phone_number=candidate_data.phone_number,
            address=candidate_data.address.model_dump()
            if candidate_data.address
            else None,
            date_of_birth=None,
            years_of_experience=candidate_data.years_of_experience,
            job_title=candidate_data.job_title,
            work_experience=[
                work.model_dump_json() for work in candidate_data.work_experience
            ]
            if candidate_data.work_experience
            else [],
            education=[edu.model_dump_json() for edu in candidate_data.education]
            if candidate_data.education
            else [],
            skills=candidate_data.skills.model_dump()
            if candidate_data.skills
            else None,
            certifications=[
                cert.model_dump_json() for cert in candidate_data.certifications
            ]
            if candidate_data.certifications
            else [],
            resume_id=candidate_data.file_id,
        )
        db.add(candidate)
        await db.commit()
        background_tasks.add_task(embed_candidates_data, candidate.id)

        return {"message": "Personal info updated successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ListCandidatesResponse])
async def list_candidates(
    deps: Tuple[User, AsyncSession] = Depends(get_current_user),
    pagination: Pagination = Depends(),
    search: str = Query(None, description="Search by first name or last name"),
):
    try:
        _, db = deps
        query = select(Candidate)

        if search:
            query = query.filter(
                (Candidate.first_name.ilike(f"%{search}%"))
                | (Candidate.last_name.ilike(f"%{search}%"))
            )

        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.limit)

        # Execute query
        result = await db.execute(query)
        print("ending")
        candidates = result.scalars().all()
        print("ending2")

        # Convert SQLAlchemy models to response models
        return [
            ListCandidatesResponse(
                id=candidate.id,
                first_name=candidate.first_name,
                last_name=candidate.last_name,
                email=candidate.email,
                phone_number=candidate.phone_number,
                date_of_birth=candidate.date_of_birth.isoformat()
                if candidate.date_of_birth
                else "2000-01-01",
                years_of_experience=float(candidate.years_of_experience)
                if candidate.years_of_experience
                else 0.0,
                job_title=candidate.job_title,
                status=candidate.status if candidate.status else "Applied",
                created_at=candidate.created_at.isoformat()
                if candidate.created_at
                else "2000-01-01",
                tags=candidate.skills["technical_skills"][:3],
                rating=5,
            )
            for candidate in candidates
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching candidates: {str(e)}"
        )


@router.get("/by_id", response_model=List[ListCandidatesFromSessionIdResponse])
async def list_candidates_by_id(
    session_id: str = Query(..., description="Session ID to fetch candidates from"),
    db: AsyncSession = Depends(get_db),
):
    try:
        if session_id is None or not session_id:
            raise HTTPException(status_code=400, detail="Invalid session ID")

        session_q = await db.execute(
            select(TempChatSession).where(TempChatSession.id == session_id)
        )
        temp_session = session_q.scalars().first()
        if temp_session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        candidate_ids = temp_session.candidates
        result = await db.execute(
            select(Candidate).filter(Candidate.id.in_(candidate_ids))
        )
        candidates = result.scalars().all()
        if not candidates:
            raise HTTPException(status_code=404, detail="Candidates not found")
        return [
            ListCandidatesFromSessionIdResponse(
                id=candidate.id,
                first_name=candidate.first_name,
                last_name=candidate.last_name,
                years_of_experience=candidate.years_of_experience,
                job_title=candidate.job_title,
            )
            for candidate in candidates
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similarity_search", response_model=List[ListCandidatesResponse])
async def similarity_search(
    search: str = Query(..., description="Search by first name or last name"),
    db: AsyncSession = Depends(get_db),
    pagination: Pagination = Depends(),
):
    try:
        model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        query_embedding = model.encode(search).tolist()
        stmt = (
            select(Candidate)
            .order_by(Candidate.embedding.cosine_distance(query_embedding))
            .limit(pagination.limit)
        )
        results = await db.execute(stmt)
        candidates = results.scalars().all()

        return [
            ListCandidatesResponse(
                id=candidate.id,
                first_name=candidate.first_name,
                last_name=candidate.last_name,
                email=candidate.email,
                phone_number=candidate.phone_number,
                date_of_birth=candidate.date_of_birth.isoformat()
                if candidate.date_of_birth
                else "2000-01-01",
                years_of_experience=float(candidate.years_of_experience)
                if candidate.years_of_experience
                else 0.0,
                job_title=candidate.job_title,
                status=candidate.status if candidate.status else "Applied",
                created_at=candidate.created_at.isoformat()
                if candidate.created_at
                else "2000-01-01",
                tags=candidate.skills["technical_skills"][:3],
                rating=5,
            )
            for candidate in candidates
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching candidates: {str(e)}"
        )


@router.get("/{candidate_id}/personal_info", response_model=GetCandidatePersonalInfo)
async def get_candidate_personal_info(
    candidate_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Candidate).filter(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return GetCandidatePersonalInfo(
            first_name=candidate.first_name,
            last_name=candidate.last_name,
            job_title=candidate.job_title,
            email=candidate.email,
            phone_number=candidate.phone_number,
            address=Address(**candidate.address) if candidate.address else None,
            years_of_experience=candidate.years_of_experience,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{candidate_id}/work_experience", response_model=List[GetCandidateWorkExperience]
)
async def get_candidate_work_experience(
    candidate_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        # 1. Fetch raw work experience data (same as before)
        result = await db.execute(
            select(Candidate.work_experience)
            .filter(Candidate.id == candidate_id)
            .limit(1)
        )
        raw_work_experience_list = result.scalar_one_or_none()

        if raw_work_experience_list is None:
            candidate_exists_result = await db.execute(
                select(Candidate.id).filter(Candidate.id == candidate_id).limit(1)
            )
            if candidate_exists_result.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Candidate not found")
            else:
                return []

        # 2. Validate data structure using Pydantic (WorkExperience model)
        validated_work_experiences: List[WorkExperience] = []
        if isinstance(raw_work_experience_list, list):
            try:
                validated_work_experiences = [
                    WorkExperience.model_validate(json.loads(exp))
                    if isinstance(exp, str)
                    else WorkExperience.model_validate(exp)
                    for exp in raw_work_experience_list
                ]
            except Exception:
                # logger.error(...)
                raise HTTPException(
                    status_code=500,
                    detail="Error validating stored work experience data.",
                )
        else:
            return []

        if not validated_work_experiences:
            return []

        # 3. Collect unique Attachment IDs and Recruiter IDs
        all_attachment_ids = set()
        all_recruiter_ids = set()
        for exp in validated_work_experiences:
            if exp.attachment_ids:
                all_attachment_ids.update(exp.attachment_ids)
            # Collect recruiter IDs from the *stored* VerificationDetail objects
            if exp.verifications:
                for verification in exp.verifications:
                    all_recruiter_ids.add(verification.recruiter_id)  # Add recruiter_id

        # 4. Fetch Attachments (same efficient logic as before)
        attachment_dict = {}
        if all_attachment_ids:
            # ... (attachment fetching logic remains the same) ...
            try:
                typed_attachment_ids = [UUID(str(id_)) for id_ in all_attachment_ids]
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid attachment ID format found."
                )

            attachment_result = await db.execute(
                select(Attachment.id, Attachment.file_path, Attachment.filename).filter(
                    Attachment.id.in_(typed_attachment_ids)
                )
            )
            attachments_data = attachment_result.all()

            for att in attachments_data:
                attachment_dict[str(att.id)] = {
                    "file_path": att.file_path,
                    "filename": att.filename,
                }

        # 5. Fetch Recruiter Names (NEW LOGIC)
        recruiter_name_dict: Dict[int, str] = {}
        if all_recruiter_ids:
            # --- Query to get recruiter names ---
            # Adjust based on your User/Recruiter table structure
            # Example: Assuming Recruiter table has id, first_name, last_name
            recruiter_result = await db.execute(
                select(Recruiter.id, Recruiter.first_name, Recruiter.last_name).filter(
                    Recruiter.id.in_(all_recruiter_ids)
                )
                # Example if names are on User table and Recruiter links via user_id:
                # select(Recruiter.id, User.first_name, User.last_name)
                # .select_from(join(Recruiter, User, Recruiter.user_id == User.id))
                # .filter(Recruiter.id.in_(all_recruiter_ids))
            )
            recruiters_data = recruiter_result.all()

            # Build the lookup dictionary
            for rec in recruiters_data:
                # Handle potential missing names gracefully
                first_name = getattr(rec, "first_name", "") or ""
                last_name = getattr(rec, "last_name", "") or ""
                recruiter_name_dict[rec.id] = f"{first_name} {last_name}".strip()
            # --- End Recruiter Name Fetching ---

        # 6. Process validated experiences and build the final response
        response_work_experiences: List[GetCandidateWorkExperience] = []
        for exp in validated_work_experiences:
            # Build attachments list (same as before)
            exp_attachments = []
            if exp.attachment_ids:
                for attachment_id in exp.attachment_ids:
                    att_id_str = str(attachment_id)
                    if att_id_str in attachment_dict:
                        # ... (append WorkExpAttachment) ...
                        att_data = attachment_dict[att_id_str]
                        exp_attachments.append(
                            WorkExpAttachment(
                                file_path=att_data["file_path"],
                                filename=att_data["filename"],
                            )
                        )

            # Build verifications list including names (NEW)
            exp_verifications_response = []
            if exp.verifications:
                for (
                    verification
                ) in exp.verifications:  # Iterate through stored VerificationDetail
                    recruiter_name = recruiter_name_dict.get(
                        verification.recruiter_id, "Unknown Recruiter"
                    )  # Look up name
                    exp_verifications_response.append(
                        VerificationDetailResponse(
                            recruiter_id=verification.recruiter_id,
                            verified_at=verification.verified_at,
                            recruiter_name=recruiter_name,  # Add the fetched name
                        )
                    )

            # Create the final response object for this work experience
            response_work_experiences.append(
                GetCandidateWorkExperience(
                    id=exp.id,
                    title=exp.title,
                    company=exp.company,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    location=exp.location,
                    attachments=exp_attachments,
                    verifications=exp_verifications_response,  # Use the list with names
                )
            )

        return response_work_experiences

    except HTTPException:
        raise
    except Exception:
        # logger.error(...)
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )


@router.put(
    "/{candidate_id}/work_experience/{work_id}/verify",
    response_model=VerifyWorkExperienceResponse,
)
async def verify_work_experience(
    candidate_id: int,
    work_id: str,
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    user, db = dbps
    recruiter_id = None  # Initialize recruiter_id

    try:
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=403, detail="Unauthorized access: User is not a recruiter."
            )

        # Get the recruiter ID performing the action
        recruiter_id = user.recruiter.id

        # Fetch the candidate
        result = await db.execute(
            select(Candidate).filter(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Ensure work_experience is not None and is a list
        if candidate.work_experience is None:
            candidate.work_experience = []  # Initialize if None

        # Load work_experience entries using Pydantic for validation
        work_experience_data: List[WorkExperience] = []
        try:
            work_experience_data = [
                WorkExperience.model_validate(json.loads(exp))
                if isinstance(exp, str)
                else WorkExperience.model_validate(exp)
                for exp in candidate.work_experience
            ]
        except Exception as validation_error:
            # Handle potential JSON decoding or Pydantic validation errors during loading
            raise HTTPException(
                status_code=400,
                detail=f"Error parsing work experience data: {validation_error}",
            )

        if not work_experience_data:
            # This case might be less likely if initialized above, but good to keep
            raise HTTPException(
                status_code=404,
                detail="Work experience list is empty for this candidate.",
            )

        # Find the target work experience entry and update it
        target_exp: Optional[WorkExperience] = None
        for exp in work_experience_data:
            if str(exp.id) == work_id:
                target_exp = exp
                break

        if target_exp is None:
            raise HTTPException(
                status_code=404,
                detail=f"Work experience with ID {work_id} not found for this candidate.",
            )

        # --- Core Logic Change ---
        # Check if this recruiter has already verified this experience
        already_verified = False
        for verification in target_exp.verifications:
            if verification.recruiter_id == recruiter_id:
                already_verified = True
                break

        if not already_verified:
            # Add new verification detail if not already verified by this recruiter
            new_verification = VerificationDetail(recruiter_id=recruiter_id)
            target_exp.verifications.append(new_verification)

            # Re-encode the updated list for DB storage
            updated_work_experience_json = [
                exp.model_dump_json() for exp in work_experience_data
            ]

            # Save the updated data
            await db.execute(
                update(Candidate)
                .where(Candidate.id == candidate_id)
                .values(
                    work_experience=updated_work_experience_json
                )  # Save the JSON string list
            )
            await db.commit()

            return VerifyWorkExperienceResponse(
                work_experience_id=work_id,
                recruiter_id=recruiter_id,
                message="Work experience verified successfully.",
            )
        else:
            # Optionally, return a specific message or status if already verified by this user
            # For simplicity, we can return the same success response,
            # or change the message. Let's indicate it was already verified.
            return VerifyWorkExperienceResponse(
                work_experience_id=work_id,
                recruiter_id=recruiter_id,
                message="Work experience was already verified by this recruiter.",
            )
    # Alternatively, raise HTTPException(status_code=409, detail="Already verified by this recruiter")

    except HTTPException:
        # Re-raise HTTPExceptions directly to let FastAPI handle them
        raise
    except Exception:
        await db.rollback()
        # Log the full error for debugging
        # logger.error(f"Internal server error during work experience verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )


@router.put(
    "/{candidate_id}/work_experience/{work_id}/unverify",
    response_model=UnverifyWorkExperienceResponse,
)
async def unverify_work_experience(
    candidate_id: int,
    work_id: str,
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    """
    Removes a verification mark placed by the requesting recruiter
    on a specific work experience entry for a candidate.
    """
    user, db = dbps
    recruiter_id = None  # Initialize recruiter_id

    try:
        # 1. Authorization: Ensure user is a recruiter
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=403, detail="Unauthorized access: User is not a recruiter."
            )

        recruiter_id = user.recruiter.id

        # 2. Fetch Candidate
        result = await db.execute(
            select(Candidate).filter(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # 3. Load and Parse Work Experience Data
        if candidate.work_experience is None:
            # If it's None, there's definitely no work experience to unverify
            raise HTTPException(
                status_code=404,
                detail=f"No work experience found for candidate {candidate_id} to unverify.",
            )

        work_experience_data: List[WorkExperience] = []
        try:
            # Handle cases where it might be None or empty before iterating
            raw_exp_list = candidate.work_experience or []
            work_experience_data = [
                WorkExperience.model_validate(json.loads(exp))
                if isinstance(exp, str)
                else WorkExperience.model_validate(exp)
                for exp in raw_exp_list
            ]
        except Exception as validation_error:
            # Handle potential JSON decoding or Pydantic validation errors
            raise HTTPException(
                status_code=400,
                detail=f"Error parsing work experience data: {validation_error}",
            )

        if not work_experience_data:
            raise HTTPException(
                status_code=404,
                detail="Work experience list is empty for this candidate.",
            )

        # 4. Find the Target Work Experience Entry
        target_exp: Optional[WorkExperience] = None
        target_exp_index: Optional[int] = (
            None  # Keep track of index to update the list later
        )
        for index, exp in enumerate(work_experience_data):
            # Ensure comparison is consistent (e.g., both strings)
            if str(exp.id) == str(work_id):
                target_exp = exp
                target_exp_index = index
                break

        if target_exp is None or target_exp_index is None:
            raise HTTPException(
                status_code=404,
                detail=f"Work experience with ID {work_id} not found for this candidate.",
            )

        # 5. --- Core Logic Change: Remove Verification ---
        initial_verifications_count = len(target_exp.verifications)

        # Filter the list, keeping only verifications NOT made by the current recruiter
        original_verifications = target_exp.verifications
        target_exp.verifications = [
            verification
            for verification in original_verifications
            if verification.recruiter_id != recruiter_id
        ]

        verifications_removed = (
            len(target_exp.verifications) < initial_verifications_count
        )

        # 6. Save Changes if Verification was Removed
        if verifications_removed:
            # Update the specific work experience item in the main list
            work_experience_data[target_exp_index] = target_exp

            # Re-encode the *entire updated* list for DB storage
            updated_work_experience_json = [
                exp.model_dump_json() for exp in work_experience_data
            ]

            # Persist changes to the database
            await db.execute(
                update(Candidate)
                .where(Candidate.id == candidate_id)
                .values(
                    work_experience=updated_work_experience_json
                )  # Save the updated JSON list
            )
            await db.commit()

            return UnverifyWorkExperienceResponse(
                work_experience_id=work_id,
                recruiter_id=recruiter_id,
                message="Work experience verification removed successfully.",
            )
        else:
            # If no verification by this recruiter was found, nothing was changed.
            return UnverifyWorkExperienceResponse(
                work_experience_id=work_id,
                recruiter_id=recruiter_id,
                message="Work experience was not previously verified by this recruiter. No changes made.",
            )
            # Alternative: Could raise a 404 or 400 if you prefer an error in this case
            # raise HTTPException(status_code=404, detail="Verification by this recruiter not found for this work experience.")

    except HTTPException:
        # Re-raise HTTPExceptions directly to let FastAPI handle them
        raise
    except Exception:
        # Rollback transaction on any other unexpected error
        await db.rollback()
        # Log the error in a real application: logger.error(f"...", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal server error occurred during unverification.",
        )
