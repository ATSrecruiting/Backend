from typing import List, Tuple, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query, status
from regex import E
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sympy import use

from auth.Oth2 import get_current_user
from auth.password import hash_password

from schema.attachments import ListAttachments
from schema.candidates import (
    Address,
    Certification,
    GetCandidateCertification,
    GetCandidateEducation,
    GetCandidatePersonalGrowth,
    GetCandidatePersonalInfo,
    GetCandidateSuccessStory,
    GetCandidateWhoAmI,
    ListCandidateWorkExperience,
    ListCandidatesFromSessionIdResponse,
    ListCandidateworkExperienceProjectsResponse,
    PersonalGrowth,
    RegisterCandidateRequest,
    RegisterCandidateResponse,
    CVData,
    ListCandidatesResponse,
    SuccessStory,
    UnVerifyCertificationResponse,
    UnVerifyEducationResponse,
    UnVerifyPersonalGrowthResponse,
    VerifyCertificationResponse,
    VerifyEducationResponse,
    VerifyPersonalGrowthResponse,
    VerifyWorkExperienceResponse,
    WhoAmI,
    VerificationDetail,
    VerificationDetailResponse,
    UnverifyWorkExperienceResponse,
    GetCandidateWorkExperience,
)
from schema.pagination import Pagination

from db.models import Attachment, Candidate, User, TempChatSession, Recruiter, WorkExperience, Education, WorkExperienceProjects, WorkExperienceVerification
from db.session import get_db

from tasks.candidates import embed_candidates_data
import json
from typing import Dict
from uuid import UUID
from sqlalchemy import update
from google import genai
from google.genai import types
from util.app_config import config


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
            user_id = user_id,
            first_name = candidate_data.first_name,
            last_name = candidate_data.last_name,
            email = candidate_data.email,
            phone_number = candidate_data.phone_number,
            address = candidate_data.address.model_dump() if candidate_data.address else None,
            years_of_experience = candidate_data.years_of_experience,
            job_title = candidate_data.job_title,
            skills = candidate_data.skills.model_dump() if candidate_data.skills else None,
        )

        db.add(candidate)
        await db.flush()

        if candidate_data.work_experience:
            work_exp_data = [
                {
                    "candidate_id": candidate.id,
                    "title": exp.title,
                    "company": exp.company,
                    "start_date": exp.start_date,
                    "end_date": exp.end_date,
                    "location": exp.location,
                    "attachment_ids": exp.attachment_ids,
                }
                for exp in candidate_data.work_experience
            ]
            await db.execute(insert(WorkExperience),work_exp_data)
        
        if candidate_data.education:
            education_data = [
                {
                    "candidate_id": candidate.id,
                    "degree": edu.degree,
                    "major": edu.major,
                    "school": edu.school,
                    "graduation_date": edu.graduation_date,
                    "attachment_ids": edu.attachment_ids,
                }
                for edu in candidate_data.education
            ]
            await db.execute(insert(Education),education_data)
        
        await db.commit()
        background_tasks.add_task(embed_candidates_data, candidate.id)
        return {"message": "Candidate personal information updated successfully."}
    except Exception as e:
        await db.rollback()
        print(f"Error updating candidate info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating candidate info: {str(e)}")
    





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
                tags=candidate.skills["technical_skills"][:3] if candidate.skills and "technical_skills" in candidate.skills else [],
                rating=5,
            )
            for candidate in candidates
        ]
    except Exception as e:
        print(f"Error fetching candidates: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching candidates: {str(e)}"
        )
    

@router.get("/{candidate_id}/education", response_model=List[GetCandidateEducation])
async def list_candidate_education(
    candidate_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        # First check if candidate exists
        candidate_exists_result = await db.execute(
            select(Candidate.id).filter(Candidate.id == candidate_id).limit(1)
        )
        if candidate_exists_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Query education records directly from the education table
        education_result = await db.execute(
            select(Education).filter(Education.candidate_id == candidate_id)
        )
        education_records = education_result.scalars().all()

        if not education_records:
            return []

        # Collect all recruiter IDs from verified_by fields
        all_recruiter_ids = set()
        for edu in education_records:
            if edu.verified_by:
                # Now verified_by is a list of dicts with 'id' and 'verified_at'
                for verification in edu.verified_by:
                    if isinstance(verification, dict) and 'id' in verification:
                        all_recruiter_ids.add(verification['id'])

        # Fetch Recruiter Names
        recruiter_name_dict: Dict[int, str] = {}
        if all_recruiter_ids:
            recruiter_result = await db.execute(
                select(Recruiter.id, Recruiter.first_name, Recruiter.last_name).filter(
                    Recruiter.id.in_(all_recruiter_ids)
                )
            )
            recruiters_data = recruiter_result.all()
            for rec in recruiters_data:
                first_name = getattr(rec, "first_name", "") or ""
                last_name = getattr(rec, "last_name", "") or ""
                recruiter_name_dict[rec.id] = f"{first_name} {last_name}".strip()

        # Build the response
        response_education: List[GetCandidateEducation] = []
        for edu in education_records:
            # Build verifications response based on verified_by list of dicts
            verifications_response = []
            if edu.verified_by:
                for verification in edu.verified_by:
                    if isinstance(verification, dict) and 'id' in verification:
                        recruiter_id = verification['id']
                        verified_at = verification.get('verified_at')
                        
                        recruiter_name = recruiter_name_dict.get(
                            recruiter_id, "Unknown Recruiter"
                        )
                        
                        # Convert verified_at to datetime if it's a string
                        verified_at_datetime = None
                        if verified_at:
                            if isinstance(verified_at, str):
                                try:
                                    # Assuming ISO format datetime string
                                    verified_at_datetime = datetime.fromisoformat(verified_at.replace('Z', '+00:00'))
                                except ValueError:
                                    # Handle other datetime formats if needed
                                    verified_at_datetime = None
                            elif isinstance(verified_at, datetime):
                                verified_at_datetime = verified_at

                        verifications_response.append(
                            VerificationDetailResponse(
                                recruiter_id=recruiter_id,
                                verified_at=verified_at_datetime,
                                recruiter_name=recruiter_name,
                            )
                        )

            response_education.append(
                GetCandidateEducation(
                    id=edu.id,
                    degree=edu.degree,
                    major=edu.major,
                    school=edu.school,
                    graduation_date=edu.graduation_date,
                    attachments=edu.attachment_ids,
                    verifications=verifications_response,
                )
            )

        return response_education

    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Error fetching education for candidate {candidate_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
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
        client = genai.Client(api_key= config.GEMINI_API_KEY)
        embedding_vector = client.models.embed_content(
                model="gemini-embedding-exp-03-07",
                contents=[search],
                config= types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY")
            ).embeddings
        query_embedding = embedding_vector[0].values # type: ignore
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
    "/{candidate_id}/work_experience", response_model=List[ListCandidateWorkExperience]
)
async def list_candidate_work_experience(
    candidate_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        candidate_exists_result = await db.execute(
            select(Candidate.id).filter(Candidate.id == candidate_id).limit(1)
        )
        if candidate_exists_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        work_exp_result = await db.execute(
            select(WorkExperience).filter(WorkExperience.candidate_id == candidate_id)
        )
        work_experience_records = work_exp_result.scalars().all()

        if not work_experience_records:
            return []
        
        recruiter_ids_result = await db.execute(
            select(WorkExperienceVerification.verifier_id)
            .filter(WorkExperienceVerification.work_experience_id.in_(
                [we.id for we in work_experience_records]
            ))
        )
        all_recruiter_ids = set(recruiter_ids_result.scalars().all())
        # Fetch Recruiter Names
        recruiter_name_dict: Dict[int, str] = {}
        if all_recruiter_ids:
            recruiter_result = await db.execute(
                select(Recruiter.id, Recruiter.first_name, Recruiter.last_name).filter(
                    Recruiter.id.in_(all_recruiter_ids)
                )
            )
            recruiters_data = recruiter_result.all()

            for rec in recruiters_data:
                first_name = getattr(rec, "first_name", "") or ""
                last_name = getattr(rec, "last_name", "") or ""
                recruiter_name_dict[rec.id] = f"{first_name} {last_name}".strip()
        # Build the response
        response_work_experience: List[ListCandidateWorkExperience] = []
        for we in work_experience_records:
            verifications_response = []
            # Fetch verifications for this work experience
            verifications_result = await db.execute(
                select(WorkExperienceVerification).filter(
                    WorkExperienceVerification.work_experience_id == we.id
                )
            )
            verifications = verifications_result.scalars().all()

            for verification in verifications:
                recruiter_name = recruiter_name_dict.get(
                    verification.verifier_id, "Unknown Recruiter"
                )
                verifications_response.append(
                    VerificationDetailResponse(
                        recruiter_id=verification.verifier_id,
                        verified_at=verification.verification_date,
                        recruiter_name=recruiter_name,
                    )
                )

            response_work_experience.append(
                ListCandidateWorkExperience(
                    id=we.id,
                    title=we.title,
                    company=we.company,
                    start_date=we.start_date if we.start_date else None,
                    end_date=we.end_date if we.end_date else None,
                    location=we.location,
                    attachments=we.attachment_ids,
                    verifications=verifications_response,
                )
            )
        return response_work_experience
    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Error fetching work experience for candidate {candidate_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )

@router.get("/{candidate_id}/work_experience/{work_id}", response_model=GetCandidateWorkExperience)
async def get_work_experience(
    candidate_id: int,
    work_id: UUID,  # Changed to UUID type for proper validation
    db: AsyncSession = Depends(get_db),
):
    try:
        # Verify the work experience exists and belongs to the candidate
        work_experience = await db.get(WorkExperience, work_id)
        if not work_experience:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work experience not found"
            )
            
        if work_experience.candidate_id != candidate_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work experience does not belong to the specified candidate"
            )
        
        return GetCandidateWorkExperience(
            id=work_experience.id,
            title=work_experience.title,
            company=work_experience.company,
            start_date=work_experience.start_date,
            end_date=work_experience.end_date,
            location=work_experience.location,
            skills=work_experience.skills,
            key_achievements=work_experience.key_achievements,
            description=work_experience.description,
        )

    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Error fetching work experience {work_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )

@router.get("/{candidate_id}/work_experience/{work_id}/projects", response_model=List[ListCandidateworkExperienceProjectsResponse])
async def get_work_experience_projects(
    candidate_id: int,
    work_id: UUID,  # Changed to UUID type for proper validation
    db: AsyncSession = Depends(get_db),
):
    try:
        # Verify the work experience exists and belongs to the candidate
        work_experience = await db.get(WorkExperience, work_id)
        if not work_experience:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work experience not found"
            )
            
        if work_experience.candidate_id != candidate_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work experience does not belong to the specified candidate"
            )

        # Fetch projects for this work experience
        projects_result = await db.execute(
            select(WorkExperienceProjects).filter(
                WorkExperienceProjects.work_experience_id == work_id
            )
        )

        projects = projects_result.scalars().all()
        if not projects:
            return []
        
        # Build the response
        response_projects: List[ListCandidateworkExperienceProjectsResponse] = []
        for project in projects:
            response_projects.append(
                ListCandidateworkExperienceProjectsResponse(
                    id=project.id,
                    work_experience_id=project.work_experience_id,
                    project_name=project.project_name,
                    description=project.description,
                    team_size=project.team_size,
                    impact=project.impact,
                )
            )

        return response_projects
    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Error fetching projects for work experience {work_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )


@router.get("/{Candidate_id}/work_experience/{work_id}/attachments", response_model=List[ListAttachments])
async def list_work_experience_attachements(
    Candidate_id: int,
    work_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        # Verify the work experience exists and belongs to the candidate
        work_experience = await db.get(WorkExperience, work_id)
        if not work_experience:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work experience not found"
            )
            
        if work_experience.candidate_id != Candidate_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work experience does not belong to the specified candidate"
            )

        # Fetch attachments for this work experience
        attachments_result = await db.execute(
            select(Attachment).filter(
                Attachment.id.in_(work_experience.attachment_ids)
            )
        )
        attachments = attachments_result.scalars().all()

        if not attachments:
            return []
        
        # Build the response
        response_attachments: List[ListAttachments] = []
        for attachment in attachments:
            # Determine the type based on content_type
            content_type = attachment.content_type.lower()
            if 'pdf' in content_type:
                attachment_type = "pdf"
            elif 'image' in content_type:
                attachment_type = "image"
            else:
                attachment_type = "other"  # or "file" or whatever default you want
            
            response_attachments.append(
                ListAttachments(
                    uuid=attachment.id,
                    name=attachment.filename,
                    type=attachment_type
                )
            )

        return response_attachments

    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Error fetching attachments for work experience {work_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )



@router.get("/{candidate_id}/work_experience/{work_id}/verifiers", response_model=List[VerificationDetailResponse])
async def get_work_experience_verifiers(
    candidate_id: int,
    work_id: UUID,  # Changed to UUID type for proper validation
    db: AsyncSession = Depends(get_db),
):
    try:
        # Verify the work experience exists and belongs to the candidate
        work_experience = await db.get(WorkExperience, work_id)
        if not work_experience:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work experience not found"
            )
            
        if work_experience.candidate_id != candidate_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work experience does not belong to the specified candidate"
            )

        # Fetch verifications for this work experience
        verifications_result = await db.execute(
            select(WorkExperienceVerification).filter(
                WorkExperienceVerification.work_experience_id == work_id
            )
        )
        verifications = verifications_result.scalars().all()

        if not verifications:
            return []

        all_recruiter_ids = set()
        for verification in verifications:
            all_recruiter_ids.add(verification.verifier_id)

        # Fetch Recruiter Names
        recruiter_name_dict: Dict[int, str] = {}
        if all_recruiter_ids:
            recruiter_result = await db.execute(
                select(Recruiter.id, Recruiter.first_name, Recruiter.last_name).filter(
                    Recruiter.id.in_(all_recruiter_ids)
                )
            )
            recruiters_data = recruiter_result.all()

            for rec in recruiters_data:
                first_name = getattr(rec, "first_name", "") or ""
                last_name = getattr(rec, "last_name", "") or ""
                recruiter_name_dict[rec.id] = f"{first_name} {last_name}".strip()

        # Build the response
        response_verifications: List[VerificationDetailResponse] = []
        for verification in verifications:
            recruiter_name = recruiter_name_dict.get(
                verification.verifier_id, "Unknown Recruiter"
            )
            response_verifications.append(
                VerificationDetailResponse(
                    recruiter_id=verification.verifier_id,
                    verified_at=verification.verification_date,
                    recruiter_name=recruiter_name,
                )
            )

        return response_verifications

    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Error fetching verifiers for work experience {work_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )




@router.get("/{candidate_id}/certification", response_model= List[GetCandidateCertification])
async def get_candidate_certifications(
    candidate_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Candidate.certifications)
            .filter(Candidate.id == candidate_id)
            .limit(1)
        )
        raw_certification_list = result.scalar_one_or_none()

        if raw_certification_list is None:
            candidate_exists_result = await db.execute(
                select(Candidate.id).filter(Candidate.id == candidate_id).limit(1)
            )
            if candidate_exists_result.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Candidate not found")
            else:
                return []
        
        # Validate data structure using Pydantic (Certification model)
        validated_certifications: List[Certification] = []
        if isinstance(raw_certification_list, list):
            try:
                validated_certifications = [
                    Certification.model_validate(json.loads(cert))
                    if isinstance(cert, str)
                    else Certification.model_validate(cert)
                    for cert in raw_certification_list
                ]
            except Exception:
                raise HTTPException(
                    status_code=500,
                    detail="Error validating stored certification data.",
                )
        else:
            return []
        
        if not validated_certifications:
            return []
        
        all_recruiter_ids = set()
        for cert in validated_certifications:
            if cert.verifications:
                for verification in cert.verifications:
                    all_recruiter_ids.add(verification.recruiter_id)
        
        # Fetch Recruiter Names
        recruiter_name_dict: Dict[int, str] = {}
        if all_recruiter_ids:
            recruiter_result = await db.execute(
                select(Recruiter.id, Recruiter.first_name, Recruiter.last_name).filter(
                    Recruiter.id.in_(all_recruiter_ids)
                )
            )
            recruiters_data = recruiter_result.all()

            for rec in recruiters_data:
                first_name = getattr(rec, "first_name", "") or ""
                last_name = getattr(rec, "last_name", "") or ""
                recruiter_name_dict[rec.id] = f"{first_name} {last_name}".strip()
        
        # Process validated certifications and build the final response
        response_certifications: List[GetCandidateCertification] = []
        for cert in validated_certifications:
            exp_verifications_response = []
            if cert.verifications:
                for verification in cert.verifications:
                    recruiter_name = recruiter_name_dict.get(
                        verification.recruiter_id, "Unknown Recruiter"
                    )
                    exp_verifications_response.append(
                        VerificationDetailResponse(
                            recruiter_id=verification.recruiter_id,
                            verified_at=verification.verified_at,
                            recruiter_name=recruiter_name,
                        )
                    )
            response_certifications.append(
                GetCandidateCertification(
                    id=cert.id,
                    certifier=cert.certifier,
                    certification_name=cert.certification_name,
                    attachments=cert.attachment_ids,
                    verifications=exp_verifications_response,
                )
            )
        return response_certifications
    except HTTPException:
        raise
    except Exception:
        # logger.error(...)
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )


@router.get(
    "/{candidate_id}/personal_growth", response_model=List[GetCandidatePersonalGrowth] 
)
async def get_candidate_personal_growth(
    candidate_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Candidate.personal_growth)
            .filter(Candidate.id == candidate_id)
            .limit(1)
        )
        raw_personal_growth_list = result.scalar_one_or_none()

        if raw_personal_growth_list is None:
            candidate_exists_result = await db.execute(
                select(Candidate.id).filter(Candidate.id == candidate_id).limit(1)
            )
            if candidate_exists_result.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Candidate not found")
            else:
                return []
        
        # Validate data structure using Pydantic (PersonalGrowth model)
        validated_personal_growth: List[PersonalGrowth] = []
        if isinstance(raw_personal_growth_list, list):
            try:
                validated_personal_growth = [
                    PersonalGrowth.model_validate(json.loads(pg))
                    if isinstance(pg, str)
                    else PersonalGrowth.model_validate(pg)
                    for pg in raw_personal_growth_list
                ]
            except Exception:
                raise HTTPException(
                    status_code=500,
                    detail="Error validating stored personal growth data.",
                )
        else:
            return []
        
        if not validated_personal_growth:
            return []
        
        all_recruiter_ids = set()
        for pg in validated_personal_growth:
            if pg.verifications:
                for verification in pg.verifications:
                    all_recruiter_ids.add(verification.recruiter_id)
        
        # Fetch Recruiter Names
        recruiter_name_dict: Dict[int, str] = {}
        if all_recruiter_ids:
            recruiter_result = await db.execute(
                select(Recruiter.id, Recruiter.first_name, Recruiter.last_name).filter(
                    Recruiter.id.in_(all_recruiter_ids)
                )
            )
            recruiters_data = recruiter_result.all()

            for rec in recruiters_data:
                first_name = getattr(rec, "first_name", "") or ""
                last_name = getattr(rec, "last_name", "") or ""
                recruiter_name_dict[rec.id] = f"{first_name} {last_name}".strip()
        
        # Process validated personal growth and build the final response
        response_personal_growth: List[GetCandidatePersonalGrowth] = []
        for pg in validated_personal_growth:
            exp_verifications_response = []
            if pg.verifications:
                for verification in pg.verifications:
                    recruiter_name = recruiter_name_dict.get(
                        verification.recruiter_id, "Unknown Recruiter"
                    )
                    exp_verifications_response.append(
                        VerificationDetailResponse(
                            recruiter_id=verification.recruiter_id,
                            verified_at=verification.verified_at,
                            recruiter_name=recruiter_name,
                        )
                    )
            response_personal_growth.append(
                GetCandidatePersonalGrowth(
                    id=pg.id,
                    area_of_focus=pg.area_of_focus,
                    activity_method=pg.activity_method,
                    description=pg.description,
                    timeframe=pg.timeframe,
                    skills_gained=pg.skills_gained,
                    attachments=pg.attachment_ids,
                    verifications=exp_verifications_response,
                )
            )
        return response_personal_growth
    except HTTPException:
        raise
    except Exception:
        # logger.error(...)
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )


@router.get(
    "/{candidate_id}/success_stories", response_model=List[GetCandidateSuccessStory]
)
async def get_candidate_success_stories(
    candidate_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Candidate.success_stories)
            .filter(Candidate.id == candidate_id)
            .limit(1)
        )
        raw_success_story_list = result.scalar_one_or_none()

        if raw_success_story_list is None:
            candidate_exists_result = await db.execute(
                select(Candidate.id).filter(Candidate.id == candidate_id).limit(1)
            )
            if candidate_exists_result.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Candidate not found")
            else:
                return []
        
        # Validate data structure using Pydantic (SuccessStory model)
        validated_success_stories: List[SuccessStory] = []
        if isinstance(raw_success_story_list, list):
            try:
                validated_success_stories = [
                    SuccessStory.model_validate(json.loads(ss))
                    if isinstance(ss, str)
                    else SuccessStory.model_validate(ss)
                    for ss in raw_success_story_list
                ]
            except Exception:
                raise HTTPException(
                    status_code=500,
                    detail="Error validating stored success story data.",
                )
        else:
            return []
        
        if not validated_success_stories:
            return []
        
        all_recruiter_ids = set()
        for ss in validated_success_stories:
            if ss.verifications:
                for verification in ss.verifications:
                    all_recruiter_ids.add(verification.recruiter_id)
        
        # Fetch Recruiter Names
        recruiter_name_dict: Dict[int, str] = {}
        if all_recruiter_ids:
            recruiter_result = await db.execute(
                select(Recruiter.id, Recruiter.first_name, Recruiter.last_name).filter(
                    Recruiter.id.in_(all_recruiter_ids)
                )
            )
            recruiters_data = recruiter_result.all()

            for rec in recruiters_data:
                first_name = getattr(rec, "first_name", "") or ""
                last_name = getattr(rec, "last_name", "") or ""
                recruiter_name_dict[rec.id] = f"{first_name} {last_name}".strip()
        
        # Process validated success stories and build the final response
        response_success_stories: List[GetCandidateSuccessStory] = []
        for ss in validated_success_stories:
            exp_verifications_response = []
            if ss.verifications:
                for verification in ss.verifications:
                    recruiter_name = recruiter_name_dict.get(
                        verification.recruiter_id, "Unknown Recruiter"
                    )
                    exp_verifications_response.append(
                        VerificationDetailResponse(
                            recruiter_id=verification.recruiter_id,
                            verified_at=verification.verified_at,
                            recruiter_name=recruiter_name,
                        )
                    )
            response_success_stories.append(
                GetCandidateSuccessStory(
                    id=ss.id,
                    headline=ss.headline,
                    situation=ss.situation,
                    actions=ss.actions,
                    results=ss.results,
                    skills=ss.skills,
                    relevant_experience=ss.relevant_experience,
                    timeframe=ss.timeframe,
                    attachments=ss.attachment_ids,
                    verifications=exp_verifications_response,  # Use the list with names
                )
            )
        return response_success_stories
    except HTTPException:
        raise
    except Exception:
        # logger.error(...)
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )
    
@router.get(
    "/{candidate_id}/who_am_i", response_model=GetCandidateWhoAmI
)
async def get_candidate_who_am_i(
    candidate_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Candidate.who_am_i)
            .filter(Candidate.id == candidate_id)
            .limit(1)
        )
        raw_who_am_i = result.scalar_one_or_none()

        if raw_who_am_i is None:
            candidate_exists_result = await db.execute(
                select(Candidate.id).filter(Candidate.id == candidate_id).limit(1)
            )
            if candidate_exists_result.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Candidate not found")
            else:
                return []
        
        # Validate data structure using Pydantic (WhoAmI model)
        validated_who_am_i: WhoAmI = WhoAmI.model_validate(
            json.loads(raw_who_am_i)
            if isinstance(raw_who_am_i, str)
            else raw_who_am_i
        )
        if not validated_who_am_i:
            return []
        
        response_who_am_i = GetCandidateWhoAmI(
            id=validated_who_am_i.id,
            personal_statement=validated_who_am_i.personal_statement,
            core_values=validated_who_am_i.core_values,
            working_style=validated_who_am_i.working_style,
            motivators=validated_who_am_i.motivators,
            interests_passions=validated_who_am_i.interests_passions,
            attachments=validated_who_am_i.attachment_ids,
        )

        return response_who_am_i
    except HTTPException:
        raise
    except Exception as e:
        # logger.error(...)
        raise HTTPException(
            status_code=500, detail=f"An unexpected internal server error occurred. {str(e)}"
        )


                


@router.put(
    "/{candidate_id}/work_experience/{work_id}/verify",
    response_model=VerifyWorkExperienceResponse,
)
async def verify_work_experience(
    candidate_id: int,
    work_id: UUID,  # Changed to UUID type for proper validation
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    user, db = dbps

    try:
        # Authorization check
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only recruiters can verify work experiences"
            )

        # Verify the work experience exists and belongs to the candidate
        work_experience = await db.get(WorkExperience, work_id)
        if not work_experience:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work experience not found"
            )
            
        if work_experience.candidate_id != candidate_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work experience does not belong to the specified candidate"
            )

        # Check if already verified by this recruiter
        existing_verification = await db.execute(
            select(WorkExperienceVerification).where(
                WorkExperienceVerification.work_experience_id == work_id,
                WorkExperienceVerification.verifier_id == user.recruiter.id
            )
        )
        if existing_verification.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This work experience has already been verified by you"
            )

        # Create new verification
        verification = WorkExperienceVerification(
            work_experience_id=work_id,
            verifier_id=user.recruiter.id,
            verification_date=datetime.now(timezone.utc)
        )

        db.add(verification)
        await db.commit()
        
        return VerifyWorkExperienceResponse(
            work_experience_id=str(work_id),  # Convert UUID to string for response
            recruiter_id=user.recruiter.id,
            message="Work experience verified successfully."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during verification: {str(e)}"
        )



@router.delete(  # Using DELETE method as we're removing a verification
    "/{candidate_id}/work_experience/{work_id}/unverify",
    response_model=UnverifyWorkExperienceResponse,
)
async def unverify_work_experience(
    candidate_id: int,
    work_id: UUID,
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    user, db = dbps

    try:
        # Authorization check
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only recruiters can unverify work experiences"
            )

        # Verify the work experience exists and belongs to the candidate
        work_experience = await db.get(WorkExperience, work_id)
        if not work_experience:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work experience not found"
            )
            
        if work_experience.candidate_id != candidate_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work experience does not belong to the specified candidate"
            )

        # Find the verification record
        verification = await db.execute(
            select(WorkExperienceVerification).where(
                WorkExperienceVerification.work_experience_id == work_id,
                WorkExperienceVerification.verifier_id == user.recruiter.id
            )
        )
        verification = verification.scalar_one_or_none()
        
        if not verification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No verification record found for this work experience and recruiter"
            )

        # Remove the verification
        await db.delete(verification)
        await db.commit()
        
        return UnverifyWorkExperienceResponse(
            work_experience_id=str(work_id),  # Convert UUID to string for response
            recruiter_id=user.recruiter.id,
            message="Work experience unverification successful."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during unverification: {str(e)}"
        )





@router.put(
    "/{candidate_id}/education/{edu_id}/verify",
    response_model=VerifyEducationResponse,
)
async def verify_education(
    candidate_id: int,
    edu_id: str,
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    user, db = dbps
    recruiter_id = None

    try:
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=403, detail="Unauthorized access: User is not a recruiter."
            )
        recruiter_id = user.recruiter.id

        result = await db.execute(
            select(Candidate).filter(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        if candidate.education is None:
            candidate.education = []
        
        education_data: List[Education] = []
        try:
            education_data = [
                Education.model_validate(json.loads(edu))
                if isinstance(edu, str)
                else Education.model_validate(edu)
                for edu in candidate.education
            ]
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Error validating stored education data.",
            )
        if not education_data:
            raise HTTPException(
                status_code=404,
                detail="Education list is empty for this candidate.",
            )
        
        target_edu: Optional[Education] = None
        for edu in education_data:
            if str(edu.id) == edu_id:
                target_edu = edu
                break
        if target_edu is None:
            raise HTTPException(
                status_code=404,
                detail=f"Education with ID {edu_id} not found for this candidate.",
            )
        
        already_verified = False
        for verification in target_edu.verifications:
            if verification.recruiter_id == recruiter_id:
                already_verified = True
                break
        
        if not already_verified:
            new_verification = VerificationDetail(recruiter_id=recruiter_id)
            target_edu.verifications.append(new_verification)

            updated_education_json = [
                edu.model_dump_json() for edu in education_data
            ]

            await db.execute(
                update(Candidate)
                .where(Candidate.id == candidate_id)
                .values(
                    education=updated_education_json
                )
            )
            await db.commit()

            return VerifyEducationResponse(
                education_id=edu_id,
                recruiter_id=recruiter_id,
                message="Education verified successfully.",
            )
        else:
            return VerifyEducationResponse(
                education_id=edu_id,
                recruiter_id=recruiter_id,
                message="Education was already verified by this recruiter.",
            )
        
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )

        
@router.put(
    "/{candidate_id}/education/{edu_id}/unverify",
    response_model=UnVerifyEducationResponse,
)
async def unverify_education(
    candidate_id: int,
    edu_id: str,
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    user, db = dbps
    recruiter_id = None

    try:
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=403, detail="Unauthorized access: User is not a recruiter."
            )
        recruiter_id = user.recruiter.id

        result = await db.execute(
            select(Candidate).filter(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        if candidate.education is None:
            raise HTTPException(
                status_code=404,
                detail="Education list is empty for this candidate.",
            )

        education_data: List[Education] = []
        try:
            education_data = [
                Education.model_validate(json.loads(edu))
                if isinstance(edu, str)
                else Education.model_validate(edu)
                for edu in candidate.education
            ]
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Error validating stored education data.",
            )
        
        target_edu: Optional[Education] = None
        target_edu_index: Optional[int] = None
        for index, edu in enumerate(education_data):
            if str(edu.id) == str(edu_id):
                target_edu = edu
                target_edu_index = index
                break
        
        if target_edu is None or target_edu_index is None:
            raise HTTPException(
                status_code=404,
                detail=f"Education with ID {edu_id} not found for this candidate.",
            )
        
        initial_verifications_count = len(target_edu.verifications)

        original_verifications = target_edu.verifications
        target_edu.verifications = [
            verification
            for verification in original_verifications
            if verification.recruiter_id != recruiter_id
        ]

        verifications_removed = (
            len(target_edu.verifications) < initial_verifications_count
        )

        if verifications_removed:
            education_data[target_edu_index] = target_edu

            updated_education_json = [
                edu.model_dump_json() for edu in education_data
            ]
            await db.execute(
                update(Candidate)
                .where(Candidate.id == candidate_id)
                .values(
                    education=updated_education_json
                )
            )
            await db.commit()
            return UnVerifyEducationResponse(
                education_id=edu_id,
                recruiter_id=recruiter_id,
                message="Education verification removed successfully.",
            )
        else:
            return UnVerifyEducationResponse(
                education_id=edu_id,
                recruiter_id=recruiter_id,
                message="Education was not previously verified by this recruiter. No changes made.",
            )
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal server error occurred during unverification.",
        )


@router.put(
    "/{candidate_id}/certification/{cert_id}/verify",
    response_model=VerifyCertificationResponse,
)
async def verify_certification(
    candidate_id: int,
    cert_id: str,
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    user, db = dbps
    recruiter_id = None

    try:
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=403, detail="Unauthorized access: User is not a recruiter."
            )
        recruiter_id = user.recruiter.id

        result = await db.execute(
            select(Candidate).filter(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        if candidate.certifications is None:
            candidate.certifications = []
        
        certification_data: List[Certification] = []
        try:
            certification_data = [
                Certification.model_validate(json.loads(cert))
                if isinstance(cert, str)
                else Certification.model_validate(cert)
                for cert in candidate.certifications
            ]
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Error validating stored certification data.",
            )
        
        if not certification_data:
            raise HTTPException(
                status_code=404,
                detail="Certification list is empty for this candidate.",
            )
        
        target_cert: Optional[Certification] = None
        for cert in certification_data:
            if str(cert.id) == cert_id:
                target_cert = cert
                break
        
        if target_cert is None:
            raise HTTPException(
                status_code=404,
                detail=f"Certification with ID {cert_id} not found for this candidate.",
            )
        
        already_verified = False
        for verification in target_cert.verifications:
            if verification.recruiter_id == recruiter_id:
                already_verified = True
                break
        
        if not already_verified:
            new_verification = VerificationDetail(recruiter_id=recruiter_id)
            target_cert.verifications.append(new_verification)

            updated_certification_json = [
                cert.model_dump_json() for cert in certification_data
            ]

            await db.execute(
                update(Candidate)
                .where(Candidate.id == candidate_id)
                .values(
                    certifications=updated_certification_json
                )
            )
            await db.commit()

            return VerifyCertificationResponse(
                certification_id=cert_id,
                recruiter_id=recruiter_id,
                message="Certification verified successfully.",
            )
        else:
            return VerifyCertificationResponse(
                certification_id=cert_id,
                recruiter_id=recruiter_id,
                message="Certification was already verified by this recruiter.",
            )
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )


@router.put(
    "/{candidate_id}/certification/{cert_id}/unverify",
    response_model=UnVerifyCertificationResponse,
)
async def unverify_certification(
    candidate_id: int,
    cert_id: str,
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    user, db = dbps
    recruiter_id = None

    try:
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=403, detail="Unauthorized access: User is not a recruiter."
            )
        recruiter_id = user.recruiter.id

        result = await db.execute(
            select(Candidate).filter(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        if candidate.certifications is None:
            raise HTTPException(
                status_code=404,
                detail="Certification list is empty for this candidate.",
            )

        certification_data: List[Certification] = []
        try:
            certification_data = [
                Certification.model_validate(json.loads(cert))
                if isinstance(cert, str)
                else Certification.model_validate(cert)
                for cert in candidate.certifications
            ]
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Error validating stored certification data.",
            )
        
        target_cert: Optional[Certification] = None
        target_cert_index: Optional[int] = None
        for index, cert in enumerate(certification_data):
            if str(cert.id) == str(cert_id):
                target_cert = cert
                target_cert_index = index
                break
        
        if target_cert is None or target_cert_index is None:
            raise HTTPException(
                status_code=404,
                detail=f"Certification with ID {cert_id} not found for this candidate.",
            )
        
        initial_verifications_count = len(target_cert.verifications)

        original_verifications = target_cert.verifications
        target_cert.verifications = [
            verification
            for verification in original_verifications
            if verification.recruiter_id != recruiter_id
        ]

        verifications_removed = (
            len(target_cert.verifications) < initial_verifications_count
        )

        if verifications_removed:
            certification_data[target_cert_index] = target_cert

            updated_certification_json = [
                cert.model_dump_json() for cert in certification_data
            ]
            await db.execute(
                update(Candidate)
                .where(Candidate
                .id == candidate_id)
                .values(
                    certifications=updated_certification_json
                )
            )
            await db.commit()
            return UnVerifyCertificationResponse(
                certification_id=cert_id,
                recruiter_id=recruiter_id,
                message="Certification verification removed successfully.",
            )
        else:
            return UnVerifyCertificationResponse(
                certification_id=cert_id,
                recruiter_id=recruiter_id,
                message="Certification was not previously verified by this recruiter. No changes made.",
            )
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal server error occurred during unverification.",
        )


@router.put(
    "/{candidate_id}/personal_growth/{pg_id}/verify",
    response_model=VerifyPersonalGrowthResponse,
)
async def verify_personal_growth(
    candidate_id: int,
    pg_id: str,
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    user, db = dbps
    recruiter_id = None

    try:
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=403, detail="Unauthorized access: User is not a recruiter."
            )
        recruiter_id = user.recruiter.id

        result = await db.execute(
            select(Candidate).filter(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        if candidate.personal_growth is None:
            candidate.personal_growth = []
        
        personal_growth_data: List[PersonalGrowth] = []
        try:
            personal_growth_data = [
                PersonalGrowth.model_validate(json.loads(pg))
                if isinstance(pg, str)
                else PersonalGrowth.model_validate(pg)
                for pg in candidate.personal_growth
            ]
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Error validating stored personal growth data.",
            )
        
        if not personal_growth_data:
            raise HTTPException(
                status_code=404,
                detail="Personal growth list is empty for this candidate.",
            )
        
        target_pg: Optional[PersonalGrowth] = None
        for pg in personal_growth_data:
            if str(pg.id) == pg_id:
                target_pg = pg
                break
        
        if target_pg is None:
            raise HTTPException(
                status_code=404,
                detail=f"Personal growth with ID {pg_id} not found for this candidate.",
            )
        
        already_verified = False
        for verification in target_pg.verifications:
            if verification.recruiter_id == recruiter_id:
                already_verified = True
                break
        
        if not already_verified:
            new_verification = VerificationDetail(recruiter_id=recruiter_id)
            target_pg.verifications.append(new_verification)

            updated_personal_growth_json = [
                pg.model_dump_json() for pg in personal_growth_data
            ]

            await db.execute(
                update(Candidate)
                .where(Candidate.id == candidate_id)
                .values(
                    personal_growth=updated_personal_growth_json
                )
            )
            await db.commit()
            return VerifyPersonalGrowthResponse(
                personal_growth_id=pg_id,
                recruiter_id=recruiter_id,
                message="Personal growth verified successfully.",
            )
        else:
            return VerifyPersonalGrowthResponse(
                personal_growth_id=pg_id,
                recruiter_id=recruiter_id,
                message="Personal growth was already verified by this recruiter.",
            )
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="An unexpected internal server error occurred."
        )
@router.put(
    "/{candidate_id}/personal_growth/{pg_id}/unverify",
    response_model=UnVerifyPersonalGrowthResponse,
)
async def unverify_personal_growth(
    candidate_id: int,
    pg_id: str,
    dbps: Tuple[User, AsyncSession] = Depends(get_current_user),
):
    user, db = dbps
    recruiter_id = None

    try:
        if user.account_type != "recruiter" or user.recruiter is None:
            raise HTTPException(
                status_code=403, detail="Unauthorized access: User is not a recruiter."
            )
        recruiter_id = user.recruiter.id

        result = await db.execute(
            select(Candidate).filter(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        if candidate.personal_growth is None:
            raise HTTPException(
                status_code=404,
                detail="Personal growth list is empty for this candidate.",
            )

        personal_growth_data: List[PersonalGrowth] = []
        try:
            personal_growth_data = [
                PersonalGrowth.model_validate(json.loads(pg))
                if isinstance(pg, str)
                else PersonalGrowth.model_validate(pg)
                for pg in candidate.personal_growth
            ]
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Error validating stored personal growth data.",
            )
        
        target_pg: Optional[PersonalGrowth] = None
        target_pg_index: Optional[int] = None
        for index, pg in enumerate(personal_growth_data):
            if str(pg.id) == str(pg_id):
                target_pg = pg
                target_pg_index = index
                break
        
        if target_pg is None or target_pg_index is None:
            raise HTTPException(
                status_code=404,
                detail=f"Personal growth with ID {pg_id} not found for this candidate.",
            )
        
        initial_verifications_count = len(target_pg.verifications)

        original_verifications = target_pg.verifications
        target_pg.verifications = [
            verification
            for verification in original_verifications
            if verification.recruiter_id != recruiter_id
        ]

        verifications_removed = (
            len(target_pg.verifications) < initial_verifications_count
        )

        if verifications_removed:
            personal_growth_data[target_pg_index] = target_pg

            updated_personal_growth_json = [
                pg.model_dump_json() for pg in personal_growth_data
            ]
            await db.execute(
                update(Candidate)
                .where(Candidate.id == candidate_id)
                .values(
                    personal_growth=updated_personal_growth_json
                )
            )
            await db.commit()
            return UnVerifyPersonalGrowthResponse(
                personal_growth_id=pg_id,
                recruiter_id=recruiter_id,
                message="Personal growth verification removed successfully.",
            )
        else:
            return UnVerifyPersonalGrowthResponse(
                personal_growth_id=pg_id,
                recruiter_id=recruiter_id,
                message="Personal growth was not previously verified by this recruiter. No changes made.",
            )
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An unexpected internal server error occurred during unverification.",
        )
