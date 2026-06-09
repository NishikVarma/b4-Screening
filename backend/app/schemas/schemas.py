from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# SESSION
# ═══════════════════════════════════════════════════════════════

class SessionCreate(BaseModel):
    role: str = Field(..., examples=["ai_ml"])

class SessionResponse(BaseModel):
    id: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class SessionSummaryResponse(BaseModel):
    session: SessionResponse
    total_questions: int
    answered: int
    average_score: Optional[float]
    feedback_summary: Optional[str]

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# RESUME
# ═══════════════════════════════════════════════════════════════

class ResumeResponse(BaseModel):
    id: str
    session_id: str
    filename: str
    skills: Optional[list[str]]
    experience_summary: Optional[str]
    domain_exposure: Optional[list[str]]
    seniority_level: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# QUESTION
# ═══════════════════════════════════════════════════════════════

class QuestionResponse(BaseModel):
    id: str
    session_id: str
    order: int
    text: str
    difficulty: Optional[str]
    source_topics: Optional[list[str]]

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# ANSWER
# ═══════════════════════════════════════════════════════════════

class AnswerCreate(BaseModel):
    text: str = Field(..., min_length=1)

class AnswerResponse(BaseModel):
    id: str
    question_id: str
    text: str
    feedback: Optional[str]
    score: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# COMBINED — used in interview flow
# ═══════════════════════════════════════════════════════════════

class QuestionWithAnswer(BaseModel):
    question: QuestionResponse
    answer: Optional[AnswerResponse]

    model_config = {"from_attributes": True}

class NextQuestionResponse(BaseModel):
    """Returned by GET /sessions/{id}/next-question"""
    question: Optional[QuestionResponse]   # None means interview is complete
    question_number: int
    total_questions: int
    is_complete: bool

class SubmitAnswerResponse(BaseModel):
    """Returned by POST /sessions/{id}/answer"""
    answer: AnswerResponse
    next_question: Optional[QuestionResponse]  # None means interview is complete
    is_complete: bool


# ═══════════════════════════════════════════════════════════════
# ERRORS
# ═══════════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    detail: str