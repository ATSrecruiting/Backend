from pydantic import BaseModel, EmailStr
from typing import List, Optional


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
    title: str
    company: str
    start_date: str
    end_date: Optional[str] = None  # Optional: can be null
    location: str

class Education(BaseModel):
    degree: str
    major: str
    school: str
    graduation_date: Optional[str] = None  # Optional: can be null

class Language(BaseModel):
    language: str
    level: str

class SkillSet(BaseModel):
    general_skills: List[str]
    technical_skills: List[str]
    languages: List[Language]

class Certification(BaseModel):
    certifier: str
    certification_name: str

class CVData(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone_number: str
    address: Address
    date_of_birth: Optional[str] = None  # Optional: can be null
    years_of_experience: float
    job_title: str
    work_experience: List[WorkExperience]
    education: List[Education]
    skills: SkillSet
    certifications: List[Certification]



class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str


class LoginRequest(BaseModel):
    username: str
    password: str