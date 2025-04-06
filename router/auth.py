import datetime
from typing import Tuple
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from db.models import User, Session
from db.session import get_db
from schema.auth import LoginRequest, LoginResponse, GetLoggedUserResponse
from util.app_config import config
from auth.token import Payload, create_token
from auth.password import verify_password
from auth.Oth2 import get_current_user


from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/auth")


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    Login a recruiter
    """
    try:
        result = await db.execute(select(User).filter(User.email == login_data.email))
        user = result.scalar_one_or_none()

        if user is None or not verify_password(login_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid username or password",
            )

        access_payload = Payload(
            id=uuid.uuid4(),
            user_id=user.id,
            token_type="access_token",
            account_type=user.account_type,
            is_revoked=False,
            issued_at=datetime.datetime.now(datetime.timezone.utc),
            expires_at=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=config.ACCESS_TOKEN_DURATION),
        )

        access_token = create_token(
            access_payload,
            secretKey=config.ACCESS_TOKEN_SECRET_KEY,
            algorithm=config.ALGORITHM,
        )

        refresh_payload = Payload(
            id=uuid.uuid4(),
            user_id=user.id,
            token_type="refresh_token",
            account_type=user.account_type,
            is_revoked=False,
            issued_at=datetime.datetime.now(datetime.timezone.utc),
            expires_at=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=config.REFRESH_TOKEN_DURATION),
        )

        refresh_token = create_token(
            refresh_payload,
            secretKey=config.REFRESH_TOKEN_SECRET_KEY,
            algorithm=config.ALGORITHM,
        )

        session = Session(
            refresh_token=refresh_token,
            user_agent=request.headers.get("user-agent", ""),
            client_ip=request.client.host if request.client is not None else "",
            expires_at=refresh_payload.expires_at,
            user_id=user.id,
        )
        db.add(session)
        await db.commit()

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            account_type=user.account_type,
        )
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during login: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during login: {str(e)}",
        )


@router.get("/user", response_model=GetLoggedUserResponse)
async def get_logged_user(dbps: Tuple[User, AsyncSession] = Depends(get_current_user)):
    """
    Get the current user
    """
    try:
        user, db = dbps
        if user.account_type == "recruiter" and user.recruiter is not None:
            return GetLoggedUserResponse(
                user_id=user.id,
                recruiter_id=user.recruiter.id,
                candidate_id=None,
                user_type=user.account_type,
                first_name=user.recruiter.first_name,
                last_name=user.recruiter.last_name,
                email=user.email,
            )
        elif user.account_type == "candidate" and user.candidate is not None:
            return GetLoggedUserResponse(
                user_id=user.id,
                recruiter_id=None,
                candidate_id=user.candidate.id,
                user_type=user.account_type,
                first_name=user.candidate.first_name,
                last_name=user.candidate.last_name,
                email=user.email,
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during getting user: {str(e)}",
        )
