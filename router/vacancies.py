





from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.Oth2 import get_current_user
from db.models import User, Vacancy
from db.session import get_db
from schema.vacancies import CreateVacancyRequest, CreateVacancyResponse


router = APIRouter( prefix="/vacancies")




@router.post("", response_model=CreateVacancyResponse)
async def create_vacancy(request: CreateVacancyRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Create a new vacancy.
    """
    if user.recruiter is None:
        raise HTTPException(status_code=403, detail="Only recruiters can create vacancies")
    vacancy = Vacancy(
        recruiter_id=user.recruiter.id,
        title=request.title,
        description=request.description,
        location=request.location,
        end_date=request.end_date,
        is_active=True,

    )
    db.add(vacancy)
    await db.commit()
    return CreateVacancyResponse(
        id=vacancy.id,
        recruiter_id=vacancy.recruiter_id,
        title=vacancy.title,
        description=vacancy.description,
        location=vacancy.location,
        is_active=vacancy.is_active,
        created_at=vacancy.created_at,
        end_date=vacancy.end_date,
    )

    