"""
Retrieves relevant chunks from ChromaDB at runtime.
Called by the question generator with a query built from resume + role.
"""

import logging
from dataclasses import dataclass

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from chromadb.config import Settings as ChromaSettings
from pathlib import Path

from app.core.config import get_settings
from app.services.rag.ingest import ROLE_COLLECTION_MAP

logger = logging.getLogger(__name__)
settings = get_settings()


# ═══════════════════════════════════════════════════════════════
# Data container for a single retrieved chunk
# ═══════════════════════════════════════════════════════════════

@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    source: str          # which PDF it came from
    relevance_score: float  # 0.0 (least) → 1.0 (most relevant)
    chunk_index: int


# ═══════════════════════════════════════════════════════════════
# Client — reuse a single instance across the app lifetime
# ═══════════════════════════════════════════════════════════════

_chroma_client: chromadb.ClientAPI | None = None

def _get_client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        persist_dir = Path(settings.chroma_persist_dir).resolve()
        _chroma_client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def _get_embedding_function():
    return SentenceTransformerEmbeddingFunction(
        model_name=settings.embedding_model
    )


# ═══════════════════════════════════════════════════════════════
# Core retrieval
# ═══════════════════════════════════════════════════════════════

def retrieve(
        query: str,
        role: str,
        top_k: int | None = None,
) -> list[RetrievedChunk]:
    """
    Query ChromaDB for chunks most relevant to `query` for a given `role`.

    Args:
        query:  Natural language query (built from resume + role context).
        role:   e.g. "ai_ml" — selects the right collection.
        top_k:  Number of chunks to return. Defaults to settings.retrieval_top_k.

    Returns:
        List of RetrievedChunk sorted by relevance (highest first).
    """
    top_k = top_k or settings.retrieval_top_k
    collection_name = ROLE_COLLECTION_MAP.get(role)

    if not collection_name:
        raise ValueError(f"Unknown role '{role}'. Valid: {list(ROLE_COLLECTION_MAP)}")

    client = _get_client()

    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=_get_embedding_function(),
        )
    except Exception:
        raise RuntimeError(
            f"Collection '{collection_name}' not found. "
            f"Run: python -m app.services.rag.ingest --role {role}"
        )

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    ids = results["ids"][0]

    for chunk_id, text, meta, distance in zip(ids, documents, metadatas, distances):
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        # convert to a 0-1 relevance score
        relevance = round(1 - (distance / 2), 4)
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                text=text,
                source=meta.get("source", "unknown"),
                relevance_score=relevance,
                chunk_index=meta.get("chunk_index", -1),
            )
        )

    logger.debug(
        "Retrieved %d chunks for query='%s...' role='%s'",
        len(chunks), query[:60], role,
    )
    return chunks


# ═══════════════════════════════════════════════════════════════
# Multi-query retrieval — reduces single-query blind spots
# ═══════════════════════════════════════════════════════════════

def retrieve_multi(
        queries: list[str],
        role: str,
        top_k_per_query: int = 3,
) -> list[RetrievedChunk]:
    """
    Run multiple queries and merge results, deduplicating by chunk_id.
    Returns chunks sorted by best relevance score seen across all queries.

    Use this when you have several angles on what to ask about
    (e.g. one query per skill extracted from the resume).
    """
    seen: dict[str, RetrievedChunk] = {}

    for query in queries:
        try:
            results = retrieve(query, role, top_k=top_k_per_query)
            for chunk in results:
                # keep the highest relevance score for a chunk seen in multiple queries
                if chunk.chunk_id not in seen or chunk.relevance_score > seen[chunk.chunk_id].relevance_score:
                    seen[chunk.chunk_id] = chunk
        except Exception as exc:
            logger.warning("Query failed, skipping: %s | error: %s", query, exc)

    merged = sorted(seen.values(), key=lambda c: c.relevance_score, reverse=True)
    logger.info(
        "Multi-query retrieval: %d queries → %d unique chunks",
        len(queries), len(merged),
    )
    return merged


# ═══════════════════════════════════════════════════════════════
# Query builder — constructs queries from resume data
# ═══════════════════════════════════════════════════════════════

def build_queries_from_resume(
        role: str,
        skills: list[str],
        domain_exposure: list[str],
        seniority_level: str,
) -> list[str]:
    """
    Construct a set of targeted retrieval queries from parsed resume data.
    More specific queries → more relevant chunks → better questions.
    """
    queries = []

    # role-level baseline query
    queries.append(f"core concepts and fundamentals for {role.replace('_', ' ')} engineer")

    # skill-based queries (top 5 skills to avoid too many queries)
    for skill in skills[:5]:
        queries.append(f"{skill} theory concepts and applications")

    # domain queries
    for domain in domain_exposure[:3]:
        queries.append(f"{domain} technical interview questions and concepts")

    # seniority-adjusted query
    if seniority_level == "senior":
        queries.append("advanced machine learning system design and optimization")
    elif seniority_level == "junior":
        queries.append("basic machine learning concepts definitions and intuition")
    else:
        queries.append("intermediate machine learning algorithms and practical applications")

    return queries