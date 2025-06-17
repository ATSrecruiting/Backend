from fastapi import APIRouter, Depends, HTTPException, status, Request
from schema.recruiter import (
    CreateRecruiterRequest,
    CreateRecruiterResponse,
    LoginRequest,
    LoginResponse,
    ProfileResponse,
    RefreshTokenRequest,
)
from db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from db.models import User, Recruiter, Session
from auth.password import hash_password, verify_password
from auth.token import Payload, create_token
from util.app_config import config
from auth.Oth2 import get_current_user
import uuid
import datetime

router = APIRouter(prefix="/recruiters")


@router.post("", response_model=CreateRecruiterResponse)
async def create_recruiter_profile(
    request: CreateRecruiterRequest, db: AsyncSession = Depends(get_db)
):
    """
    Create a new recruiter profile, both User and Recruiter will be created in a transaction.
    """
    try:
        async with db.begin():
            password_hash = hash_password(request.password)
            user = User(
                username=request.username,
                email=request.email,
                password=password_hash,
                account_type="recruiter",
            )
            db.add(user)
            await db.flush()  # ensures user.id is populated
            recruiter = Recruiter(
                user_id=user.id,
                first_name=request.first_name,
                last_name=request.last_name,
            )
            db.add(recruiter)

        return CreateRecruiterResponse(
            recruiter_id=recruiter.id,
            user_id=user.id,
            username=user.username,
            email=user.email,
            first_name=recruiter.first_name,
            last_name=recruiter.last_name,
        )

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating recruiter profile: {str(e)}",
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    Login a recruiter
    """
    try:
        result = await db.execute(
            select(User).filter(User.username == login_data.username)
        )
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
            is_revoked=False,
            account_type=user.account_type,
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

        return LoginResponse(access_token=access_token, refresh_token=refresh_token)
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


@router.post("/refresh", response_model=LoginResponse)
async def refresh(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh the access token using the refresh token
    """
    try:
        result = await db.execute(
            select(Session).filter(Session.refresh_token == data.refresh_token)
        )
        session = result.scalar_one_or_none()

        if (
            session is None
            or session.is_blocked
            or session.expires_at < datetime.datetime.now(datetime.timezone.utc)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid refresh token",
            )

        access_payload = Payload(
            id=uuid.uuid4(),
            user_id=session.user_id,
            token_type="access_token",
            account_type="recruiter",
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

        return LoginResponse(
            access_token=access_token, refresh_token=data.refresh_token
        )
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during refresh: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during refresh: {str(e)}",
        )


@router.get("/profile", response_model=ProfileResponse)
async def get_recruiter_profile(user: User = Depends(get_current_user)):
    """
    Get the recruiter profile
    """
    if not user.recruiter:
        raise HTTPException(status_code=404, detail="Recruiter profile not found")

    return ProfileResponse(
        user_id=user.id,
        email=user.email,
        recruiter_id=user.recruiter.id,
        first_name=user.recruiter.first_name,
        last_name=user.recruiter.last_name,
    )
