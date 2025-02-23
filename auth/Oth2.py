from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError
from util.app_config import config
from .token import Payload, validate_token
from db.session import get_db
from db.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: Payload = validate_token(
            token, config.ACCESS_TOKEN_SECRET_KEY, config.ALGORITHM
        )
        if payload is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == payload.user_id))
    user: User | None = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user
