import datetime
import re
from typing import Tuple
import uuid
from wsgiref import validate
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import JSON
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from db.models import User, Session
from db.session import get_db
from schema.auth import LoginRequest, GetLoggedUserResponse, LoginResponseBody, RefreshResponseBody
from util.app_config import config
from auth.token import Payload, create_token, validate_refresh_token
from auth.password import verify_password
from auth.Oth2 import get_current_user


from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/auth")


@router.post("/login", response_model=LoginResponseBody)
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

        response_content = LoginResponseBody(
            access_token=access_token,
            account_type=user.account_type,
        )
        response = JSONResponse(
            content=response_content.model_dump(),
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            path="/",
            max_age=config.REFRESH_TOKEN_DURATION,
            expires=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=config.REFRESH_TOKEN_DURATION),
        )
        return response
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



@router.post("/refresh", response_model= RefreshResponseBody)
async def refresh_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    refresh_token_cookie: str | None = Cookie(None, alias="refresh_token"),
)-> JSONResponse:
    """
    Refresh the access token using the refresh token
    """
    try:
        if refresh_token_cookie is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found",
            )

        query = await db.execute(
            select(Session)
            .options(selectinload(Session.user))
            .filter(Session.refresh_token == refresh_token_cookie)
        )
        session = query.scalar_one_or_none()

        if (
            session is None or
            session.user is None or
            validate_refresh_token(refresh_token_cookie, config.REFRESH_TOKEN_SECRET_KEY, config.ALGORITHM) or
            session.expires_at <= datetime.datetime.now(datetime.timezone.utc) or
            session.is_blocked
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user = session.user
        new_access_payload = Payload(
            id=uuid.uuid4(),
            user_id=user.id,
            token_type="access_token",
            account_type=user.account_type,
            is_revoked=False,
            issued_at=datetime.datetime.now(datetime.timezone.utc),
            expires_at=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=config.ACCESS_TOKEN_DURATION),
        )
        new_access_token = create_token(
            new_access_payload,
            secretKey=config.ACCESS_TOKEN_SECRET_KEY,
            algorithm=config.ALGORITHM,
        )


        response_content = RefreshResponseBody(
            access_token=new_access_token,
        )
        response = JSONResponse(
            content=response_content.model_dump(),
        )
        return response
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during refreshing access token: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during refreshing access token: {str(e)}",
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
