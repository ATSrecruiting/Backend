









import email
import profile
from pydantic import BaseModel


class LoginResponse(BaseModel):
    account_type: str
    access_token: str
    refresh_token: str


class LoginRequest(BaseModel):
    email: str
    password: str



class GetLoggedUserResponse(BaseModel):
    user_id : int
    user_type : str
    first_name: str
    last_name: str
    email: str
    

