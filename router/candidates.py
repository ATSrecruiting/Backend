import datetime
from typing import List
import uuid

from fastapi import APIRouter, Request, status, HTTPException, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.token import Payload, create_token
from auth.password import hash_password, verify_password

from schema.candidates import Address, GetCandidatePersonalInfo, GetCandidateWorkExperience, RegisterCandidateRequest, RegisterCandidateResponse, CVData, LoginRequest, LoginResponse, ListCandidatesResponse, WorkExpAttachment
from schema.pagination import Pagination

from db.models import Attachment, Candidate, Session, User
from db.session import get_db

from util.app_config import config
import json

router = APIRouter(prefix="/candidates")


@router.post("/register", response_model=RegisterCandidateResponse)
async def create_candidate_account(account_data: RegisterCandidateRequest, db: AsyncSession = Depends(get_db)):
    try:
        password_hash = hash_password(account_data.password)
        user = User(username=account_data.username, email=account_data.email, password=password_hash)
        db.add(user)
        await db.commit()
        return RegisterCandidateResponse(user_id=user.id, username=user.username, email=user.email)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    


@router.post("/personal_info")
async def update_personal_info(
    candidate_data: CVData, 
    user_id: int = Query(..., description="User ID of the candidate"), 
    db: AsyncSession = Depends(get_db)
):  
    try:
        candidate = Candidate(
            user_id=user_id,
            first_name=candidate_data.first_name,
            last_name=candidate_data.last_name,
            email=candidate_data.email,
            phone_number=candidate_data.phone_number,
            address=candidate_data.address.model_dump() if candidate_data.address else None,
            date_of_birth=None,
            years_of_experience=candidate_data.years_of_experience,
            job_title=candidate_data.job_title,
            work_experience=[work.model_dump_json() for work in candidate_data.work_experience] if candidate_data.work_experience else [],
            education=[edu.model_dump_json() for edu in candidate_data.education] if candidate_data.education else [],
            skills=candidate_data.skills.model_dump() if candidate_data.skills else None,
            certifications=[cert.model_dump_json() for cert in candidate_data.certifications] if candidate_data.certifications else []
        )
        db.add(candidate)
        await db.commit()
        return {"message": "Personal info updated successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    Login a recruiter
    """
    try:
        result = await db.execute(
            select(User).filter(User.username == login_data.username)
        )
        user = result.scalar_one_or_none()

        if user is None or not verify_password(login_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid username or password",
            )

        access_payload = Payload(
            id=uuid.uuid4(),
            user_id=user.id,
            token_type="access_token",
            is_revoked=False,
            issued_at=datetime.datetime.now(datetime.timezone.utc),
            expires_at=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=config.ACCESS_TOKEN_DURATION),
        )

        access_token = create_token(
            access_payload,
            secretKey=config.ACCESS_TOKEN_SECRET_KEY,
            algorithm=config.ALGORITHM,
        )

        refresh_payload = Payload(
            id=uuid.uuid4(),
            user_id=user.id,
            token_type="refresh_token",
            is_revoked=False,
            issued_at=datetime.datetime.now(datetime.timezone.utc),
            expires_at=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=config.REFRESH_TOKEN_DURATION),
        )

        refresh_token = create_token(
            refresh_payload,
            secretKey=config.REFRESH_TOKEN_SECRET_KEY,
            algorithm=config.ALGORITHM,
        )

        session = Session(
            refresh_token=refresh_token,
            user_agent=request.headers.get("user-agent", ""),
            client_ip=request.client.host if request.client is not None else "",
            expires_at=refresh_payload.expires_at,
            user_id=user.id,
        )
        db.add(session)
        await db.commit()

        return LoginResponse(access_token=access_token, refresh_token=refresh_token)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during login: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during login: {str(e)}",
        )
    


@router.get("", response_model=List[ListCandidatesResponse])
async def list_candidates(
    db: AsyncSession = Depends(get_db), 
    pagination: Pagination = Depends(),
    search: str = Query(None, description="Search by first name or last name")
):
    try:
        query = select(Candidate)
        
        if search:
            query = query.filter(
                (Candidate.first_name.ilike(f"%{search}%")) | 
                (Candidate.last_name.ilike(f"%{search}%"))
            )
        
        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.limit)
        
        # Execute query
        result = await db.execute(query)
        candidates = result.scalars().all()

        # Convert SQLAlchemy models to response models
        return [
            ListCandidatesResponse(
            id=candidate.id,
            first_name=candidate.first_name,
            last_name=candidate.last_name,
            email=candidate.email,
            phone_number=candidate.phone_number,
            date_of_birth=candidate.date_of_birth.isoformat() if candidate.date_of_birth else "2000-01-01",
            years_of_experience=float(candidate.years_of_experience) if candidate.years_of_experience else 0.0,
            job_title=candidate.job_title,
            status=candidate.status if candidate.status else "Applied",
            created_at=candidate.created_at.isoformat() if candidate.created_at else "2000-01-01",
            tags=candidate.skills["technical_skills"][:3],
            rating=5
            )
            for candidate in candidates
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error fetching candidates: {str(e)}"
        )


@router.get("/{candidate_id}/personal_info", response_model=GetCandidatePersonalInfo)
async def get_candidate_personal_info(candidate_id: int, db: AsyncSession = Depends(get_db)):
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
            years_of_experience=candidate.years_of_experience
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/{candidate_id}/work_experience", response_model=List[GetCandidateWorkExperience])
async def get_candidate_work_experience(candidate_id: int, db: AsyncSession = Depends(get_db)):
    try:
        # Fetch only the work_experience column for better performance
        result = await db.execute(
            select(Candidate.work_experience).filter(Candidate.id == candidate_id)
        )
        work_experience_data = result.scalar_one_or_none()
        if work_experience_data:
            # Parse the JSON strings into Python dictionaries
            work_experience_data = [json.loads(exp) if isinstance(exp, str) else exp for exp in work_experience_data]
        
        if work_experience_data is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        work_experiences = []
        
        # Early return if no work experience data
        if not isinstance(work_experience_data, list) or not work_experience_data:
            return work_experiences
        
        # Collect all attachment IDs we need to fetch
        all_attachment_ids = []
        for exp in work_experience_data:
            if exp.get("attachment_ids"):
                all_attachment_ids.extend(exp.get("attachment_ids") or [])
        
        # Create a lookup dictionary of attachments if we have any attachment IDs
        attachment_dict = {}
        if all_attachment_ids:
            # Single query to fetch all attachments at once
            attachment_result = await db.execute(
                select(Attachment.id, Attachment.file_path, Attachment.filename)
                .filter(Attachment.id.in_(all_attachment_ids))
            )
            attachments_data = attachment_result.all()
            
            # Build lookup dictionary for efficient access
            for att in attachments_data:
                attachment_dict[str(att.id)] = {
                    "file_path": att.file_path,
                    "filename": att.filename
                }
        
        # Process work experience entries with the attachment lookup
        for exp in work_experience_data:
            exp_attachments = []
            
            # Use the lookup dictionary instead of individual queries
            if exp.get("attachment_ids"):
                for attachment_id in exp.get("attachment_ids") or []:
                    att_id_str = str(attachment_id)
                    if att_id_str in attachment_dict:
                        exp_attachments.append(
                            WorkExpAttachment(
                                file_path=attachment_dict[att_id_str]["file_path"],
                                filename=attachment_dict[att_id_str]["filename"]
                            )
                        )
            
            work_experiences.append(
                GetCandidateWorkExperience(
                    title=exp.get("title"),
                    company=exp.get("company"),
                    start_date=exp.get("start_date"),
                    end_date=exp.get("end_date"),
                    location=exp.get("location"),
                    attachments=exp_attachments
                )
            )
        
        return work_experiences
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
                

