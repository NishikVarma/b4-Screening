"""
Checks the labels against the real PDFs. Run from backend/:

    python -m eval.validate_labels                    # exit 1 on any problem
    python -m eval.validate_labels --review           # also write eval/labels_review.md
    python -m eval.validate_labels --configs 500/50,250/50,150/30

Per expected entry it reports: anchor found, how often, on which page, and
whether the anchor lands whole inside at least one chunk for each config.
"""

import argparse
import sys

import fitz  # pymupdf

from eval import labels as labels_mod
from eval.metrics import normalize

REVIEW_PATH = labels_mod.EVAL_DIR / "labels_review.md"


def _load_books(filenames: set[str]) -> dict[str, list[str]]:
    """filename -> normalized text of every page."""
    books = {}
    for name in sorted(filenames):
        with fitz.open(str(labels_mod.KB_DIR / "ai_ml" / name)) as doc:
            books[name] = [normalize(page.get_text("text")) for page in doc]
    return books


def _check_normalize_in_sync() -> None:
    from app.services.rag.ingest import _clean_text

    sample = "Café  ‘quoted’ text\twith \x07 ctrl\nand  Caps -- ok"
    assert normalize(sample) == _clean_text(sample).lower(), "metrics.normalize drifted from ingest._clean_text"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--configs", default="500/50")
    args = parser.parse_args()

    data = labels_mod.load()
    problems = labels_mod.schema_errors(data)
    if problems:
        print("\n".join(problems))
        return 1

    _check_normalize_in_sync()
    from app.services.rag.ingest import chunk_text

    configs = [tuple(int(x) for x in c.split("/")) for c in args.configs.split(",")]
    source_keys = labels_mod.kb_source_keys("ai_ml")

    # byte-identical files share text, so read one per content key
    first_name_for_key: dict[str, str] = {}
    for name, key in source_keys.items():
        first_name_for_key.setdefault(key, name)
    wanted = {e["source"] for it in data["items"] for e in it["expected"]}
    books = _load_books({first_name_for_key[source_keys[w]] for w in wanted})

    chunk_cache: dict[tuple, list[str]] = {}
    review = ["# Label review", "", "Each anchor is shown with its surrounding text from the book (cleaned).", ""]
    bad = 0

    for item in data["items"]:
        review += [f"## {item['id']}: {item['topic']}", "", f"Profile: `{item['profile']}`", ""]
        for entry in item["expected"]:
            book = first_name_for_key[source_keys[entry["source"]]]
            pages = books[book]
            anchor = normalize(entry["anchor"])
            full = " ".join(pages)
            count = full.count(anchor)
            page_no = next((n for n, p in enumerate(pages, 1) if anchor in p), None)
            status = []
            if count == 0:
                status.append("NOT FOUND")
            elif count > 1:
                status.append(f"appears {count}x")
            if page_no is None and count:
                status.append("spans a page break")
            for size, overlap in configs:
                if count == 0:
                    break
                key = (book, size, overlap)
                if key not in chunk_cache:
                    chunk_cache[key] = [c.lower() for c in chunk_text(" ".join(pages), size, overlap)]
                if not any(anchor in c for c in chunk_cache[key]):
                    status.append(f"split by chunking at {size}/{overlap}")
            flag = "ok" if not status else "; ".join(status)
            if count == 0 or any(s.startswith("split") for s in status):
                bad += 1
            print(f"{item['id']} {entry['source']:<17} page {page_no!s:>4}  {flag}")
            if count:
                at = full.find(anchor)
                context = full[max(0, at - 250): at + len(anchor) + 250]
                review += [f"- **{entry['source']}**, page {page_no}", f"  - anchor: `{entry['anchor']}`", f"  - context: ...{context}...", ""]
            else:
                review += [f"- **{entry['source']}**: anchor NOT FOUND: `{entry['anchor']}`", ""]

    if args.review:
        REVIEW_PATH.write_text("\n".join(review), encoding="utf-8")
        print(f"wrote {REVIEW_PATH}")
    print(f"\n{bad} entries need attention")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
