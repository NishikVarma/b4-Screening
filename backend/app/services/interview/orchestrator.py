import json
from sqlalchemy.orm import Session

from app.models.models import (
    InterviewSession,
    Resume,
    Question,
    Answer,
)
from app.services.resume.parser import process_resume
from app.services.rag.question_generator import generate_questions

def create_session(
        db: Session,
        role: str,
) -> InterviewSession:
    session = InterviewSession(
        role=role,
        status="pending",
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def upload_resume(
        db: Session,
        session_id: str,
        file_bytes: bytes,
        filename: str,
) -> Resume:
    session = db.get(InterviewSession, session_id)

    if not session:
        raise ValueError("Session not found")

    parsed = process_resume(
        file_bytes=file_bytes,
        filename=filename,
    )

    resume = Resume(
        session_id=session.id,
        filename=filename,
        raw_text=parsed["raw_text"],
        skills=json.dumps(parsed["skills"]),
        experience_summary=parsed["experience_summary"],
        domain_exposure=json.dumps(parsed["domain_exposure"]),
        seniority_level=parsed["seniority_level"],
    )

    db.add(resume)

    session.resume = resume
    session.status = "active"

    db.commit()
    db.refresh(resume)

    return resume


def generate_questions_for_session(
        db: Session,
        session_id: str,
) -> list[Question]:
    session = db.get(InterviewSession, session_id)

    if not session:
        raise ValueError("Session not found")

    if not session.resume:
        raise ValueError("Resume not uploaded")

    if session.questions:
        return session.questions

    resume = session.resume

    generated_questions = generate_questions(
        role=session.role,
        skills=json.loads(resume.skills or "[]"),
        domain_exposure=json.loads(resume.domain_exposure or "[]"),
        seniority_level=resume.seniority_level or "mid",
        experience_summary=resume.experience_summary or "",
    )

    created_questions = []

    for q in generated_questions:
        question = Question(
            session_id=session.id,
            order=q.order,
            text=q.text,
            difficulty=q.difficulty,
            source_topics=json.dumps(q.source_topics),
            context_chunks=json.dumps(q.context_chunk_ids),
        )

        db.add(question)
        created_questions.append(question)

    db.commit()

    for question in created_questions:
        db.refresh(question)

    return created_questions


def get_next_question(
        db: Session,
        session_id: str,
) -> Question | None:
    session = db.get(InterviewSession, session_id)

    if not session:
        raise ValueError("Session not found")

    questions = (
        db.query(Question)
        .filter(Question.session_id == session_id)
        .order_by(Question.order)
        .all()
    )

    for question in questions:
        if question.answer is None:
            return question

    return None


def submit_answer(
        db: Session,
        session_id: str,
        question_id: str,
        answer_text: str,
) -> Answer:
    session = db.get(InterviewSession, session_id)

    if not session:
        raise ValueError("Session not found")

    question = (
        db.query(Question)
        .filter(
            Question.id == question_id,
            Question.session_id == session_id,
            )
        .first()
    )

    if not question:
        raise ValueError("Question not found")

    if question.answer:
        raise ValueError("Question already answered")

    answer = Answer(
        question_id=question.id,
        text=answer_text,
    )

    db.add(answer)
    db.commit()
    db.refresh(answer)

    remaining = get_next_question(db, session_id)

    if remaining is None:
        session.status = "completed"
        db.commit()

    return answer


def get_session_summary(
        db: Session,
        session_id: str,
) -> dict:
    session = db.get(InterviewSession, session_id)

    if not session:
        raise ValueError("Session not found")

    total_questions = len(session.questions)

    answered = sum(
        1
        for q in session.questions
        if q.answer is not None
    )

    scores = [
        q.answer.score
        for q in session.questions
        if q.answer and q.answer.score is not None
    ]

    average_score = (
        round(sum(scores) / len(scores), 2)
        if scores
        else None
    )

    return {
        "session": session,
        "total_questions": total_questions,
        "answered": answered,
        "average_score": average_score,
        "feedback_summary": None,
    }