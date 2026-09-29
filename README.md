# RoomFit Copilot — Candidate C-2474

> AI-powered furniture shopping assistant with hybrid RAG, a tool-calling
> agent, a dual-backend inference gateway, and SSE streaming.

**Status:** end-to-end pipeline working on the reference hardware.
See `docs/evidence/chat_sse_success.txt` for a captured SSE session.

---

## 0. Measured results at a glance

All numbers below come from scripts under `bench/` and are reproducible
against the running stack. Full methodology and per-config breakdown in
`docs/BENCHMARKS.md`.

| Surface | Metric | Value |
|---|---|---|
| Retrieval (hybrid BM25 + RRF) | Recall@5 / MRR (20 retrieval questions) | **1.00 / 1.00** |
| Retrieval (dense-only, hash fallback) | Recall@5 / MRR | 0.10 / 0.10 |
| Inference (FP16, 1 user) | TTFT p50 / throughput | 574 ms / 111 tok/s |
| Inference (FP8, 1 user) | TTFT p50 / throughput | **384 ms / 164 tok/s** |
| Load test (FP8, 32 concurrent) | aggregate throughput / p95 | **1746 tok/s / 349 ms** |
| Weights footprint | FP16 → FP8 | 2.98 GiB → **1.73 GiB** (-42%) |
| Cost (projected) | per 1M output tokens, on-demand RTX 5060 class | $0.677 |

Model: `Qwen/Qwen2.5-1.5B-Instruct`. Hardware: RTX 5060 8GB (Blackwell
SM120) + Ryzen 5 5600X, WSL2. The FP8 row is measured with vLLM runtime
quantization (see ADR-014).

## 1. How to run it

### Prerequisites

- Docker Engine + Docker Compose v2.
- A running LLM inference server exposing an OpenAI-compatible
  `/v1/chat/completions` endpoint with tool-calling enabled.
- Python 3.11+ (only for the seed script and benchmarks, run outside Docker).

### 1.1 Start the inference server (WSL2 / native Linux)

The gateway expects a vLLM server on `http://<host>:8001/v1`. On WSL2 the
following flags are required (see `docs/DECISIONS.md` ADR-009):

    VLLM_USE_V2_MODEL_RUNNER=0 \
    VLLM_USE_FLASHINFER_SAMPLER=0 \
    VLLM_WSL2_ENABLE_PIN_MEMORY=1 \
    python -m vllm.entrypoints.openai.api_server \
      --model Qwen/Qwen2.5-1.5B-Instruct \
      --served-model-name Qwen/Qwen2.5-1.5B-Instruct \
      --host 0.0.0.0 --port 8001 \
      --max-model-len 4096 \
      --gpu-memory-utilization 0.75 \
      --enable-auto-tool-choice \
      --tool-call-parser hermes

The `--enable-auto-tool-choice` and `--tool-call-parser hermes` flags are
mandatory — without them vLLM returns `400 Bad Request` when the agent
sends `tools` in the request payload.

### 1.2 Start the application stack

    cd infra
    docker compose up -d --build

This brings up Postgres (pgvector), Redis, and the API container. The API
reaches the vLLM host through `VLLM_URL` (defaults to the WSL2 host IP in
`infra/docker-compose.yml`; override via the environment).

Verify the API is up and the tools registered:

    curl -s http://localhost:8000/health
    docker compose -f infra/docker-compose.yml logs --tail=20 api | grep tools_registered

Expected log line:

    api.tools_registered  tools=['search_catalog', 'get_product', 'check_fit', 'compare_products']

### 1.3 Seed the catalog

The seeder is intentionally run outside the image so it can read the
`data/` directory from the host:

    docker compose -f infra/docker-compose.yml run --rm \
      -v "$PWD/scripts:/app/scripts:ro" \
      -v "$PWD/data:/app/data:ro" \
      api python /app/scripts/seed_catalog.py

Expected output ends with `Catalog successfully seeded`.

### 1.4 Query the chat endpoint

    curl -N -X POST http://localhost:8000/chat \
      -H "Content-Type: application/json" \
      -d '{"message": "find me a standing desk under 500 dollars"}'

The response is an SSE stream: `event: message` with `data: {"type":
"tool_call"|"tool_result"|"token"|"done", ...}`.

---

## 2. Tests and benchmarks

### 2.1 Anonymity verification

    bash scripts/check_anonymity.sh

### 2.2 Unit and integration tests

    pytest packages/ apps/api/tests -v

### 2.3 Benchmarks

    python3 bench/run_benchmarks.py

Measured artifacts are written to `bench/results/`. See
`docs/BENCHMARKS.md` for the interpretation and for the explicit
measured-vs-projected distinction.

**Note:** the concurrency scaling test is disabled — `asyncio.gather` does
not isolate tail latency correctly. A proper load generator (Locust, k6)
is required.

---

## 2.4 Security posture

- **Prompt injection guard.** Catalog text reaching the LLM through the
  `search_catalog` tool is filtered by a pattern-based sanitizer
  (`packages/rag_core/src/rag_core/security/prompt_guard.py`). Matches are
  replaced with a redaction marker before the content enters the model
  context. Validated end-to-end; see `docs/DECISIONS.md` ADR-010.
- **Rate limiting.** 60 requests per minute per IP, enforced by
  `apps/api/src/api/middleware/rate_limit.py`.
- **Token budget.** Per-request token accounting middleware
  (`apps/api/src/api/middleware/token_budget.py`).
- **Anonymity gate.** `scripts/check_anonymity.sh` runs in CI and fails
  the build if personal data patterns appear in the repo.

- **Prometheus metrics.** `/metrics` endpoint exposes standard HTTP
  metrics (request count, latency histograms, in-flight requests) via
  `prometheus-fastapi-instrumentator`. In the offline build environment
  the package is mounted from the host's site-packages via
  `/opt/prom-wheelhouse` (see `docs/DECISIONS.md` ADR-011). In a
  networked build, it would be a normal `pip install` dependency.

## 3. Scope cuts (48 h) and next steps (one more week)

### 3.1 Scope cuts

1. **Full client dataset ingestion.** The pipeline is built for drop-in
   replacement of `catalog.jsonl`, `catalog_updates.jsonl`, and
   `eval_questions.jsonl` under `data/`. The current run uses a
   **2050-product synthetic catalog** generated by
   `scripts/generate_dataset.py` (deterministic, seed=42), plus a
   60-question eval set and 46 catalog update events. See
   `docs/BENCHMARKS.md` Section 4 for measured retrieval quality on this
   corpus.
2. **Kubernetes deployment.** Focused on a production-grade
   `docker-compose.yml` plus a GPU override rather than Helm charts.
3. **Prefix-cache sweeps.** Implemented base vLLM configuration; deeper
   KV memory tuning is documented as future work.
4. **CPU fallback deployment.** The `llama.cpp` adapter exists and is
   unit-tested, but no CPU container is provisioned in this environment.
5. **Concurrency benchmark.** Requires a proper load generator.

### 3.2 Next steps (one more week)

1. **Complete model precision sweep.** FP16 vs AWQ 4-bit, measured on a
   dedicated GPU node, plotting latency vs throughput automatically.
2. **Semantic cache threshold calibration.** Sweep
   `semantic_similarity_threshold` from 0.85 to 0.95 against
   `eval_questions.jsonl` to compute exact false-hit rates.
3. **Prompt-injection guards.** Add an input sanitization classifier
   before retrieved catalog text is fed into the agent loop context.
4. **Automated end-to-end failover test.** Spin up Compose, kill the
   vLLM container under load, and verify zero-downtime failover to the
   CPU backend.
5. **Proper concurrency load test.** Locust or k6, measuring true tail
   latency and aggregate throughput under controlled arrival rates.

---

## 4. Architecture and decisions

- `docs/architecture/component.md` — system components (Mermaid).
- `docs/architecture/sequence_chat.md` — chat request sequence.
- `docs/architecture/class_inference_gateway.md` — gateway class diagram.
- `docs/architecture/class_rag_core.md` — RAG core class diagram.
- `docs/architecture/patterns.md` — the 8 design patterns with code pointers.

- `docs/DECISIONS.md` — 9 ADRs (including the WSL2 workarounds).
- `docs/BENCHMARKS.md` — measured vs projected metrics.
- `docs/AI_USAGE.md` — AI assistant usage disclosure.

---

## 5. Hardware and environment

- **CPU:** AMD Ryzen 5 5600X (6C/12T)
- **RAM:** 32 GB DDR4
- **GPU:** NVIDIA GeForce RTX 5060, 8 GB GDDR7, Blackwell SM120, CUDA 13.4
- **OS:** Ubuntu 22.04 on WSL2
- **Runtime:** vLLM 0.29.0, Qwen2.5-1.5B-Instruct (bfloat16)

`bench/hardware.json` captures the same information programmatically.
