from sqlalchemy import (
    Enum,
    Integer,
    String,
    ForeignKey,
    Boolean,
    DateTime,
    BigInteger,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import datetime, timezone
import uuid

from .base import Base
from typing import Optional

from pgvector.sqlalchemy import Vector


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    is_used = mapped_column(Boolean, nullable=False, default=False)

    # Relationship
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="resume")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password: Mapped[str] = mapped_column(String)
    account_type: Mapped[str] = mapped_column(
        Enum("candidate", "recruiter", name="account_type_enum"), nullable=False
    )
    profile_picture: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    recruiter: Mapped[Optional["Recruiter"]] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )
    candidate: Mapped[Optional["Candidate"]] = relationship(
        back_populates="user", uselist=False
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    refresh_token: Mapped[str] = mapped_column(String, nullable=False)
    user_agent: Mapped[str] = mapped_column(String, nullable=False)
    client_ip: Mapped[str] = mapped_column(String, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="sessions")


class Recruiter(Base):
    __tablename__ = "recruiters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    first_name: Mapped[str] = mapped_column(String, nullable=True)
    last_name: Mapped[str] = mapped_column(String, nullable=True)
    profile_picture: Mapped[str] = mapped_column(String, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="recruiter")
    vacancies: Mapped[list["Vacancy"]] = relationship(
        "Vacancy", back_populates="recruiter"
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    first_name: Mapped[str] = mapped_column(String, nullable=True)
    last_name: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=True)
    address: Mapped[dict] = mapped_column(JSONB, nullable=True)
    date_of_birth: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    years_of_experience: Mapped[int] = mapped_column(Integer, nullable=True)
    job_title: Mapped[str] = mapped_column(String, nullable=True)
    work_experience: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    education: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    skills: Mapped[dict] = mapped_column(JSONB, nullable=True)
    certifications: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    personal_growth : Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    who_am_i: Mapped[dict] = mapped_column(JSONB, nullable=True)
    success_stories: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=True, default="applied")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, default=datetime.now(timezone.utc)
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(3072), nullable=True)
    is_embedding_ready: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="candidate")
    resume: Mapped["Attachment"] = relationship(
        "Attachment", back_populates="candidate"
    )


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recruiter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recruiters.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationship
    recruiter: Mapped["Recruiter"] = relationship(
        "Recruiter", back_populates="vacancies"
    )
    # applications: Mapped[list["Application"]] = relationship(
    #     "Application", back_populates="vacancy"
    # )


class TempChatSession(Base):
    __tablename__ = "temp_chat_sessions"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    candidates: Mapped[dict] = mapped_column(JSONB, nullable=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    candidates: Mapped[dict] = mapped_column(JSONB, nullable=True)


class ChatMessages(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chat_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    sender: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
