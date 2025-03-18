from uuid import UUID
from more_itertools import first, first_true
from pydantic import BaseModel, EmailStr
from typing import Any, List, Optional

from sympy import O


class RegisterCandidateRequest (BaseModel):
    username: str
    email: EmailStr
    password: str

class RegisterCandidateResponse(BaseModel):
    user_id: int
    username: str
    email: str


class Address(BaseModel):
    street: str
    country: str

class WorkExperience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None 
    location: Optional[str] = None
    attachment_ids: Optional[List[UUID]] = None  

class Education(BaseModel):
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
    certifier: Optional[str] = None
    certification_name: Optional[str] = None
    attachment_id: Optional[List[UUID]] = None  # Optional: can be null


class CVData(BaseModel):
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
    username: str
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
    status : str | None
    created_at: str
    tags: List[str]
    rating: Optional[float] = None



class GetCandidatePersonalInfo(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[Address] = None
    years_of_experience: Optional[float] = None


class WorkExpAttachment(BaseModel):
    file_path : str
    filename : str


class GetCandidateWorkExperience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    attachments : Optional[List[WorkExpAttachment]] = None




