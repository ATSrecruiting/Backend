from email import message
from uuid import UUID, uuid4
from pydantic import BaseModel, EmailStr, Field
from typing import Any, List, Optional
from datetime import datetime, timezone

from sympy import N


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
    attachment_ids: Optional[List[UUID]] = None  # Optional: can be null
    verifications: List[VerificationDetail] = Field(default_factory=list)


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
    attachment_ids: Optional[List[UUID]] = None  # Optional: can be null

    verifications: List[VerificationDetail] = Field(default_factory=list)


class WhoAmI(BaseModel):
    id : UUID = Field(default_factory=uuid4)
    personal_statement: Optional[str] = None
    core_values : Optional[List[str]] = None
    working_style : Optional[List[str]] = None
    motivators : Optional[List[str]] = None
    interests_passions : Optional[List[str]] = None
    attachment_ids: Optional[List[UUID]] = None  # Optional: can be null


class PersonalGrowth(BaseModel):
    id : UUID = Field(default_factory=uuid4)
    area_of_focus: Optional[str] = None
    activity_method: Optional[str] = None
    description: Optional[str] = None
    timeframe: Optional[str] = None
    skills_gained : Optional[List[str]] = None
    attachment_ids: Optional[List[UUID]] = None  # Optional: can be null

    verifications: List[VerificationDetail] = Field(default_factory=list)


class SuccessStory(BaseModel):
    id : UUID = Field(default_factory=uuid4)
    headline: Optional[str] = None
    situation: Optional[str] = None
    actions: Optional[str] = None
    results: Optional[str] = None
    skills : Optional[List[str]] = None
    relevant_experience: Optional[str] = None
    timeframe: Optional[str] = None
    attachment_ids: Optional[List[UUID]] = None  # Optional: can be null

    verifications: List[VerificationDetail] = Field(default_factory=list)

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
    personal_growth: Optional[List[PersonalGrowth]] = None
    who_am_i: Optional[WhoAmI] = None
    success_stories: Optional[List[SuccessStory]] = None

    


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



class VerificationDetailResponse(BaseModel):
    recruiter_id: int
    verified_at: Optional[datetime]
    recruiter_name: Optional[str] = None  # Add the name field


class ListCandidateWorkExperience(BaseModel):
    id: Optional[UUID] = None
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[List[str]] = None
    attachments: List[UUID] | None


    # Use the response model that includes the name
    verifications: List[VerificationDetailResponse] = Field(default_factory=list)


class GetCandidateWorkExperience(BaseModel):
    id: Optional[UUID] = None
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[List[str]] = None
    key_achievements: Optional[List[str]] = None
    description : Optional[str] = None


class ListCandidateworkExperienceProjectsResponse(BaseModel):
    id : Optional[UUID] = None
    work_experience_id: Optional[UUID] = None
    project_name: Optional[str] = None
    description: Optional[str] = None
    duration : Optional[str] = None
    team_size: Optional[int] = None
    impact : Optional[str] = None



class GetCandidateEducation(BaseModel):
    id: Optional[UUID] = None
    degree: Optional[str] = None
    major: Optional[str] = None
    school: Optional[str] = None
    graduation_date: Optional[str] = None  # Optional: can be null
    attachments: List[UUID] | None 

    # Use the response model that includes the name
    verifications: List[VerificationDetailResponse] = Field(default_factory=list)


class GetCandidateCertification(BaseModel):
    id: Optional[UUID] = None
    certifier: Optional[str] = None
    certification_name: Optional[str] = None
    attachments: List[UUID] | None 

    # Use the response model that includes the name
    verifications: List[VerificationDetailResponse] = Field(default_factory=list)


class GetCandidatePersonalGrowth(BaseModel):
    id: Optional[UUID] = None
    area_of_focus: Optional[str] = None
    activity_method: Optional[str] = None
    description: Optional[str] = None
    timeframe: Optional[str] = None
    skills_gained : Optional[List[str]] = None
    attachments: List[UUID] | None 

    # Use the response model that includes the name
    verifications: List[VerificationDetailResponse] = Field(default_factory=list)

class GetCandidateWhoAmI(BaseModel):
    id: Optional[UUID] = None
    personal_statement: Optional[str] = None
    core_values : Optional[List[str]] = None
    working_style : Optional[List[str]] = None
    motivators : Optional[List[str]] = None
    interests_passions : Optional[List[str]] = None
    attachments: List[UUID] | None 

class GetCandidateSuccessStory(BaseModel):
    id: Optional[UUID] = None
    headline: Optional[str] = None
    situation: Optional[str] = None
    actions: Optional[str] = None
    results: Optional[str] = None
    skills : Optional[List[str]] = None
    relevant_experience: Optional[str] = None
    timeframe: Optional[str] = None
    attachments: List[UUID] | None 

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


class VerifyEducationResponse(BaseModel):
    education_id: str
    recruiter_id: int
    message: str = "Education verified successfully."


class UnVerifyEducationResponse(BaseModel):
    education_id: str
    recruiter_id: int
    message: str = "Education verified successfully."


class VerifyCertificationResponse(BaseModel):
    certification_id: str
    recruiter_id: int
    message: str = "Certification verified successfully."

class UnVerifyCertificationResponse(BaseModel):
    certification_id: str
    recruiter_id: int
    message: str = "Certification unverified successfully."

class VerifyPersonalGrowthResponse(BaseModel):
    personal_growth_id: str
    recruiter_id: int
    message: str = "Personal growth verified successfully."

class UnVerifyPersonalGrowthResponse(BaseModel):
    personal_growth_id: str
    recruiter_id: int
    message: str = "Personal growth unverified successfully."



class UpdateWorkExperienceDescriptionRequest(BaseModel):
    description: str


class UpdateWorkExperienceDescriptionResponse(BaseModel):
    work_experience_id: UUID
    description: str
    message: str = "Work experience description updated successfully."



class UpdateWorkExperienceKeyAchievementsRequest(BaseModel):
    key_achievements: List[str]

class UpdateWorkExperienceKeyAchievementsResponse(BaseModel):
    work_experience_id: UUID
    key_achievements: List[str]
    message: str = "Work experience key achievements updated successfully."



class UpdateWorkExperienceProjectsRequest(BaseModel):
    project_name: Optional[str] = None
    description: Optional[str] = None
    duration : Optional[str] = None
    team_size: Optional[int] = None
    impact : Optional[str] = None




class WorkExperienceProjectSchema(BaseModel):
    id: UUID
    project_name: str
    description: str
    duration: str
    team_size: int
    impact: str

    model_config = {
        "from_attributes": True
    }

class UpdateWorkExperienceProjectsResponse(BaseModel):
    work_experience_id : UUID
    projects : List[WorkExperienceProjectSchema]
    message: str = "Work experience projects updated successfully."