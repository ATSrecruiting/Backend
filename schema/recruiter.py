from pydantic import BaseModel, EmailStr


# /recruiter post
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


# recruiter/login
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# /recruiter profile


class ProfileResponse(BaseModel):
    recruiter_id: int
    user_id: int
    email: str
    first_name: str
    last_name: str
