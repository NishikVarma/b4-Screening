"""Tests for the retrieval changes. Skipped where chromadb / pymupdf are not installed (CI)."""

import pytest

pytest.importorskip("chromadb")
fitz = pytest.importorskip("fitz")

from app.services.rag import ingest, retriever  # noqa: E402


def _chunk(chunk_id, text, score):
    return retriever.RetrievedChunk(chunk_id, text, "x.pdf", score, 0)


def test_retrieve_multi_dedupes_identical_text_under_different_ids(monkeypatch):
    twins = [_chunk("a_1", "same  passage\nhere", 0.6), _chunk("b_9", "same passage here", 0.8)]
    other = [_chunk("c_3", "different passage", 0.7)]
    monkeypatch.setattr(retriever, "retrieve", lambda q, role, top_k=None: twins if q == "q1" else other)

    merged = retriever.retrieve_multi(["q1", "q2"], role="ai_ml")

    assert [c.chunk_id for c in merged] == ["b_9", "c_3"]  # best-scoring twin kept, sorted by score


def test_embedding_function_is_built_once():
    assert retriever._get_embedding_function.cache_info().maxsize == 1


def test_body_pages_are_valid_ranges_inside_each_book():
    kb = ingest.Path(ingest.settings.knowledge_base_dir).resolve() / "ai_ml"
    for name, (first, last) in ingest.BODY_PAGES.items():
        with fitz.open(str(kb / name)) as doc:
            assert 1 <= first <= last <= len(doc), name
