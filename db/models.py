from sqlalchemy import Column, Integer, String
from .base import Base


class Transcription(Base):
    __tablename__ = "transcription"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, index=True)
