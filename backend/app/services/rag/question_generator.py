"""
Generates interview questions using retrieved RAG context + resume data.
Called by the interview orchestrator at session start.
"""

import json
import logging
from dataclasses import dataclass

import google.generativeai as genai

from app.core.config import get_settings
from app.services.rag.retriever import (
    RetrievedChunk,
    build_queries_from_resume,
    retrieve_multi,
)

logger = logging.getLogger(__name__)
settings = get_settings()

genai.configure(api_key=settings.google_api_key)
_model = genai.GenerativeModel(settings.google_model)

TOTAL_QUESTIONS = 7


# ═══════════════════════════════════════════════════════════════
# Data container for a generated question
# ═══════════════════════════════════════════════════════════════

@dataclass
class GeneratedQuestion:
    order: int
    text: str
    difficulty: str           # easy | medium | hard
    source_topics: list[str]  # human-readable topics
    context_chunk_ids: list[str]  # traceability — which chunks produced this


# ═══════════════════════════════════════════════════════════════
# Prompt
# ═══════════════════════════════════════════════════════════════

_QUESTION_PROMPT = """
You are a senior technical interviewer conducting a role-based screening interview.

Your job is to generate exactly {total} interview questions for the candidate below.

─── CANDIDATE PROFILE ───────────────────────────────────────────
Role applying for : {role}
Seniority level   : {seniority}
Skills            : {skills}
Domain exposure   : {domains}
Experience summary: {experience}

─── KNOWLEDGE BASE CONTEXT ──────────────────────────────────────
The following excerpts are from authoritative textbooks on the subject.
Use them as the PRIMARY source for question content.

{context_blocks}

─── INSTRUCTIONS ────────────────────────────────────────────────
1. Generate exactly {total} questions total.
2. Mix of difficulty: 2 easy, 3 medium, 2 hard — scaled to the seniority level.
3. Every question MUST be grounded in the knowledge base context above.
4. Questions must be specific to the candidate's skills and domain exposure.
5. No generic "tell me about yourself" questions.
6. No yes/no questions — all should require explanation or reasoning.
7. For senior candidates, include at least one system design or tradeoff question.

Return ONLY a valid JSON array — no markdown, no explanation, no extra text.

Schema for each question object:
{{
  "order": 1,
  "text": "The full question text",
  "difficulty": "easy | medium | hard",
  "source_topics": ["topic1", "topic2"]
}}
"""


# ═══════════════════════════════════════════════════════════════
# Context formatter
# ═══════════════════════════════════════════════════════════════

def _format_context_blocks(chunks: list[RetrievedChunk], max_chunks: int = 8) -> str:
    """
    Format top chunks into a numbered block for the prompt.
    Limit total context to avoid hitting token limits.
    """
    selected = chunks[:max_chunks]
    blocks = []
    for i, chunk in enumerate(selected, 1):
        blocks.append(
            f"[{i}] Source: {chunk.source} (relevance: {chunk.relevance_score:.2f})\n"
            f"{chunk.text[:600]}"  # cap each chunk at 600 chars in prompt
        )
    return "\n\n".join(blocks)


# ═══════════════════════════════════════════════════════════════
# LLM call + parsing
# ═══════════════════════════════════════════════════════════════

def _call_llm(prompt: str) -> list[dict]:
    """Call Gemini and parse the returned JSON array."""
    try:
        response = _model.generate_content(prompt)
        content = response.text.strip()

        # strip accidental markdown fences
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        parsed = json.loads(content)
        if not isinstance(parsed, list):
            raise ValueError("LLM did not return a JSON array.")
        return parsed

    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s", exc)
        raise
    except Exception as exc:
        logger.error("Question generation LLM call failed: %s", exc)
        raise


def _parse_questions(
        raw: list[dict],
        chunks: list[RetrievedChunk],
) -> list[GeneratedQuestion]:
    """Validate and convert raw dicts into GeneratedQuestion objects."""
    questions = []
    chunk_ids = [c.chunk_id for c in chunks]

    for i, item in enumerate(raw):
        try:
            difficulty = item.get("difficulty", "medium").lower()
            if difficulty not in ("easy", "medium", "hard"):
                difficulty = "medium"

            questions.append(GeneratedQuestion(
                order=item.get("order", i + 1),
                text=item["text"].strip(),
                difficulty=difficulty,
                source_topics=item.get("source_topics", []),
                # assign the top chunk ids as traceability
                # (we can't know exactly which chunk inspired each question)
                context_chunk_ids=chunk_ids[:3],
            ))
        except KeyError as exc:
            logger.warning("Skipping malformed question object: missing %s", exc)

    return questions


# ═══════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════

def generate_questions(
        role: str,
        skills: list[str],
        domain_exposure: list[str],
        seniority_level: str,
        experience_summary: str,
) -> list[GeneratedQuestion]:
    """
    Full pipeline:
      resume data → retrieval queries → RAG chunks → Gemini → questions

    Returns a list of GeneratedQuestion sorted by order.
    """
    # 1. build targeted queries from resume
    queries = build_queries_from_resume(
        role=role,
        skills=skills,
        domain_exposure=domain_exposure,
        seniority_level=seniority_level,
    )
    logger.info("Built %d retrieval queries for role='%s'", len(queries), role)

    # 2. retrieve relevant chunks
    chunks = retrieve_multi(
        queries=queries,
        role=role,
        top_k_per_query=4,
    )
    if not chunks:
        raise RuntimeError(
            "No chunks retrieved. Make sure ingest has been run for this role."
        )
    logger.info("Retrieved %d unique chunks for question generation", len(chunks))

    # 3. build prompt
    prompt = _QUESTION_PROMPT.format(
        total=TOTAL_QUESTIONS,
        role=role.replace("_", " ").title(),
        seniority=seniority_level,
        skills=", ".join(skills[:10]) or "Not specified",
        domains=", ".join(domain_exposure[:6]) or "Not specified",
        experience=experience_summary[:400] or "Not provided",
        context_blocks=_format_context_blocks(chunks),
    )

    # 4. call LLM
    raw_questions = _call_llm(prompt)
    logger.info("LLM returned %d raw questions", len(raw_questions))

    # 5. parse + validate
    questions = _parse_questions(raw_questions, chunks)

    # ensure correct ordering
    questions.sort(key=lambda q: q.order)

    logger.info(
        "Generated %d questions for session (role=%s, seniority=%s)",
        len(questions), role, seniority_level,
    )
    return questions