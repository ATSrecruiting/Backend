from pydantic import BaseModel, EmailStr


class CreateRecruiterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class CreateRecruiterResponse(BaseModel):
    recruiter_id: int
    user_id: int
    username: str
    email: str
    first_name: str
    last_name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    AccessToken: str
    RefreshToken: str
