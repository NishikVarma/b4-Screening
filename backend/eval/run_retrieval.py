"""
Retrieval evaluation. Run from backend/:

    python -m eval.run_retrieval                  # chunk configs 500/50, 250/50, 150/30
    python -m eval.run_retrieval --configs 500/50 # default config only

Needs no Gemini key. Writes JSON + markdown to eval/results/.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from importlib import metadata
from pathlib import Path

from eval import labels as labels_mod
from eval.metrics import KS, aggregate, score_item

DEFAULT_CONFIGS = "500/50,250/50,150/30"
STRATEGIES = ("role_only", "single_concat", "multi_production")
STRATEGY_NOTES = {
    "role_only": "production's first query only (ignores the resume), a floor",
    "single_concat": "one query: role + seniority + all skills/domains joined",
    "multi_production": "build_queries_from_resume + retrieve_multi, unmodified",
}
CACHE_DIR = labels_mod.EVAL_DIR / ".cache"
RESULTS_DIR = labels_mod.EVAL_DIR / "results"


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=labels_mod.BACKEND_DIR, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _version(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return "not installed"


def _run_worker(size: int, overlap: int, kb_hash: str, out_path: Path) -> dict:
    persist = CACHE_DIR / f"{size}_{overlap}_{kb_hash}"
    env = dict(
        os.environ,
        CHROMA_PERSIST_DIR=str(persist),
        CHUNK_SIZE=str(size),
        CHUNK_OVERLAP=str(overlap),
    )
    subprocess.run(
        [sys.executable, "-m", "eval.worker", "--out", str(out_path)],
        cwd=labels_mod.BACKEND_DIR,
        env=env,
        check=True,
    )
    return json.loads(out_path.read_text(encoding="utf-8"))


def _score_config(raw: dict) -> dict:
    per_strategy = {}
    for name in STRATEGIES:
        scored = []
        for item in raw["items"]:
            ranked = item["strategies"][name]
            scored.append({
                "id": item["id"],
                **score_item({
                    "matches": [r["matches"] for r in ranked],
                    "text_hashes": [r["text_hash"] for r in ranked],
                    "n_expected": item["n_expected"],
                }),
            })
        metrics_only = [{k: v for k, v in s.items() if k != "id"} for s in scored]
        per_strategy[name] = {"aggregate": aggregate(metrics_only), "items": scored}
    return per_strategy


def _combine_runs(runs: list[dict]) -> dict:
    """runs: _score_config outputs. Items are averaged per metric over runs;
    `runs` keeps every run's aggregate so the spread stays visible."""
    combined = {}
    for name in STRATEGIES:
        items = []
        for pos, first in enumerate(runs[0][name]["items"]):
            row = {"id": first["id"]}
            for key in first:
                if key != "id":
                    row[key] = sum(r[name]["items"][pos][key] for r in runs) / len(runs)
            items.append(row)
        combined[name] = {
            "aggregate": aggregate([{k: v for k, v in i.items() if k != "id"} for i in items]),
            "items": items,
            "runs": [r[name]["aggregate"] for r in runs],
        }
    return combined


def _range(runs: list[dict], key: str) -> str:
    vals = [r[key] for r in runs]
    return f"{min(vals):.2f}-{max(vals):.2f}"


def _paired(per_strategy: dict, a: str, b: str, key: str) -> tuple[int, int, int]:
    """(a better, b better, tie) over items for one metric."""
    wins = losses = ties = 0
    for x, y in zip(per_strategy[a]["items"], per_strategy[b]["items"]):
        if x[key] > y[key]:
            wins += 1
        elif x[key] < y[key]:
            losses += 1
        else:
            ties += 1
    return wins, losses, ties


def _markdown(report: dict) -> str:
    env = report["environment"]
    lines = [
        f"# Retrieval evaluation, {report['date']}",
        "",
        f"- Labelled items: {report['n_items']} (knowledge base `{report['role']}`, labels in `eval/labels/ai_ml.json`)",
        f"- Embedding model: `{env['embedding_model']}`, max_seq_length {env['max_seq_length']}",
        f"- chromadb {env['chromadb']}, sentence-transformers {env['sentence_transformers']}, git `{env['git_commit']}`{' (dirty)' if env['git_dirty'] else ''}",
        f"- Knowledge-base files: {env['kb_files']}",
        "- A retrieved chunk counts as a hit when it comes from an expected book and contains the expected anchor phrase.",
        "- No Gemini calls were made.",
        "- Chroma's approximate search returned slightly different top-8 lists in different processes on the same index, so each config is run several times and the spread is shown.",
        "",
    ]
    if env["kb_duplicates"]:
        lines += [
            "> Byte-identical files in the knowledge base (both are ingested): "
            + "; ".join(" = ".join(group) for group in env["kb_duplicates"]),
            "",
        ]
    head = ["Strategy"] + [f"Hit@{k}" for k in KS] + ["MRR", "Recall@5", "Recall@8", "Dup@8"]
    for cfg in report["configs"]:
        lines += [
            f"## chunk_size={cfg['chunk_size']} overlap={cfg['chunk_overlap']} ({cfg['n_chunks']} chunks)",
            "",
            f"Mean over {cfg['repeats']} runs, (min-max) in brackets.",
            "",
            "| " + " | ".join(head) + " |",
            "|" + "|".join(["---"] * len(head)) + "|",
        ]
        for name in STRATEGIES:
            a = cfg["strategies"][name]["aggregate"]
            runs = cfg["strategies"][name]["runs"]
            cell = lambda key: f"{a[key]:.2f} ({_range(runs, key)})"
            row = [f"`{name}`"] + [cell(f"hit@{k}") for k in KS]
            row += [cell("mrr"), cell("recall@5"), cell("recall@8"), cell("dup@8")]
            lines.append("| " + " | ".join(row) + " |")
        w, l, t = _paired(cfg["strategies"], "multi_production", "single_concat", "mrr")
        w5, l5, t5 = _paired(cfg["strategies"], "multi_production", "single_concat", "hit@5")
        lines += [
            "",
            f"`multi_production` vs `single_concat`, per item (run-averaged): MRR better/worse/same = {w}/{l}/{t}; Hit@5 better/worse/same = {w5}/{l5}/{t5}.",
            "",
        ]
        for name in STRATEGIES:
            misses = [i["id"] for i in cfg["strategies"][name]["items"] if i["hit@5"] == 0]
            lines.append(f"- `{name}` never hit at k=5 in any run ({len(misses)}/{report['n_items']}): {', '.join(misses) or 'none'}")
        lines.append("")
    lines += ["## Strategies", ""]
    lines += [f"- `{k}`: {v}" for k, v in STRATEGY_NOTES.items()]
    lines += [
        "",
        "Note: the strategies differ in candidate-pool size (`multi_production` merges up to ~36 chunks from ~9 queries and ranks by best relevance; the others take the top 8 of one query). Every list is cut to its first 8 chunks before scoring.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs", default=DEFAULT_CONFIGS, help="comma list of chunk_size/overlap")
    parser.add_argument("--out-dir", default=str(RESULTS_DIR))
    parser.add_argument(
        "--repeats", type=int, default=5,
        help="runs per config; Chroma's approximate search is not identical between processes",
    )
    args = parser.parse_args()

    data = labels_mod.load()
    problems = labels_mod.schema_errors(data)
    if problems:
        sys.exit("labels invalid:\n  " + "\n  ".join(problems))

    configs = [tuple(int(x) for x in c.split("/")) for c in args.configs.split(",")]
    source_keys = labels_mod.kb_source_keys("ai_ml")
    # the index depends on the PDFs and on how ingest reads them (BODY_PAGES, chunking)
    ingest_src = (labels_mod.BACKEND_DIR / "app" / "services" / "rag" / "ingest.py").read_bytes()
    kb_hash = hashlib.md5(
        json.dumps(source_keys, sort_keys=True).encode() + ingest_src
    ).hexdigest()[:8]
    by_key: dict[str, list[str]] = {}
    for name, key in source_keys.items():
        by_key.setdefault(key, []).append(name)

    results = []
    for size, overlap in configs:
        print(f"== chunk_size={size} overlap={overlap}", flush=True)
        raws = []
        for n in range(args.repeats):
            print(f"-- run {n + 1}/{args.repeats}", flush=True)
            with tempfile.TemporaryDirectory() as tmp:
                raws.append(_run_worker(size, overlap, kb_hash, Path(tmp) / "raw.json"))
        raw = raws[0]
        results.append({
            "chunk_size": raw["chunk_size"],
            "chunk_overlap": raw["chunk_overlap"],
            "n_chunks": raw["n_chunks"],
            "index_seconds": raw["index_seconds"],
            "queries": {i["id"]: i["queries"] for i in raw["items"]},
            "repeats": args.repeats,
            "strategies": _combine_runs([_score_config(r) for r in raws]),
            "rankings_run1": {i["id"]: i["strategies"] for i in raw["items"]},
            "_embedding_model": raw["embedding_model"],
            "_max_seq_length": raw["max_seq_length"],
        })

    status = _git("status", "--porcelain", "--", "eval", "../knowledge_base", "app")
    report = {
        "date": date.today().isoformat(),
        "role": "ai_ml",
        "n_items": len(data["items"]),
        "environment": {
            "embedding_model": results[0].pop("_embedding_model"),
            "max_seq_length": results[0].pop("_max_seq_length"),
            "chromadb": _version("chromadb"),
            "sentence_transformers": _version("sentence-transformers"),
            "git_commit": _git("rev-parse", "--short", "HEAD"),
            "git_dirty": bool(status) and status != "unknown",
            "kb_files": source_keys,
            "kb_duplicates": [sorted(v) for v in by_key.values() if len(v) > 1],
        },
        "configs": results,
    }
    for r in results[1:]:
        r.pop("_embedding_model", None)
        r.pop("_max_seq_length", None)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg_hash = hashlib.md5(
        json.dumps([list(c) for c in configs] + [kb_hash]).encode()
    ).hexdigest()[:8]
    stem = out_dir / f"retrieval_{report['date']}_{cfg_hash}"
    stem.with_suffix(".json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    stem.with_suffix(".md").write_text(_markdown(report), encoding="utf-8")
    print(f"wrote {stem}.json and .md")


if __name__ == "__main__":
    main()
