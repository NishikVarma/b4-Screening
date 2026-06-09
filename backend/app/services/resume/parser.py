import json
import logging
from pathlib import Path

import fitz  # pymupdf
import google.generativeai as genai

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── configure Gemini once at import time ──────────────────────
genai.configure(api_key=settings.google_api_key)
_model = genai.GenerativeModel(settings.google_model)


# ═══════════════════════════════════════════════════════════════
# PDF → raw text
# ═══════════════════════════════════════════════════════════════

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF given its raw bytes."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text("text") for page in doc]
        doc.close()
        text = "\n".join(pages).strip()
        if not text:
            raise ValueError("PDF appears to be empty or image-only (no selectable text).")
        return text
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        raise


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Decode a plain-text resume."""
    try:
        return file_bytes.decode("utf-8", errors="replace").strip()
    except Exception as exc:
        logger.error("Text file decoding failed: %s", exc)
        raise


def extract_raw_text(file_bytes: bytes, filename: str) -> str:
    """Route to the correct extractor based on file extension."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif suffix in (".txt", ".md"):
        return extract_text_from_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Upload a PDF or TXT file.")


# ═══════════════════════════════════════════════════════════════
# raw text → structured data via Gemini
# ═══════════════════════════════════════════════════════════════

_PARSE_PROMPT = """
You are a technical recruiter assistant. Analyse the resume text below and
return ONLY a valid JSON object — no markdown, no explanation, no extra text.

Schema:
{{
  "skills": ["list", "of", "technical", "skills"],
  "experience_summary": "2-3 sentence summary of the candidate's overall experience",
  "domain_exposure": ["list", "of", "technical", "domains", "e.g. NLP, Computer Vision, Backend, DevOps"],
  "seniority_level": "junior | mid | senior"
}}

Rules:
- skills: extract every technology, language, framework, tool mentioned
- domain_exposure: infer broader domains from the skills and project descriptions
- seniority_level: judge from years of experience and complexity of work described
- If a field cannot be determined, use null

Resume:
---
{resume_text}
---
"""


def parse_resume_with_llm(raw_text: str) -> dict:
    """
    Send raw resume text to Gemini and get back a structured dict with:
    skills, experience_summary, domain_exposure, seniority_level.
    """
    # truncate to ~6000 chars to stay well within token limits
    truncated = raw_text[:6000]
    prompt = _PARSE_PROMPT.format(resume_text=truncated)

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
        return _validate_parsed(parsed)

    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s", exc)
        return _empty_parsed()
    except Exception as exc:
        logger.error("Resume LLM parsing failed: %s", exc)
        return _empty_parsed()


def _validate_parsed(data: dict) -> dict:
    """Ensure all expected keys exist and have the right types."""
    skills = data.get("skills")
    domain_exposure = data.get("domain_exposure")

    return {
        "skills": skills if isinstance(skills, list) else [],
        "experience_summary": data.get("experience_summary") or "",
        "domain_exposure": domain_exposure if isinstance(domain_exposure, list) else [],
        "seniority_level": data.get("seniority_level") or "mid",
    }


def _empty_parsed() -> dict:
    return {
        "skills": [],
        "experience_summary": "",
        "domain_exposure": [],
        "seniority_level": "mid",
    }


# ═══════════════════════════════════════════════════════════════
# public entry point
# ═══════════════════════════════════════════════════════════════

def process_resume(file_bytes: bytes, filename: str) -> dict:
    """
    Full pipeline:
      bytes → raw text → structured dict

    Returns:
      {
        "raw_text": str,
        "skills": list[str],
        "experience_summary": str,
        "domain_exposure": list[str],
        "seniority_level": str,
      }
    """
    raw_text = extract_raw_text(file_bytes, filename)
    structured = parse_resume_with_llm(raw_text)
    return {"raw_text": raw_text, **structured}