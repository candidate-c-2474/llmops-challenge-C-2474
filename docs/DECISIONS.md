# Architecture Decisions — Candidate C-2474

Format: Decision / Options Considered / Rationale / Status.

**Status legend:**
- **MEASURED** — verified on the reference hardware.
- **DEPLOYED** — implementation is in the repo and running.
- **PROJECTED** — derived from published benchmarks or future work.

---

## ADR-001: Model Selection — Qwen2.5-1.5B FP16 (Demo) → Qwen2.5-3B AWQ (Production Target)

**Decision (deployed):** Serve `Qwen/Qwen2.5-1.5B-Instruct` in bfloat16 for
this assessment demo.

**Decision (production target, not deployed here):** Migrate to
`Qwen2.5-3B-Instruct` quantized to AWQ 4-bit once a dedicated GPU node is
available.

**Options considered:**
- Qwen2.5-1.5B FP16 — **chosen for the demo**.
- Qwen2.5-3B AWQ 4-bit — **production target**.
- Llama-3.1-8B FP16 — rejected (does not fit 8 GB VRAM at FP16 with usable KV cache).

**Rationale:**
- The 1.5B FP16 model was **already present in the local HuggingFace cache**
  and could be served with **zero network download** — critical given the
  development environment's intermittent 4G connectivity.
- The production target (3B AWQ) drops weight footprint from ~2.98 GiB to
  ~2.45 GiB, freeing ~5.5 GiB for KV cache — a projection based on published
  AWQ results, **not measured in this environment**.
- See `docs/BENCHMARKS.md` Section 3 for the measured KV budget under the
  current demo configuration.

**Status:** 1.5B FP16 **MEASURED**; 3B AWQ **PROJECTED**.

---

## ADR-002: Dual Inference Backend Strategy

**Decision:** vLLM on GPU as primary backend. The gateway is designed to
accept a secondary CPU fallback (llama.cpp) via the same `InferenceBackend`
interface, activated by a `CircuitBreaker` after 3 consecutive failures.

**Options considered:**
- Single GPU backend only — rejected (assessment requires a failover path).
- Cloud LLM API provider — rejected (sovereignty / latency / cost).
- vLLM primary + llama.cpp fallback via `Strategy` + `Adapter` patterns — **chosen**.

**Rationale:**
- The `InferenceBackend` ABC (`interfaces.py`) allows swapping backends
  without touching the agent loop or routes.
- `CircuitBreaker` (`circuit_breaker.py`) transitions CLOSED → OPEN after
  3 failures, then HALF_OPEN after 30 s, with a single test request.
- `MetricsBackend` + `RetryBackend` decorators wrap both backends without
  modifying their code.

**Deployment note:** In the current development environment only the vLLM
backend is deployed. The llama.cpp adapter exists
(`llamacpp_backend.py`) and is unit-tested, but no CPU container is
provisioned. The fallback path is validated in tests with `FakeBackend`.

**Status:** vLLM primary **DEPLOYED**; llama.cpp fallback **IMPLEMENTED,
NOT DEPLOYED**.

---

## ADR-003: Hybrid Retrieval Pipeline

**Decision:** Combine lexical search (Postgres `ts_rank_cd` full-text) and
dense vector retrieval (pgvector HNSW), fused via Reciprocal Rank Fusion
(k=60), with an optional Cross-Encoder rerank stage.

**Options considered:**
- Dense-only vector search — rejected (misses exact SKU/ID queries).
- BM25-only lexical search — rejected (misses semantic queries).
- Hybrid with RRF, no reranker — **deployed**.
- Hybrid + Cross-Encoder rerank — **implemented, degrades gracefully**.

**Rationale:**
- The `HybridRetrievalPipeline` runs both retrievers concurrently via
  `asyncio.gather`, then fuses with RRF.
- The Cross-Encoder reranker (`cross-encoder/ms-marco-MiniLM-L6-v2`) is
  loaded lazily on first use. In the current environment the model is **not
  in the local HF cache** and the network is offline; the reranker catches
  the load exception and degrades to **pass-through ordering**, preserving
  the RRF ranking.
- Retrieval quality metrics are **not measured at this scale** — the smoke
  catalog contains 10 products. A full evaluation requires the production
  catalog (~2000 products) and `eval_questions.jsonl`. See
  `docs/BENCHMARKS.md` Section 4.

**Status:** Hybrid RRF **DEPLOYED**; reranker **IMPLEMENTED, DEGRADES
GRACEFULLY**; quality metrics **NOT MEASURED**.

---

## ADR-004: Two-Layer Response Caching

**Decision:** Exact-match cache (SHA-256 of canonical query) + semantic
cache (embedding cosine ≥ 0.92) on Redis.

**Options considered:**
- TTL-only single-layer string cache — rejected (no semantic dedup).
- Two-layer (exact + semantic) — **chosen**.

**Rationale:**
- Exact cache serves near-duplicate queries at sub-millisecond Redis latency.
- Semantic cache catches paraphrases with cosine similarity above the
  configured threshold (`semantic_similarity_threshold: 0.92` in `config.py`).
- The threshold is a deployment-time tuning knob, not a hardcoded constant.

**Status:** **DEPLOYED**.

---

## ADR-005: Observer Pattern for Cache Invalidation

**Decision:** Event-driven cache invalidation via `CatalogEventBus` +
`CacheInvalidator` observer.

**Options considered:**
- TTL expiration only — rejected (leaves stale prices visible for up to 1 h).
- Global cache flush on any catalog update — rejected (thundering herd,
  zero hit rate during refill).
- Per-product surgical invalidation via observer — **chosen**.

**Rationale:**
- `POST /admin/catalog/apply-updates` publishes a `CatalogUpdate` event.
- The observer walks the affected `product_ids` and purges only matching
  cache entries.
- `PRODUCT_CREATED` events are intentionally no-ops — no cache entry can
  exist for an ID that was just created.
- This pattern was chosen after rejecting a naive AI-generated
  `FLUSHDB`-on-every-event proposal (documented in `AI_USAGE.md`).

**Status:** **DEPLOYED**.

---

## ADR-006: Repository Pattern for Catalog Access

**Decision:** Abstract `CatalogRepository` interface with
`PostgresCatalogRepository` and `InMemoryCatalogRepository` implementations.

**Options considered:**
- Direct SQL from agent tools — rejected (zero test isolation).
- ORM calls embedded in tools — rejected (same problem, plus ORM weight).
- Repository abstraction — **chosen**.

**Rationale:**
- Enables 100% of unit tests to run in under 0.5 s with no live Postgres.
- `InMemoryCatalogRepository` is used in `test_tools.py`.

**Status:** **DEPLOYED**.

---

## ADR-007: Agent Tool-Calling Execution Cap

**Decision:** Hard cap of 4 tool-calling rounds per user question in
`AgentLoop`.

**Options considered:**
- Unbounded iterative tool calling — rejected (infinite-loop risk, token
  budget exhaustion).
- Single tool call per question — rejected (insufficient for compare-then-fit
  workflows).
- Fixed cap of 4 rounds — **chosen**.

**Rationale:**
- Prevents runaway loops.
- Allows multi-step reasoning: search → get → check_fit → compare.
- The cap is a configuration value in `AgentConfig.max_tool_rounds`.

**Status:** **DEPLOYED**.

---

## ADR-008: Monorepo Package Isolation

**Decision:** `packages/inference_gateway` and `packages/rag_core` are
independent installable packages with their own `pyproject.toml`. Neither
imports from `apps/`.

**Options considered:**
- Single monolithic codebase — rejected (violates dependency direction).
- Published to PyPI — rejected (overkill for the assessment).
- Independent local packages via `pip install -e` — **chosen**.

**Rationale:**
- Enforces dependency direction: `apps/api` depends on `packages/*`, never
  the reverse.
- Enables running `rag_core` tests without the inference gateway installed,
  and vice-versa.

**Status:** **DEPLOYED**.

---

## ADR-009: WSL2 Platform Workarounds for vLLM

**Decision:** Run vLLM with three environment flags on WSL2:
`VLLM_USE_V2_MODEL_RUNNER=0`, `VLLM_USE_FLASHINFER_SAMPLER=0`,
`VLLM_WSL2_ENABLE_PIN_MEMORY=1`.

**Options considered:**
- Run vLLM on native Linux — not available in this environment.
- Run vLLM on Windows — no GPU passthrough for vLLM's CUDA stack.
- WSL2 with the three flags above — **chosen**.

**Rationale (each flag addresses a distinct platform limitation):**

1. **`VLLM_USE_V2_MODEL_RUNNER=0`** — WSL2 does not expose UVA (Unified
   Virtual Addressing). vLLM's V2 runner requires UVA for its staging
   buffers; forcing the V1 runner bypasses the requirement. Without this
   flag, the engine aborts with `RuntimeError: UVA is not available`.

2. **`VLLM_USE_FLASHINFER_SAMPLER=0`** — FlashInfer compiles sampling
   kernels via NVRTC / nvcc at runtime. The container does not ship nvcc.
   Disabling the FlashInfer sampler forces the native PyTorch sampler,
   which is pre-compiled. Without this flag, the engine aborts with
   `RuntimeError: Could not find nvcc`.

3. **`VLLM_WSL2_ENABLE_PIN_MEMORY=1`** — Pinned host memory is opt-in on
   WSL2 (it is disabled by default for compatibility). Enabling it
   stabilizes the CPU↔GPU copy path used by the gateway.

**Trade-offs:**
- V1 runner + native sampler may lose some throughput versus a fully
  optimized native-Linux deployment. This is **the price of running on
  WSL2**; on a dedicated Linux node these flags would not be needed.
- **These flags are the environment adaptation, not the architecture.**
  The `InferenceBackend` interface is unchanged.

**Status:** **DEPLOYED** (required for vLLM to run on WSL2).
