"""
Runs inside a subprocess started by run_retrieval.py, with CHROMA_PERSIST_DIR,
CHUNK_SIZE and CHUNK_OVERLAP set in the environment.

It builds the index with the real rag.ingest.ingest_role and retrieves with the
real rag.retriever functions. It never imports the Gemini modules, so no API key
or quota is involved.

    python -m eval.worker --out raw.json
"""

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

from eval import labels as labels_mod
from eval.metrics import MAX_K, matched_entries, normalize

ROLE = "ai_ml"
TOP_K_PER_QUERY = 4  # same constant question_generator.generate_questions uses
DONE_MARKER = ".complete"


def _prepare_index(persist_dir: Path) -> None:
    """Drop a half-built index so a crashed earlier run cannot be reused."""
    if persist_dir.exists() and not (persist_dir / DONE_MARKER).exists():
        shutil.rmtree(persist_dir)


def _concat_query(profile: dict) -> str:
    terms = profile["skills"] + profile["domain_exposure"]
    return f"{profile['role'].replace('_', ' ')} {profile['seniority_level']} " + ", ".join(terms)


def _describe(chunks, expected, source_keys) -> list[dict]:
    ranked = []
    for chunk in chunks[:MAX_K]:
        key = source_keys.get(chunk.source, chunk.source)
        ranked.append({
            "chunk_id": chunk.chunk_id,
            "source": chunk.source,
            "relevance": chunk.relevance_score,
            "text_hash": hashlib.sha1(normalize(chunk.text).encode()).hexdigest()[:12],
            "matches": matched_entries(key, chunk.text, expected),
            "preview": chunk.text[:160],
        })
    return ranked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--labels", default=str(labels_mod.LABELS_PATH))
    args = parser.parse_args()

    from app.core.config import get_settings

    settings = get_settings()
    persist_dir = Path(settings.chroma_persist_dir).resolve()
    _prepare_index(persist_dir)

    from app.services.rag import ingest, retriever

    started = time.time()
    n_chunks = ingest.ingest_role(ROLE)
    persist_dir.joinpath(DONE_MARKER).write_text("ok")
    index_seconds = round(time.time() - started, 1)

    embed_model = getattr(retriever._get_embedding_function(), "_model", None)
    max_seq_length = getattr(embed_model, "max_seq_length", None)

    source_keys = labels_mod.kb_source_keys(ROLE)
    data = labels_mod.load(Path(args.labels))
    items_out = []

    for item in data["items"]:
        profile = item["profile"]
        expected = labels_mod.resolve_expected(item, source_keys)
        queries = retriever.build_queries_from_resume(
            role=profile["role"],
            skills=profile["skills"],
            domain_exposure=profile["domain_exposure"],
            seniority_level=profile["seniority_level"],
        )
        single = _concat_query(profile)

        merged = retriever.retrieve_multi(
            queries=queries, role=profile["role"], top_k_per_query=TOP_K_PER_QUERY
        )
        strategies = {
            "role_only": retriever.retrieve(queries[0], profile["role"], top_k=MAX_K),
            "single_concat": retriever.retrieve(single, profile["role"], top_k=MAX_K),
            "multi_production": merged,
        }
        items_out.append({
            "id": item["id"],
            "topic": item["topic"],
            "n_expected": len(expected),
            "queries": {"role_only": queries[0], "single_concat": single, "multi_production": queries},
            "multi_pool_size": len(merged),
            "strategies": {
                name: _describe(chunks, expected, source_keys) for name, chunks in strategies.items()
            },
        })

    Path(args.out).write_text(
        json.dumps({
            "n_chunks": n_chunks,
            "index_seconds": index_seconds,
            "embedding_model": settings.embedding_model,
            "max_seq_length": max_seq_length,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "items": items_out,
        }, indent=1),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
