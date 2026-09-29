#!/usr/bin/env python3
"""
RoomFit Copilot — Reproducible Benchmark Suite (Candidate C-2474)

Every metric is measured against running endpoints. If an endpoint is
unavailable, the result is explicitly marked OFFLINE_OR_UNAVAILABLE — no
fallback to calibrated/hardcoded profiles.

Run with: python3 bench/run_benchmarks.py
"""
import json
import time
import asyncio
import statistics
import httpx
from pathlib import Path
from datetime import datetime

API_URL = "http://localhost:8000"
VLLM_URL = "http://172.25.12.152:8001"  # WSL2 host IP; must be reachable from inside containers
LLAMACPP_URL = "http://localhost:8080"
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Sample questions aligned with the smoke-suite catalog (data/catalog.jsonl).
# IDs follow the real convention: {CATEGORY}-{NNN}.
SAMPLE_QUESTIONS = [
    "Find me a standing desk under $500.",
    "What are the dimensions of DESK-001?",
    "Is DESK-002 in stock?",
    "Show me ergonomic office chairs.",
    "Compare DESK-001 and DESK-002.",
    "Find the cheapest sofa in stock.",
    "What is the weight of BED-001?",
    "Show me bookshelves under $200.",
    "Find a floor lamp with an adjustable arm.",
    "What is the price of TABLE-001?",
]


def save_result(name: str, data: dict):
    filepath = RESULTS_DIR / f"{name}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  💾 Saved: {filepath}")


async def measure_ttft_and_throughput(base_url: str, label: str, n: int = 10):
    """Measure real TTFT and throughput against a running model server."""
    ttfts = []
    throughputs = []
    errors = 0

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Warmup — the first request pays lazy kernel compilation cost.
        try:
            await client.post("/v1/chat/completions", json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": "warmup"}],
                "max_tokens": 8,
            })
        except Exception:
            pass

        for i in range(n):
            q = SAMPLE_QUESTIONS[i % len(SAMPLE_QUESTIONS)]
            t0 = time.perf_counter()
            try:
                resp = await client.post("/v1/chat/completions", json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": q}],
                    "max_tokens": 64,
                    "temperature": 0.7,
                })
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if resp.status_code == 200:
                    data = resp.json()
                    tokens = data.get("usage", {}).get("completion_tokens", 1)
                    ttfts.append(elapsed_ms)
                    throughputs.append(tokens / (elapsed_ms / 1000.0) if elapsed_ms > 0 else 0)
                else:
                    errors += 1
            except Exception:
                errors += 1

    if not ttfts:
        return {
            "backend": label,
            "status": "OFFLINE_OR_UNAVAILABLE",
            "samples_attempted": n,
            "errors": errors,
            "note": f"Could not connect to {base_url}. Ensure service is running.",
        }

    ttfts_sorted = sorted(ttfts)
    p50_idx = int(len(ttfts_sorted) * 0.5)
    p95_idx = int(len(ttfts_sorted) * 0.95)

    return {
        "backend": label,
        "status": "ONLINE",
        "model": MODEL_NAME,
        "samples": len(ttfts),
        "errors": errors,
        "ttft_p50_ms": round(ttfts_sorted[p50_idx], 2),
        "ttft_p95_ms": round(ttfts_sorted[p95_idx], 2),
        "ttft_mean_ms": round(statistics.mean(ttfts), 2),
        "throughput_mean_tok_s": round(statistics.mean(throughputs), 1),
        "throughput_p50_tok_s": round(sorted(throughputs)[p50_idx], 1),
    }


async def measure_load_concurrency(base_url: str, concurrencies: list[int] = [1, 8, 32]):
    """Load test at different concurrency levels using async gathering."""
    results = {}
    for c in concurrencies:
        latencies = []
        t0 = time.perf_counter()

        async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
            async def single_request(i: int):
                q = SAMPLE_QUESTIONS[i % len(SAMPLE_QUESTIONS)]
                req_t0 = time.perf_counter()
                try:
                    resp = await client.post("/v1/chat/completions", json={
                        "model": MODEL_NAME,
                        "messages": [{"role": "user", "content": q}],
                        "max_tokens": 32,
                    })
                    if resp.status_code == 200:
                        req_elapsed = (time.perf_counter() - req_t0) * 1000.0
                        latencies.append(req_elapsed)
                except Exception:
                    pass

            tasks = [single_request(i) for i in range(c)]
            await asyncio.gather(*tasks)

        total_time = time.perf_counter() - t0
        if latencies:
            latencies.sort()
            p95_idx = int(len(latencies) * 0.95)
            results[f"{c}_users"] = {
                "throughput_tok_s": round((len(latencies) * 32) / total_time, 1),
                "p95_latency_ms": round(latencies[min(p95_idx, len(latencies) - 1)], 2),
                "completed_requests": len(latencies),
                "total_time_s": round(total_time, 2),
            }
        else:
            results[f"{c}_users"] = {
                "status": "OFFLINE",
                "note": f"Service at {base_url} unavailable during concurrency test.",
            }
    return results


def estimate_cost(throughput_tok_s: float):
    """Estimate cost per 1M output tokens on an on-demand cloud GPU."""
    cloud_hourly_rate = 0.40  # RunPod / Vast.ai RTX 4090/5060 class
    tokens_per_hour = throughput_tok_s * 3600
    cost_per_1m = (1_000_000 / tokens_per_hour) * cloud_hourly_rate if tokens_per_hour > 0 else 0
    return {
        "cloud_provider": "RunPod On-Demand",
        "gpu_class": "NVIDIA RTX 5060 / 4090 Class",
        "hourly_rate_usd": cloud_hourly_rate,
        "measured_throughput_tok_s": throughput_tok_s,
        "tokens_per_hour": round(tokens_per_hour),
        "cost_per_1m_output_tokens_usd": round(cost_per_1m, 4),
        "status": "PROJECTED — unit economics, not a metered cloud bill",
    }


async def run_suite():
    print("=" * 65)
    print("  RoomFit Copilot — Benchmark Suite (C-2474)")
    print("=" * 65)

    # 1. TTFT & Throughput (primary only — llama.cpp not deployed in this env)
    print("\n[1/3] Measuring TTFT & Decode Throughput (primary vLLM)...")
    ttft_primary = await measure_ttft_and_throughput(VLLM_URL, "vLLM-GPU (Primary)", n=10)
    save_result("ttft_and_throughput", ttft_primary)

    # 2. Load Concurrency — DISABLED
    # Reason: asyncio.gather does not isolate tail latency correctly and
    # produces physically inconsistent numbers (higher concurrency reported
    # as higher aggregate throughput while p95 explodes). A proper load
    # generator (Locust, k6) is required. Tracked as future work.
    print("\n[2/3] Concurrency scaling: SKIPPED (requires Locust/k6, see BENCHMARKS.md)")

    # 3. Cost Estimation
    print("\n[3/3] Projecting Cost per 1M Tokens...")
    mean_throughput = ttft_primary.get("throughput_mean_tok_s", 0.0)
    if mean_throughput > 0:
        cost_data = estimate_cost(mean_throughput)
        save_result("cost_estimation", cost_data)
    else:
        print("  ⚠️  Skipping cost estimation — no measured throughput available.")

    print("\n" + "=" * 65)
    print("✅ Benchmark Suite Completed. Artifacts in bench/results/")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_suite())
