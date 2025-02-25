





from fastapi import APIRouter
from schema.candidates import RegisterCandidateRequest, RegisterCandidateResponse
from db.models import Candidate, User
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from db.session import get_db
from fastapi import Depends
from auth.password import hash_password

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
    


