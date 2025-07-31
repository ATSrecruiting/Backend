








from pydantic import BaseModel, Field


class ListLLMModelsResponse(BaseModel):
    id :int 
    name: str
    provider: str
    model_name: str
    description: str | None = None



