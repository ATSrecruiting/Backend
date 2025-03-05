





import datetime
import uuid
from fastapi import APIRouter, Request, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from auth.token import Payload, create_token
from schema.candidates import RegisterCandidateRequest, RegisterCandidateResponse, CVData, LoginRequest, LoginResponse
from db.models import Candidate, Session, User
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from db.session import get_db
from fastapi import Depends
from auth.password import hash_password, verify_password
from fastapi import Query
from util.app_config import config

router = APIRouter(prefix="/candidates")


@router.post("/register", response_model=RegisterCandidateResponse)
async def create_candidate_account(account_data: RegisterCandidateRequest, db: AsyncSession = Depends(get_db)):
    try:
        password_hash = hash_password(account_data.password)
        user = User(username=account_data.username, email=account_data.email, password=password_hash)
        db.add(user)
        await db.commit()
        return RegisterCandidateResponse(user_id=user.id, username=user.username, email=user.email)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    


@router.post("/personal_info")
async def update_personal_info(
    candidate_data: CVData, 
    user_id: int = Query(..., description="User ID of the candidate"), 
    db: AsyncSession = Depends(get_db)
):
    try:
        candidate = Candidate(
            user_id=user_id,
            first_name=candidate_data.first_name,
            last_name=candidate_data.last_name,
            email=candidate_data.email,
            phone_number=candidate_data.phone_number,
            address=candidate_data.address.model_dump(),
            date_of_birth=candidate_data.date_of_birth,
            years_of_experience=candidate_data.years_of_experience,
            job_title=candidate_data.job_title,
            work_experience=[work.model_dump() for work in candidate_data.work_experience],
            education=[edu.model_dump() for edu in candidate_data.education],
            skills=candidate_data.skills.model_dump(),
            certifications=[cert.model_dump() for cert in candidate_data.certifications]
        )
        db.add(candidate)
        await db.commit()
        return {"message": "Personal info updated successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    


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
    
