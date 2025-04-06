from uuid import UUID, uuid4
from more_itertools import first
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime, timezone


class RegisterCandidateRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class RegisterCandidateResponse(BaseModel):
    user_id: int
    username: str
    email: str


class Address(BaseModel):
    street: Optional[str] = None
    country: Optional[str] = None


class VerificationDetail(BaseModel):
    recruiter_id: int  # Assuming recruiter ID is an integer
    verified_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )  # Store UTC timestamp


class WorkExperience(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    attachment_ids: Optional[List[UUID]] = None
    # Remove is_verified and verified_by
    # is_verified: bool = False  # No longer needed
    # verified_by: Optional[str] = None # No longer needed

    # Add a list to store verification details
    verifications: List[VerificationDetail] = Field(default_factory=list)


class Education(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    degree: Optional[str] = None
    major: Optional[str] = None
    school: Optional[str] = None
    graduation_date: Optional[str] = None  # Optional: can be null
    attachment_id: Optional[List[UUID]] = None  # Optional: can be null


class Language(BaseModel):
    language: Optional[str] = None
    level: Optional[str] = None


class SkillSet(BaseModel):
    general_skills: Optional[List[str]] = None
    technical_skills: Optional[List[str]] = None
    languages: Optional[List[Language]] = None


class Certification(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    certifier: Optional[str] = None
    certification_name: Optional[str] = None
    attachment_id: Optional[List[UUID]] = None  # Optional: can be null


class CVData(BaseModel):
    file_id: UUID
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address: Optional[Address] = None
    date_of_birth: Optional[str] = None  # Optional: can be null
    years_of_experience: Optional[float] = None
    job_title: Optional[str] = None
    work_experience: Optional[List[WorkExperience]] = None
    education: Optional[List[Education]] = None
    skills: Optional[SkillSet] = None
    certifications: Optional[List[Certification]] = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ListCandidatesResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone_number: str
    date_of_birth: str
    years_of_experience: float
    job_title: str
    status: str | None
    created_at: str
    tags: List[str]
    rating: Optional[float] = None


class ListCandidatesFromSessionIdResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    years_of_experience: float
    job_title: str


class GetCandidatePersonalInfo(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[Address] = None
    years_of_experience: Optional[float] = None


class WorkExpAttachment(BaseModel):
    file_path: str
    filename: str


class VerificationDetailResponse(BaseModel):
    recruiter_id: int
    verified_at: datetime
    recruiter_name: Optional[str] = None  # Add the name field


class GetCandidateWorkExperience(BaseModel):
    id: Optional[UUID] = None
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    attachments: List[WorkExpAttachment] = Field(default_factory=list)

    # Use the response model that includes the name
    verifications: List[VerificationDetailResponse] = Field(default_factory=list)


# Update the response model
class VerifyWorkExperienceResponse(BaseModel):
    work_experience_id: str
    recruiter_id: int
    message: str = "Work experience verified successfully."


class UnverifyWorkExperienceResponse(BaseModel):
    work_experience_id: str
    recruiter_id: int
    message: str
