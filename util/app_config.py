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
    OPEN_ROUTER_KEY: str
    AWS_REGION: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_S3_BUCKET_NAME: str
    API_BASE_URL: str
    GEMINI_API_KEY: str


config = Config(
    ACCESS_TOKEN_SECRET_KEY=os.getenv("ACCESS_TOKEN_SECRET_KEY", ""),
    REFRESH_TOKEN_SECRET_KEY=os.getenv("REFRESH_TOKEN_SECRET_KEY", ""),
    ALGORITHM=os.getenv("ALGORITHM", ""),
    ACCESS_TOKEN_DURATION=int(os.getenv("ACCESS_TOKEN_DURATION", "0")),
    REFRESH_TOKEN_DURATION=int(os.getenv("REFRESH_TOKEN_DURATION", "0")),
    SQLALCHEMY_DATABASE_URI=os.getenv("SQLALCHEMY_DATABASE_URI", ""),
    OPEN_ROUTER_KEY=os.getenv("OPEN_ROUTER_KEY", ""),
    AWS_REGION=os.getenv("AWS_REGION", ""),
    AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID", ""),
    AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
    AWS_S3_BUCKET_NAME=os.getenv("AWS_S3_BUCKET_NAME", ""),
    API_BASE_URL=os.getenv("API_BASE_URL", ""),
    GEMINI_API_KEY=os.getenv("GEMINI_API_KEY", ""),
)
