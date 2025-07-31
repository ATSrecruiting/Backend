from typing import Tuple
from fastapi import APIRouter, Depends
from auth.Oth2 import get_current_user
from db.session import get_db
from schema.llm_models import ListLLMModelsResponse
from sqlalchemy import select
from db.models import LLMModel, User
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/llm_models")




@router.get("/", response_model=list[ListLLMModelsResponse])
async def list_llm_models(db = Depends(get_db)):
    """
    List all available LLM models.
    """
    llm_models = await db.execute(
        select(LLMModel)
    )
    result = llm_models.scalars().all()

    return [ListLLMModelsResponse(
        id=model.id,
        name=model.name,
        provider=model.provider,
        model_name=model.model_name,
        description=model.description
    ) for model in result]




    