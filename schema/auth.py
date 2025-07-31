from pydantic import BaseModel


class GetLoggedUserResponse(BaseModel):
    user_id: int
    recruiter_id: int | None
    candidate_id: int | None
    user_type: str
    first_name: str
    last_name: str
    email: str


class LoginResponseBody(BaseModel):
    account_type: str
    access_token: str
    user: GetLoggedUserResponse



class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshResponseBody(BaseModel):
    access_token: str



