#!/usr/bin/env python3
"""
Semantic cache threshold calibration.

Sweeps semantic similarity thresholds and measures the false-hit rate at
each level using a controlled probe set:

  - TRUE POSITIVE probes: pairs of queries that are paraphrases of each
    other and should hit the semantic cache.
  - FALSE POSITIVE probes: pairs of queries that are semantically distinct
    and should NOT hit the semantic cache.

For each threshold, this script reports:
  - hit_rate_on_paraphrases   (higher is better)
  - false_hit_rate            (lower is better)

The chosen threshold is the lowest one that keeps false_hit_rate at 0
while maximizing hit_rate_on_paraphrases.

Usage:
    docker compose -f infra/docker-compose.yml run --rm \\
      -v "$PWD/bench:/app/bench" \\
      api python /app/bench/run_semantic_cache_calibration.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "/app/packages/rag_core/src")

from rag_core.config import RedisConfig

RESULTS_DIR = Path("/app/bench/results")
RESULTS_DIR.mkdir(exist_ok=True)


# --- Probe sets ------------------------------------------------------------

PARAPHRASE_PAIRS = [
    ("standing desk under 500 dollars", "adjustable desk cheaper than $500"),
    ("cheapest sofa in stock", "lowest price sofa available now"),
    ("ergonomic office chair", "office chair with lumbar support"),
    ("wood dining table for six", "six-person wooden dining table"),
    ("modern floor lamp adjustable arm", "contemporary arc floor lamp"),
    ("queen platform bed with storage", "storage bed frame queen size"),
    ("marble coffee table round", "circular marble coffee table"),
    ("persian area rug 8x10", "8 by 10 persian rug"),
    ("industrial bookshelf metal wood", "metal-and-wood bookshelf industrial"),
    ("minimalist scandinavian dining chair", "scandinavian dining chair minimalist"),
]

DISTINCT_PAIRS = [
    ("standing desk under 500 dollars", "cheapest sofa in stock"),
    ("ergonomic office chair", "marble coffee table round"),
    ("wood dining table for six", "persian area rug 8x10"),
    ("modern floor lamp adjustable arm", "queen platform bed with storage"),
    ("industrial bookshelf metal wood", "minimalist scandinavian dining chair"),
    ("standing desk under 500 dollars", "persian area rug 8x10"),
    ("ergonomic office chair", "industrial bookshelf metal wood"),
    ("marble coffee table round", "queen platform bed with storage"),
    ("modern floor lamp adjustable arm", "wood dining table for six"),
    ("cheapest sofa in stock", "minimalist scandinavian dining chair"),
]


def cosine(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def hash_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic hash embed — MUST match scripts/seed_catalog.py."""
    import random
    import math
    rng = random.Random(text)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


async def main():
    print("=" * 65)
    print("  Semantic Cache Threshold Calibration")
    print("=" * 65)

    cfg = RedisConfig()
    print(f"\nCurrent configured threshold: {cfg.semantic_similarity_threshold}")
    print(f"Embedding mode: hash-fallback (semantic embedder not cached offline)")
    print(f"  -> paraphrase pairs will NOT be similar in hash space;")
    print(f"     this calibration demonstrates the *methodology*, and the")
    print(f"     measured false-hit rate reflects the hash fallback, not")
    print(f"     the production semantic embedder.\n")

    # Compute similarity for each pair
    para_sims = []
    for q1, q2 in PARAPHRASE_PAIRS:
        v1 = hash_embed(q1)
        v2 = hash_embed(q2)
        para_sims.append(cosine(v1, v2))

    distinct_sims = []
    for q1, q2 in DISTINCT_PAIRS:
        v1 = hash_embed(q1)
        v2 = hash_embed(q2)
        distinct_sims.append(cosine(v1, v2))

    print(f"Paraphrase pair similarities: mean={sum(para_sims)/len(para_sims):.4f}, "
          f"max={max(para_sims):.4f}, min={min(para_sims):.4f}")
    print(f"Distinct pair similarities:   mean={sum(distinct_sims)/len(distinct_sims):.4f}, "
          f"max={max(distinct_sims):.4f}, min={min(distinct_sims):.4f}")
    print()

    thresholds = [0.70, 0.75, 0.80, 0.85, 0.88, 0.90, 0.92, 0.94, 0.95]
    results = []

    for t in thresholds:
        hits_para = sum(1 for s in para_sims if s >= t)
        hits_distinct = sum(1 for s in distinct_sims if s >= t)
        hit_rate = hits_para / len(para_sims)
        false_hit_rate = hits_distinct / len(distinct_sims)

        results.append({
            "threshold": t,
            "hit_rate_on_paraphrases": round(hit_rate, 4),
            "false_hit_rate": round(false_hit_rate, 4),
            "true_positives": hits_para,
            "false_positives": hits_distinct,
            "n_paraphrase_pairs": len(para_sims),
            "n_distinct_pairs": len(distinct_sims),
        })

        print(f"  threshold={t:.2f}  hit_rate={hit_rate:.3f}  "
              f"false_hit_rate={false_hit_rate:.3f}  "
              f"(TP={hits_para}/{len(para_sims)}, FP={hits_distinct}/{len(distinct_sims)})")

    # Recommend: lowest threshold with FP=0 and highest hit rate
    zero_fp = [r for r in results if r["false_hit_rate"] == 0.0]
    if zero_fp:
        best = max(zero_fp, key=lambda r: r["hit_rate_on_paraphrases"])
    else:
        # Fall back: highest threshold
        best = max(results, key=lambda r: r["threshold"])

    print()
    print(f"Recommended threshold: {best['threshold']:.2f}")
    print(f"  hit_rate_on_paraphrases = {best['hit_rate_on_paraphrases']:.4f}")
    print(f"  false_hit_rate          = {best['false_hit_rate']:.4f}")

    summary = {
        "timestamp": datetime.now().isoformat(),
        "embedding_mode": "hash-fallback",
        "note": (
            "Semantic embedder is not available offline. The measured "
            "distances reflect the hash fallback used by DenseRetriever "
            "and SemanticCache in this environment. The calibration "
            "methodology is what matters: a production deployment with "
            "the semantic embedder would re-run this same sweep to pick "
            "a threshold from data."
        ),
        "n_paraphrase_pairs": len(para_sims),
        "n_distinct_pairs": len(distinct_sims),
        "sweep": results,
        "recommended_threshold": best["threshold"],
    }

    out = RESULTS_DIR / f"semantic_cache_calibration_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n💾 Saved: {out}")


if __name__ == "__main__":
    asyncio.run(main())
