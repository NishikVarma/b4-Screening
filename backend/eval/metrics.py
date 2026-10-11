"""
Retrieval metrics. Pure Python: no app or third-party imports, so CI can test
this without torch, chromadb or the PDFs.

Vocabulary
  expected : list of {"source_key": str, "anchor": str} for one eval item.
             source_key identifies a file by content (md5), so byte-identical
             copies of a book count as the same source.
  matches  : for one ranked list, one entry per retrieved chunk: the sorted
             indexes of the `expected` entries that chunk satisfies.
"""

import re
from collections.abc import Sequence

MAX_K = 8
KS = (1, 3, 5, 8)


def normalize(text: str) -> str:
    """Same cleaning as rag.ingest._clean_text, then lowercase.
    validate_labels.py asserts the two stay in sync."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x20-\x7E\n]", "", text)
    return text.strip().lower()


def matched_entries(source_key: str, text: str, expected: Sequence[dict]) -> list[int]:
    """Indexes of expected entries satisfied by one retrieved chunk."""
    norm = normalize(text)
    return [
        i
        for i, entry in enumerate(expected)
        if entry["source_key"] == source_key and normalize(entry["anchor"]) in norm
    ]


def hit_at_k(matches: Sequence[Sequence[int]], k: int) -> float:
    return 1.0 if any(matches[:k]) else 0.0


def reciprocal_rank(matches: Sequence[Sequence[int]]) -> float:
    for rank, m in enumerate(matches, start=1):
        if m:
            return 1.0 / rank
    return 0.0


def recall_at_k(matches: Sequence[Sequence[int]], n_expected: int, k: int) -> float:
    if n_expected <= 0:
        raise ValueError("an item needs at least one expected entry")
    covered = set()
    for m in matches[:k]:
        covered.update(m)
    return len(covered) / n_expected


def duplicate_rate_at_k(text_hashes: Sequence[str], k: int) -> float:
    """Share of the top-k chunks whose text equals an earlier chunk's text."""
    top = text_hashes[:k]
    if not top:
        return 0.0
    return (len(top) - len(set(top))) / len(top)


def score_item(item: dict, ks: Sequence[int] = KS) -> dict:
    """item: {"matches": [...], "text_hashes": [...], "n_expected": int}"""
    matches, hashes, n = item["matches"], item["text_hashes"], item["n_expected"]
    out = {"mrr": reciprocal_rank(matches)}
    for k in ks:
        out[f"hit@{k}"] = hit_at_k(matches, k)
        out[f"recall@{k}"] = recall_at_k(matches, n, k)
        out[f"dup@{k}"] = duplicate_rate_at_k(hashes, k)
    return out


def aggregate(scored: Sequence[dict]) -> dict:
    """Mean of every metric over items."""
    if not scored:
        raise ValueError("no items to aggregate")
    keys = scored[0].keys()
    return {key: sum(s[key] for s in scored) / len(scored) for key in keys}
