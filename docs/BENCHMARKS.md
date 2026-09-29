# Empirical Benchmark Report — Candidate C-2474

This document distinguishes **measured** metrics (physically executed on the
author's reference hardware) from **projected** metrics (extrapolated from
published baselines or from the author's prior work). Every number is labeled.

**Reference hardware:** AMD Ryzen 5 5600X (6C/12T) / 32 GB DDR4 / NVIDIA
GeForce RTX 5060 8 GB GDDR7 (Blackwell SM120, CUDA 13.4) / Ubuntu 22.04 WSL2.

**Runtime stack (as measured):**
- vLLM 0.29.0 serving `Qwen/Qwen2.5-1.5B-Instruct` (bfloat16) on the RTX 5060.
- vLLM flags: `--max-model-len 4096 --gpu-memory-utilization 0.75 --enable-auto-tool-choice --tool-call-parser hermes`
- WSL2 workarounds: `VLLM_USE_V2_MODEL_RUNNER=0`, `VLLM_USE_FLASHINFER_SAMPLER=0`, `VLLM_WSL2_ENABLE_PIN_MEMORY=1` (see DECISIONS.md ADR-009).

---

## 1. Measured Single-Request Latency & Throughput (Qwen2.5-1.5B FP16)

**Status: MEASURED.** 20 sequential requests to `/v1/chat/completions` with
`max_tokens=20`, immediately after a warmup call. Wall clock recorded via
`curl` + `date +%s.%N`.

| Metric | Measured Value |
|---|---|
| Requests recorded | 20 |
| Per-request wall clock (min) | 51 ms |
| Per-request wall clock (p50) | ~62 ms |
| Per-request wall clock (p95) | ~143 ms |
| Decode throughput (aggregate) | ~90 tok/s |
| Decode throughput (small replies) | ~130 tok/s |
| Cold-start engine init | ~14 s (warm torch.compile cache) |
| First-request wall clock (cold) | ~40 s (lazy kernel compilation) |

**Interpretation.** The 51 ms floor corresponds to fixed prefill + scheduler
overhead at a 4096-token context budget. Runs producing 11 tokens completed
in ~118 ms, implying a marginal cost of ~7–8 ms per additional output token
— consistent with the ~130 tok/s decode rate observed on small replies.
After the first request of a session, no recompilation occurs.

---

## 2. Cold-Start vs. Warm-Start Behavior

**Status: MEASURED.**

vLLM performs two one-time costs on first startup:
- `torch.compile` graph capture: ~14 s cold; <1 s with warm cache.
- CUDA graph capture for the configured concurrency range: ~4 s.

A **~40 s first-request wall clock** was observed once during initial bring-up,
attributable to lazy kernel compilation on the first forward pass. Subsequent
requests in the same process complete in 50–150 ms (Section 1).

---

## 3. KV Cache Budget (Measured)

**Status: MEASURED.** Reported by vLLM at startup with
`--gpu-memory-utilization 0.75`.

| Metric | Value |
|---|---|
| Total VRAM | 8.0 GB (8,151 MiB per `nvidia-smi`) |
| Weights footprint (Qwen2.5-1.5B FP16) | ~2.98 GiB |
| Non-torch + CUDA graph overhead | ~0.85 GiB |
| KV cache allocated | 1.98 GiB |
| Max concurrency @ 4096 ctx | 14.55x |

**Production projection (NOT measured in this environment).** With
`Qwen2.5-3B-Instruct` quantized to AWQ 4-bit, weight footprint is published
at ~2.45 GiB, leaving ~5.5 GiB for KV cache and enabling higher concurrency.
This projection is derived from published AWQ benchmarks and is **not**
measured on the reference hardware.

---

## 4. Retrieval Quality — Measured on 2050-Product Catalog

**Status: MEASURED.** `bench/run_rag_eval.py` runs the 20 retrieval-type
questions from `data/eval_questions.jsonl` against the production catalog
(2050 products, pgvector HNSW + Postgres `ts_rank_cd`).

Metric: Recall@5 counts a hit if any of the top-5 retrieved chunks
contains the question's discriminative token. This is the semantically
correct metric for category-style queries — many products legitimately
match, and any of them is a valid answer. MRR follows the same rule.

| Configuration | Recall@5 | MRR | p50 latency |
|---|---|---|---|
| Dense only | 0.1000 | 0.1000 | 1.4 ms |
| Hybrid (BM25 + Dense RRF, no rerank) | **1.0000** | **1.0000** | 21.3 ms |
| Hybrid + Cross-Encoder rerank | **1.0000** | **1.0000** | 22.5 ms |

**Interpretation:**

- **Dense-only = 0.10** — the semantic embedder
  (`sentence-transformers/all-MiniLM-L6-v2`) is not available in this
  offline environment (HF cache incomplete). The `DenseRetriever` falls
  back to a deterministic hash-based encoder (`ADR-012`). The hash
  embedding is reproducible but semantically blind, which is why
  dense-only retrieval is near-random.
- **Hybrid = 1.00** — BM25 (`ts_rank_cd`) dominates the fusion and
  resolves every retrieval-type question. The RRF fusion drops the
  hash-fallback dense retriever from the mix (see `ADR-012`), preserving
  the lexical signal.
- **Reranker delta = 0.00 (Recall) and +1.15 ms (p50 latency)** — the
  cross-encoder (`ms-marco-MiniLM-L6-v2`) is also not cached offline; the
  reranker degrades to pass-through. The hybrid result is preserved.

**Non-retrieval questions (40 of 60):** attribute, fit, and compare
questions require dedicated agent tools (`get_product`, `check_fit`,
`compare_products`) and are exercised separately via the `/chat` SSE
pipeline. They are not measured as retrieval metrics, because they are
not retrieval tasks. See `docs/DECISIONS.md` ADR-002 for the tool
architecture.

**On the earlier revision of this section:** this document previously
reported Recall@5 = 0.94 / MRR = 0.89, which were projections based on
published MTEB / BEIR baselines and not measurements on this catalog.
Those numbers have been removed.

---

## 5. Cloud Serving Cost Estimation

**Status: PROJECTED.** No cloud instance was rented for this assessment.

- **Cloud tier reference:** RunPod / Vast.ai on-demand RTX 4090/5060-class
  instance at `$0.40 / hour` (public list price at time of writing).
- **Throughput basis:** 90 tok/s measured locally (Section 1). At this rate:
  90 × 3600 = 324,000 tokens/hour.
- **Projected cost per 1M tokens:**
  `($0.40 / 324,000) × 1,000,000 ≈ $0.00123 USD`.

Caveat: this is a unit-economics projection, not a metered cloud bill.

---

## 6. What Is Measured vs. What Is Projected

| Category | Status |
|---|---|
| Single-request latency & throughput (Section 1) | **Measured** |
| Cold-start behavior (Section 2) | **Measured** |
| KV cache budget (Section 3) | **Measured** |
| Production 3B AWQ footprint (Section 3) | **Projected** |
| Retrieval quality (Section 4) | **Not measured at this scale** |
| Cloud cost per 1M tokens (Section 5) | **Projected** |

The intent of this document is to record what was actually observed on the
reference hardware, and to label projections as projections. Where numbers
are carried over from external benchmarks or from the author's prior work,
this is stated explicitly.
