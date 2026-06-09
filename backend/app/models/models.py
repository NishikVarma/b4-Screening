import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ── helpers ───────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── InterviewSession ──────────────────────────────────────────────────────────

class InterviewSession(Base):
    """One screening session per candidate per role."""
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("pending", "active", "completed", "abandoned", name="session_status"),
        default="pending",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    # relationships
    resume: Mapped[Optional["Resume"]] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Question.order",
    )

    def __repr__(self) -> str:
        return f"<InterviewSession id={self.id} role={self.role} status={self.status}>"


# ── Resume ────────────────────────────────────────────────────────────────────

class Resume(Base):
    """Parsed resume attached to a session."""
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # structured data extracted by LLM — stored as JSON string
    skills: Mapped[Optional[str]] = mapped_column(Text)           # JSON list
    experience_summary: Mapped[Optional[str]] = mapped_column(Text)
    domain_exposure: Mapped[Optional[str]] = mapped_column(Text)  # JSON list
    seniority_level: Mapped[Optional[str]] = mapped_column(String(50))  # junior/mid/senior

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    # relationships
    session: Mapped["InterviewSession"] = relationship(back_populates="resume")

    def __repr__(self) -> str:
        return f"<Resume id={self.id} session_id={self.session_id}>"


# ── Question ──────────────────────────────────────────────────────────────────

class Question(Base):
    """A generated interview question within a session."""
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)   # 1-based position
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # traceability — what RAG context produced this question
    context_chunks: Mapped[Optional[str]] = mapped_column(Text)   # JSON list of chunk ids
    source_topics: Mapped[Optional[str]] = mapped_column(Text)    # JSON list of topic strings
    difficulty: Mapped[Optional[str]] = mapped_column(
        Enum("easy", "medium", "hard", name="difficulty_level")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    # relationships
    session: Mapped["InterviewSession"] = relationship(back_populates="questions")
    answer: Mapped[Optional["Answer"]] = relationship(
        back_populates="question", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} order={self.order}>"


# ── Answer ────────────────────────────────────────────────────────────────────

class Answer(Base):
    """Candidate's response to a question."""
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # optional LLM-generated feedback stored after session ends
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    score: Mapped[Optional[int]] = mapped_column(Integer)   # 1-10

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    # relationships
    question: Mapped["Question"] = relationship(back_populates="answer")

    def __repr__(self) -> str:
        return f"<Answer id={self.id} question_id={self.question_id}>"