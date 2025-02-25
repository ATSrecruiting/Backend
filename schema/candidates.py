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
    country: str
    street: str

class WorkExperience(BaseModel):
    title: str
    company: str
    start_date: str  # YYYY-MM format
    end_date: str
    location: str

class CreateCandidateRequest(BaseModel):
    first_name: str
    last_name: str
    job_title: str
    years_of_experience: float 
    phone_number: str  
    address: Address
    email: EmailStr
    work_experience: List[WorkExperience]




