import json
import logging
from dataclasses import dataclass

import google.generativeai as genai

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

genai.configure(api_key=settings.google_api_key)
_model = genai.GenerativeModel(settings.google_model)


@dataclass
class EvaluationResult:
    score: int
    feedback: str


_EVALUATION_PROMPT = """
You are a senior technical interviewer.
Evaluate the candidate's answer.

Question:
{question}

Candidate Answer:
{answer}

Score the answer from 1-10.

Return ONLY valid JSON.

Schema:
{{
  "score": 8,
  "feedback": "Short professional feedback explaining strengths and weaknesses."
}}
"""


def evaluate_answer(
        question: str,
        answer: str,
) -> EvaluationResult:
    try:
        response = _model.generate_content(
            _EVALUATION_PROMPT.format(
                question=question,
                answer=answer,
            )
        )

        content = response.text.strip()

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        parsed = json.loads(content)
        score = int(parsed.get("score", 5))
        score = max(1, min(10, score))

        feedback = parsed.get(
            "feedback",
            "No feedback generated.",
        )

        return EvaluationResult(
            score=score,
            feedback=feedback,
        )

    except Exception as exc:
        logger.exception(
            "Evaluation failed: %s",
            exc,
        )

        return EvaluationResult(
            score=5,
            feedback="Evaluation unavailable.",
        )