from datetime import datetime
import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import (
    AnswerCreate,
    NextQuestionResponse,
    QuestionResponse,
    ResumeResponse,
    SessionCreate,
    SessionResponse,
    SessionSummaryResponse,
    SubmitAnswerResponse,
)
from app.services.interview.orchestrator import (
    create_session,
    generate_questions_for_session,
    get_next_question,
    get_session_summary,
    submit_answer,
    skip_question,
    upload_resume,
)

router = APIRouter(prefix="/sessions", tags=["Interview"])


def _question_to_response(question):
    return QuestionResponse(
        id=question.id,
        session_id=question.session_id,
        order=question.order,
        text=question.text,
        difficulty=question.difficulty,
        source_topics=json.loads(question.source_topics or "[]"),
    )


@router.post("", response_model=SessionResponse)
def create_session_route(
        payload: SessionCreate,
        db: Session = Depends(get_db),
):
    session = create_session(db, payload.role)
    return session


@router.post("/{session_id}/resume", response_model=ResumeResponse)
async def upload_resume_route(
        session_id: str,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
):
    try:
        file_bytes = await file.read()

        resume = upload_resume(
            db=db,
            session_id=session_id,
            file_bytes=file_bytes,
            filename=file.filename,
        )

        generate_questions_for_session(
            db=db,
            session_id=session_id,
        )

        return ResumeResponse(
            id=resume.id,
            session_id=resume.session_id,
            filename=resume.filename,
            skills=json.loads(resume.skills or "[]"),
            experience_summary=resume.experience_summary,
            domain_exposure=json.loads(resume.domain_exposure or "[]"),
            seniority_level=resume.seniority_level,
            created_at=resume.created_at,
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{session_id}/next-question", response_model=NextQuestionResponse)
def get_next_question_route(
        session_id: str,
        db: Session = Depends(get_db),
):
    try:
        question = get_next_question(
            db=db,
            session_id=session_id,
        )

        session_summary = get_session_summary(
            db=db,
            session_id=session_id,
        )

        total_questions = session_summary["total_questions"]

        if question is None:
            return NextQuestionResponse(
                question=None,
                question_number=total_questions,
                total_questions=total_questions,
                is_complete=True,
            )

        return NextQuestionResponse(
            question=_question_to_response(question),
            question_number=question.order,
            total_questions=total_questions,
            is_complete=False,
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/{session_id}/questions/{question_id}/answer",
    response_model=SubmitAnswerResponse,
)
def submit_answer_route(
        session_id: str,
        question_id: str,
        payload: AnswerCreate,
        db: Session = Depends(get_db),
):
    try:
        answer = submit_answer(
            db=db,
            session_id=session_id,
            question_id=question_id,
            answer_text=payload.text,
        )

        next_question = get_next_question(
            db=db,
            session_id=session_id,
        )

        return SubmitAnswerResponse(
            answer=answer,
            next_question=(
                _question_to_response(next_question)
                if next_question
                else None
            ),
            is_complete=(next_question is None),
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post(
    "/{session_id}/questions/{question_id}/skip",
    response_model=SubmitAnswerResponse,
)
def skip_question_route(
        session_id: str,
        question_id: str,
        db: Session = Depends(get_db),
):
    try:
        answer = skip_question(
            db=db,
            session_id=session_id,
            question_id=question_id,
        )

        next_question = get_next_question(
            db=db,
            session_id=session_id,
        )

        return SubmitAnswerResponse(
            answer=answer,
            next_question=(
                _question_to_response(next_question)
                if next_question
                else None
            ),
            is_complete=(next_question is None),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

@router.get("/{session_id}/summary", response_model=SessionSummaryResponse)
def get_summary_route(
        session_id: str,
        db: Session = Depends(get_db),
):
    try:
        summary = get_session_summary(
            db=db,
            session_id=session_id,
        )

        return SessionSummaryResponse(
            session=summary["session"],
            total_questions=summary["total_questions"],
            answered=summary["answered"],
            average_score=summary["average_score"],
            feedback_summary=summary["feedback_summary"],
            question_details=summary["question_details"],
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))