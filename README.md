# RoomFit Copilot — Candidate C-XXXX

> AI-powered furniture shopping assistant with hybrid RAG, tool-calling agent, dual-backend inference gateway, and SSE streaming UI.

## 1. How to run it in under five commands, CPU and GPU

### CPU Path (End-to-End)
```bash
cp .env.example .env
docker compose up --build -d
python3 scripts/seed_catalog.py
```

### GPU Path (NVIDIA CUDA Override)
```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
```

### Local Development Mode (FakeBackend)
```bash
pip install -e packages/inference_gateway -e packages/rag_core -e apps/api
uvicorn api.main:app --app-dir apps/api/src --reload --port 8000
```

## 2. How to run the tests and the benchmarks

### Anonymity Verification
```bash
bash scripts/check_anonymity.sh
```

### Run Unit and Integration Tests
```bash
pytest packages/ apps/api/tests -v
```

### Run Benchmark Suite
```bash
python3 bench/run_benchmarks.py
```

*Raw benchmark outputs are saved as JSON files in bench/results/.*

## 3. What you cut because of the 48 hours, and what you would do next with one more week

### Scope Cuts (48 Hours)
1. **Full Client Dataset Ingestion**: Built for drop-in replacement of catalog.jsonl, catalog_updates.jsonl, and eval_questions.jsonl under data/. The smoke suite uses a 10-item representative sample.
2. **Kubernetes Deployment**: Focused on production-grade docker-compose.yml and docker-compose.gpu.yml rather than Helm charts or K8s manifests.
3. **Advanced Prefix Caching Sweeps**: Implemented base vLLM configurations; KV memory share and prefix caching tuning documented in DECISIONS.md.

### Next Steps (One More Week)
1. **Complete Model Precision Sweep**: Run automated FP16 vs AWQ 4-bit benchmarks directly on dedicated cloud GPU nodes (Lambda/Vast.ai) and auto-plot latency vs throughput.
2. **Dynamic Semantic Threshold Calibration**: Perform an exhaustive sweep over eval_questions.jsonl to calculate exact false-hit rates for semantic cache thresholds between 0.85 and 0.95.
3. **Enhanced Prompt Injection Guards**: Add input sanitization classifiers before feeding retrieved catalog text into the agent loop context.
4. **Automated End-to-End Failover Integration Test**: Expand CI to spin up Docker Compose, simulate vLLM container termination under load, and verify llama.cpp zero-downtime failover automatically.
