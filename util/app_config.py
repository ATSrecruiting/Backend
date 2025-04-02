from dotenv import load_dotenv
from pydantic import BaseModel
import os


load_dotenv()


class Config(BaseModel):
    ACCESS_TOKEN_SECRET_KEY: str
    REFRESH_TOKEN_SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_DURATION: int
    REFRESH_TOKEN_DURATION: int
    SQLALCHEMY_DATABASE_URI: str
    OPEN_ROUTER_KEY:str



config = Config(
    ACCESS_TOKEN_SECRET_KEY=os.getenv("ACCESS_TOKEN_SECRET_KEY", ""),
    REFRESH_TOKEN_SECRET_KEY=os.getenv("REFRESH_TOKEN_SECRET_KEY", ""),
    ALGORITHM=os.getenv("ALGORITHM", ""),
    ACCESS_TOKEN_DURATION=int(os.getenv("ACCESS_TOKEN_DURATION", "0")),
    REFRESH_TOKEN_DURATION=int(os.getenv("REFRESH_TOKEN_DURATION", "0")),
    SQLALCHEMY_DATABASE_URI=os.getenv("SQLALCHEMY_DATABASE_URI", ""),
    OPEN_ROUTER_KEY=os.getenv("OPEN_ROUTER_KEY", "")
)
