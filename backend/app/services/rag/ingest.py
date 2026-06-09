"""
Run this script ONCE before starting the server to populate ChromaDB.

Usage (from backend/):
    python -m app.services.rag.ingest
"""

import json
import logging
import re
import sys
from pathlib import Path

import fitz  # pymupdf
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

ROLE_COLLECTION_MAP = {
    "ai_ml": "knowledge_ai_ml",
    "backend": "knowledge_backend",
}


# ═══════════════════════════════════════════════════════════════
# ChromaDB client (singleton)
# ═══════════════════════════════════════════════════════════════

def get_chroma_client() -> chromadb.ClientAPI:
    persist_dir = Path(settings.chroma_persist_dir).resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_embedding_function():
    return SentenceTransformerEmbeddingFunction(
        model_name=settings.embedding_model
    )


# ═══════════════════════════════════════════════════════════════
# PDF loading
# ═══════════════════════════════════════════════════════════════

def load_pdf(path: Path) -> str:
    """Extract all text from a PDF file."""
    doc = fitz.open(str(path))
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(pages)


def load_all_pdfs(role: str) -> list[dict]:
    """
    Load every PDF from knowledge_base/<role>/.
    Returns list of {filename, text}.
    """
    kb_dir = Path(settings.knowledge_base_dir).resolve() / role
    if not kb_dir.exists():
        raise FileNotFoundError(f"Knowledge base directory not found: {kb_dir}")

    docs = []
    pdf_files = list(kb_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDFs found in {kb_dir}")

    for pdf_path in pdf_files:
        logger.info("Loading %s ...", pdf_path.name)
        try:
            text = load_pdf(pdf_path)
            if text.strip():
                docs.append({"filename": pdf_path.name, "text": text})
            else:
                logger.warning("Skipping %s — no extractable text.", pdf_path.name)
        except Exception as exc:
            logger.error("Failed to load %s: %s", pdf_path.name, exc)

    logger.info("Loaded %d documents for role '%s'.", len(docs), role)
    return docs


# ═══════════════════════════════════════════════════════════════
# Chunking
# ═══════════════════════════════════════════════════════════════

def _clean_text(text: str) -> str:
    """Remove excessive whitespace and non-printable characters."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x20-\x7E\n]", "", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split text into overlapping word-based chunks.
    Word-based (not character-based) so chunks don't cut mid-sentence
    as aggressively.
    """
    text = _clean_text(text)
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 50:   # skip near-empty chunks
            chunks.append(chunk)
        start += chunk_size - overlap  # slide window with overlap

    return chunks


# ═══════════════════════════════════════════════════════════════
# Ingest pipeline
# ═══════════════════════════════════════════════════════════════

def ingest_role(role: str, reset: bool = False) -> int:
    """
    Full ingest pipeline for one role:
      PDFs → text → chunks → embeddings → ChromaDB

    Args:
        role:  e.g. "ai_ml"
        reset: if True, wipe the existing collection before ingesting

    Returns:
        Number of chunks stored.
    """
    collection_name = ROLE_COLLECTION_MAP.get(role)
    if not collection_name:
        raise ValueError(f"Unknown role '{role}'. Valid: {list(ROLE_COLLECTION_MAP)}")

    client = get_chroma_client()
    embed_fn = get_embedding_function()

    # optionally wipe existing data
    if reset:
        try:
            client.delete_collection(collection_name)
            logger.info("Deleted existing collection '%s'.", collection_name)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    # skip if already populated and reset not requested
    existing = collection.count()
    if existing > 0 and not reset:
        logger.info(
            "Collection '%s' already has %d chunks. Skipping. "
            "Pass reset=True to re-ingest.",
            collection_name, existing,
        )
        return existing

    # load PDFs
    docs = load_all_pdfs(role)

    # chunk + collect
    all_ids, all_texts, all_metas = [], [], []
    chunk_index = 0

    for doc in docs:
        chunks = chunk_text(
            doc["text"],
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        logger.info("  %s → %d chunks", doc["filename"], len(chunks))

        for i, chunk in enumerate(chunks):
            all_ids.append(f"{role}_{chunk_index:06d}")
            all_texts.append(chunk)
            all_metas.append({
                "source": doc["filename"],
                "role": role,
                "chunk_index": chunk_index,
                "chunk_in_doc": i,
            })
            chunk_index += 1

    # batch upsert (ChromaDB recommends batches of ≤5000)
    batch_size = 500
    for start in range(0, len(all_ids), batch_size):
        collection.upsert(
            ids=all_ids[start : start + batch_size],
            documents=all_texts[start : start + batch_size],
            metadatas=all_metas[start : start + batch_size],
        )
        logger.info(
            "  Upserted batch %d-%d / %d",
            start, min(start + batch_size, len(all_ids)), len(all_ids),
        )

    total = collection.count()
    logger.info("Ingest complete. Collection '%s' now has %d chunks.", collection_name, total)
    return total


# ═══════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest knowledge base into ChromaDB.")
    parser.add_argument(
        "--role",
        choices=list(ROLE_COLLECTION_MAP.keys()),
        default="ai_ml",
        help="Which role's knowledge base to ingest (default: ai_ml)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe the existing collection and re-ingest from scratch",
    )
    args = parser.parse_args()

    try:
        total = ingest_role(role=args.role, reset=args.reset)
        logger.info("Done. %d chunks ready for retrieval.", total)
        sys.exit(0)
    except Exception as exc:
        logger.error("Ingest failed: %s", exc)
        sys.exit(1)