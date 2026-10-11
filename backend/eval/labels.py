"""Load and check the labelled set. Stdlib only."""

import hashlib
import json
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent
KB_DIR = BACKEND_DIR.parent / "knowledge_base"
LABELS_PATH = EVAL_DIR / "labels" / "ai_ml.json"

REQUIRED_PROFILE_KEYS = ("role", "skills", "domain_exposure", "seniority_level")
SENIORITIES = ("junior", "mid", "senior")


def load(path: Path = LABELS_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(data: dict) -> list[str]:
    """Human-readable problems with a labels file. Empty list means valid."""
    errors = []
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return ["'items' must be a non-empty list"]

    seen = set()
    for pos, item in enumerate(items):
        where = item.get("id", f"#{pos}")
        if where in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(where)

        profile = item.get("profile") or {}
        for key in REQUIRED_PROFILE_KEYS:
            if key not in profile:
                errors.append(f"{where}: profile is missing '{key}'")
        if profile.get("seniority_level") not in SENIORITIES:
            errors.append(f"{where}: seniority_level must be one of {SENIORITIES}")
        for key in ("skills", "domain_exposure"):
            if not isinstance(profile.get(key), list) or not profile.get(key):
                errors.append(f"{where}: profile.{key} must be a non-empty list")

        expected = item.get("expected")
        if not isinstance(expected, list) or not expected:
            errors.append(f"{where}: 'expected' must be a non-empty list")
            continue
        for entry in expected:
            if not str(entry.get("source", "")).endswith(".pdf"):
                errors.append(f"{where}: expected entry needs a .pdf 'source'")
            if len(str(entry.get("anchor", "")).split()) < 4:
                errors.append(f"{where}: anchor must be at least 4 words")
    return errors


def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def kb_source_keys(role: str = "ai_ml") -> dict[str, str]:
    """filename -> content md5. Byte-identical files share a key."""
    return {p.name: file_md5(p) for p in sorted((KB_DIR / role).glob("*.pdf"))}


def resolve_expected(item: dict, source_keys: dict[str, str]) -> list[dict]:
    """Expected entries as {"source_key", "anchor"} for metrics.matched_entries."""
    out = []
    for entry in item["expected"]:
        if entry["source"] not in source_keys:
            raise ValueError(f"{item['id']}: no such knowledge-base file {entry['source']!r}")
        out.append({"source_key": source_keys[entry["source"]], "anchor": entry["anchor"]})
    return out
