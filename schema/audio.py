from pydantic import BaseModel


class TranscribeAudioResponse(BaseModel):
    text: str
    segments: list[dict[str, str]]
