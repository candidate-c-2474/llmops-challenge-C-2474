#!/usr/bin/env python3
"""
RAG retrieval quality evaluation for RoomFit Copilot (Candidate C-2474).

Runs the 60-question eval set (data/eval_questions.jsonl) through the hybrid
retrieval pipeline in three configurations:
  1. Dense only
  2. Hybrid (BM25 + Dense, RRF fusion, no reranker)
  3. Hybrid + Cross-Encoder reranker

Reports Recall@5 and MRR per configuration, plus per-config latency.

Results are written to bench/results/rag_quality_<timestamp>.json.

Usage:
    python3 bench/run_rag_eval.py
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from datetime import datetime

# --- Make packages importable in a bare shell -------------------------------
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "packages" / "rag_core" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "inference_gateway" / "src"))

from rag_core.config import PostgresConfig, RetrievalConfig
from rag_core.repository import PostgresCatalogRepository
from rag_core.retrieval.bm25_retriever import BM25Retriever
from rag_core.retrieval.dense_retriever import DenseRetriever
from rag_core.retrieval.hybrid_pipeline import HybridRetrievalPipeline
from rag_core.retrieval.reranker import CrossEncoderReranker

EVAL_PATH = ROOT / "data" / "eval_questions.jsonl"
RESULTS_DIR = ROOT / "bench" / "results"
RESULTS_DIR.mkdir(exist_ok=True)

TOP_K = 5


def load_eval_questions():
    qs = []
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                qs.append(json.loads(line))
    return qs


def recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Fraction of expected IDs present in the top-k retrieved IDs."""
    top = set(retrieved_ids[:k])
    hits = top & set(expected_ids)
    return len(hits) / len(expected_ids) if expected_ids else 0.0


def token_recall_at_k(retrieved_chunks, token: str, k: int) -> float:
    """A retrieval counts as a hit if ANY of the top-k chunks contains
    the discriminative token in its content (case-insensitive). This is the
    semantically correct metric: multiple products legitimately match a
    category-style query, and any of them is a valid answer."""
    top = retrieved_chunks[:k]
    for c in top:
        if token.lower() in (c.content or "").lower():
            return 1.0
    return 0.0


def token_reciprocal_rank(retrieved_chunks, token: str) -> float:
    """MRR variant: rank of the first chunk whose content contains the token."""
    for rank, c in enumerate(retrieved_chunks, start=1):
        if token.lower() in (c.content or "").lower():
            return 1.0 / rank
    return 0.0


def reciprocal_rank(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    expected = set(expected_ids)
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in expected:
            return 1.0 / rank
    return 0.0


async def run_config(label: str, retrieve_fn, questions: list[dict]):
    """Run one retrieval configuration over all questions."""
    recalls = []
    rrs = []
    latencies = []
    details = []

    for q in questions:
        query = q["question"]
        expected = q["expected_product_ids"]

        t0 = time.perf_counter()
        chunks = await retrieve_fn(query, top_k=TOP_K)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        retrieved_ids = [c.product_id for c in chunks]
        token = q.get("discriminative_token")

        if q["type"] == "retrieval" and token:
            # Use token-based recall: any top-k chunk containing the token is a hit
            r = token_recall_at_k(chunks, token, TOP_K)
            rr = token_reciprocal_rank(chunks, token)
        else:
            # Use exact-ID recall for attribute/fit/compare
            r = recall_at_k(retrieved_ids, expected, TOP_K)
            rr = reciprocal_rank(retrieved_ids, expected)

        recalls.append(r)
        rrs.append(rr)
        latencies.append(elapsed_ms)
        details.append({
            "question_id": q["id"],
            "query": query,
            "expected": expected,
            "retrieved_top5": retrieved_ids,
            "recall": r,
            "rr": rr,
            "latency_ms": round(elapsed_ms, 2),
        })

    lat_sorted = sorted(latencies)
    p50 = lat_sorted[len(lat_sorted) // 2]
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)]

    return {
        "config": label,
        "n_questions": len(questions),
        "recall_at_5_mean": round(statistics.mean(recalls), 4),
        "mrr_mean": round(statistics.mean(rrs), 4),
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
        "latency_mean_ms": round(statistics.mean(latencies), 2),
        "details": details,
    }


async def main():
    print("=" * 65)
    print("  RAG Retrieval Quality Evaluation — Candidate C-2474")
    print("=" * 65)

    all_questions = load_eval_questions()
    # Retrieval quality is only meaningful for retrieval-type questions.
    # attribute/fit/compare require agent-level tool calls (get_product,
    # check_fit, compare_products), not the retrieval pipeline. See
    # docs/BENCHMARKS.md Section 4 for the rationale.
    questions = [q for q in all_questions if q["type"] == "retrieval"]
    print(f"\nLoaded {len(all_questions)} eval questions from {EVAL_PATH.name}")
    print(f"Retrieval-type subset: {len(questions)} questions "
          f"(the other {len(all_questions) - len(questions)} require agent tools)")

    print("\nConnecting to Postgres...")
    repo = PostgresCatalogRepository(PostgresConfig())
    await repo.initialize()

    cfg = RetrievalConfig()
    bm25 = BM25Retriever(repo)
    dense = DenseRetriever(repo, cfg)
    reranker = CrossEncoderReranker(cfg)

    # Config 1: Dense only
    print("\n[1/3] Running Dense-only config...")
    async def dense_only(query, top_k):
        return await dense.retrieve(query, top_k=top_k)
    dense_result = await run_config("dense_only", dense_only, questions)
    print(f"  Recall@5 = {dense_result['recall_at_5_mean']:.4f} | "
          f"MRR = {dense_result['mrr_mean']:.4f} | "
          f"p50 = {dense_result['latency_p50_ms']} ms")

    # Config 2: Hybrid (no reranker)
    print("\n[2/3] Running Hybrid (no reranker) config...")
    hybrid_no_rerank = HybridRetrievalPipeline(
        retrievers=[bm25, dense], reranker=None, config=cfg
    )
    async def hybrid_plain(query, top_k):
        return await hybrid_no_rerank.retrieve(query, top_k=top_k, skip_rerank=True)
    hybrid_result = await run_config("hybrid_no_rerank", hybrid_plain, questions)
    print(f"  Recall@5 = {hybrid_result['recall_at_5_mean']:.4f} | "
          f"MRR = {hybrid_result['mrr_mean']:.4f} | "
          f"p50 = {hybrid_result['latency_p50_ms']} ms")

    # Config 3: Hybrid + reranker
    print("\n[3/3] Running Hybrid + reranker config...")
    hybrid_full = HybridRetrievalPipeline(
        retrievers=[bm25, dense], reranker=reranker, config=cfg
    )
    async def hybrid_rerank(query, top_k):
        return await hybrid_full.retrieve(query, top_k=top_k, skip_rerank=False)
    rerank_result = await run_config("hybrid_with_rerank", hybrid_rerank, questions)
    print(f"  Recall@5 = {rerank_result['recall_at_5_mean']:.4f} | "
          f"MRR = {rerank_result['mrr_mean']:.4f} | "
          f"p50 = {rerank_result['latency_p50_ms']} ms")

    # Summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "n_questions": len(questions),
        "top_k": TOP_K,
        "configs": {
            "dense_only": {k: v for k, v in dense_result.items() if k != "details"},
            "hybrid_no_rerank": {k: v for k, v in hybrid_result.items() if k != "details"},
            "hybrid_with_rerank": {k: v for k, v in rerank_result.items() if k != "details"},
        },
        "delta_rerank_latency_p50_ms": round(
            rerank_result["latency_p50_ms"] - hybrid_result["latency_p50_ms"], 2
        ),
        "delta_rerank_latency_p95_ms": round(
            rerank_result["latency_p95_ms"] - hybrid_result["latency_p95_ms"], 2
        ),
        "delta_recall_hybrid_vs_dense": round(
            hybrid_result["recall_at_5_mean"] - dense_result["recall_at_5_mean"], 4
        ),
        "delta_recall_rerank_vs_hybrid": round(
            rerank_result["recall_at_5_mean"] - hybrid_result["recall_at_5_mean"], 4
        ),
    }

    out_path = RESULTS_DIR / f"rag_quality_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "details": {
            "dense_only": dense_result["details"],
            "hybrid_no_rerank": hybrid_result["details"],
            "hybrid_with_rerank": rerank_result["details"],
        }}, f, indent=2)

    print("\n" + "=" * 65)
    print("  SUMMARY")
    print("=" * 65)
    print(f"Dense only           : Recall@5 = {summary['configs']['dense_only']['recall_at_5_mean']:.4f} | MRR = {summary['configs']['dense_only']['mrr_mean']:.4f}")
    print(f"Hybrid (no rerank)   : Recall@5 = {summary['configs']['hybrid_no_rerank']['recall_at_5_mean']:.4f} | MRR = {summary['configs']['hybrid_no_rerank']['mrr_mean']:.4f}")
    print(f"Hybrid + rerank      : Recall@5 = {summary['configs']['hybrid_with_rerank']['recall_at_5_mean']:.4f} | MRR = {summary['configs']['hybrid_with_rerank']['mrr_mean']:.4f}")
    print(f"\nΔ Recall (hybrid vs dense)  : {summary['delta_recall_hybrid_vs_dense']:+.4f}")
    print(f"Δ Recall (rerank vs hybrid) : {summary['delta_recall_rerank_vs_hybrid']:+.4f}")
    print(f"Δ Reranker latency p50      : {summary['delta_rerank_latency_p50_ms']:+.2f} ms")
    print(f"\n💾 Saved: {out_path}")

    await repo.close()


if __name__ == "__main__":
    asyncio.run(main())
