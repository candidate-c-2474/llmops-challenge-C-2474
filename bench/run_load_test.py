#!/usr/bin/env python3
"""
Load test at concurrency levels 1, 8, 32.

Methodology:
  - For each concurrency level C, run N=5 independent rounds.
  - Each round launches C concurrent requests in parallel via asyncio.gather.
  - Each request asks for 32 output tokens.
  - Record wall-clock latency per request.
  - Aggregate throughput = (total output tokens across the round) / (round wall-clock).
  - p50/p95 computed across all requests at that concurrency level.
  - 2s cool-down between rounds and 5s between concurrency levels to avoid
    cross-round KV cache contention.

The previous version of this test measured 32-user throughput higher than
1-user and p95 lower than 8-user, which is physically impossible. The
root cause was measuring a single async batch without per-request timing.

Run:
    python3 bench/run_load_test.py
or inside the container:
    docker compose -f infra/docker-compose.yml run --rm \\
      -v "$PWD/bench:/app/bench" \\
      api python /app/bench/run_load_test.py
"""
from __future__ import annotations

import asyncio
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

import httpx

VLLM_URL = "http://172.25.12.152:8001"
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CONCURRENCY_LEVELS = [1, 8, 32]
ROUNDS_PER_LEVEL = 5
MAX_TOKENS = 32
COOLDOWN_BETWEEN_ROUNDS_S = 2.0
COOLDOWN_BETWEEN_LEVELS_S = 5.0

PROMPT = "Say a short sentence about furniture."


async def one_request(client: httpx.AsyncClient, request_id: int) -> dict:
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": PROMPT}],
                "max_tokens": MAX_TOKENS,
                "temperature": 0.7,
            },
            timeout=60.0,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}", "latency_ms": elapsed_ms}
        data = resp.json()
        completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
        return {
            "ok": True,
            "latency_ms": elapsed_ms,
            "completion_tokens": completion_tokens,
            "request_id": request_id,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
        }


async def one_round(concurrency: int, round_idx: int) -> dict:
    async with httpx.AsyncClient(base_url=VLLM_URL) as client:
        t0 = time.perf_counter()
        results = await asyncio.gather(
            *[one_request(client, i) for i in range(concurrency)]
        )
        round_wall_s = time.perf_counter() - t0

    latencies = [r["latency_ms"] for r in results if r["ok"]]
    total_tokens = sum(r.get("completion_tokens", 0) for r in results if r["ok"])
    errors = sum(1 for r in results if not r["ok"])
    throughput = total_tokens / round_wall_s if round_wall_s > 0 else 0.0

    return {
        "concurrency": concurrency,
        "round": round_idx,
        "n_requests": concurrency,
        "n_ok": len(latencies),
        "errors": errors,
        "round_wall_s": round(round_wall_s, 3),
        "total_completion_tokens": total_tokens,
        "aggregate_throughput_tok_s": round(throughput, 2),
        "latency_p50_ms": round(statistics.median(latencies), 2) if latencies else None,
        "latency_p95_ms": round(
            sorted(latencies)[int(len(latencies) * 0.95)], 2
        ) if latencies else None,
        "latency_mean_ms": round(statistics.mean(latencies), 2) if latencies else None,
    }


async def main():
    print("=" * 65)
    print("  RoomFit Copilot — Load Test (concurrency 1, 8, 32)")
    print("=" * 65)
    print(f"Model: {MODEL}")
    print(f"max_tokens per request: {MAX_TOKENS}")
    print(f"Rounds per level: {ROUNDS_PER_LEVEL}")
    print(f"Levels: {CONCURRENCY_LEVELS}")

    # Warmup
    print("\nWarmup...")
    async with httpx.AsyncClient(base_url=VLLM_URL) as client:
        await one_request(client, -1)

    all_rounds = []
    summary_by_level = {}

    for c in CONCURRENCY_LEVELS:
        print(f"\n[concurrency={c}]")
        level_rounds = []
        for r in range(ROUNDS_PER_LEVEL):
            result = await one_round(c, r)
            level_rounds.append(result)
            all_rounds.append(result)
            print(
                f"  round {r+1}: wall={result['round_wall_s']:>6}s  "
                f"tok={result['total_completion_tokens']:>4}  "
                f"agg={result['aggregate_throughput_tok_s']:>7} tok/s  "
                f"p50={result['latency_p50_ms']}ms  "
                f"p95={result['latency_p95_ms']}ms  "
                f"err={result['errors']}"
            )
            await asyncio.sleep(COOLDOWN_BETWEEN_ROUNDS_S)

        # Summary across the level
        agg_throughputs = [r["aggregate_throughput_tok_s"] for r in level_rounds if r["n_ok"] > 0]
        p50s = [r["latency_p50_ms"] for r in level_rounds if r["latency_p50_ms"] is not None]
        p95s = [r["latency_p95_ms"] for r in level_rounds if r["latency_p95_ms"] is not None]
        errors = sum(r["errors"] for r in level_rounds)

        summary_by_level[f"c{c}"] = {
            "concurrency": c,
            "rounds": ROUNDS_PER_LEVEL,
            "n_requests_total": c * ROUNDS_PER_LEVEL,
            "total_errors": errors,
            "aggregate_throughput_tok_s_mean": round(statistics.mean(agg_throughputs), 2) if agg_throughputs else 0,
            "aggregate_throughput_tok_s_max": round(max(agg_throughputs), 2) if agg_throughputs else 0,
            "latency_p50_ms_mean": round(statistics.mean(p50s), 2) if p50s else 0,
            "latency_p95_ms_mean": round(statistics.mean(p95s), 2) if p95s else 0,
        }

        await asyncio.sleep(COOLDOWN_BETWEEN_LEVELS_S)

    # Print final summary
    print("\n" + "=" * 65)
    print("  SUMMARY (mean across rounds)")
    print("=" * 65)
    print(f"{'Conc':>6} | {'Throughput (tok/s)':>20} | {'p50 (ms)':>10} | {'p95 (ms)':>10} | {'Errors':>7}")
    print("-" * 65)
    for key in sorted(summary_by_level.keys()):
        s = summary_by_level[key]
        print(
            f"{s['concurrency']:>6} | {s['aggregate_throughput_tok_s_mean']:>20} | "
            f"{s['latency_p50_ms_mean']:>10} | {s['latency_p95_ms_mean']:>10} | "
            f"{s['total_errors']:>7}"
        )

    # Save
    out = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "rounds_per_level": ROUNDS_PER_LEVEL,
            "concurrency_levels": CONCURRENCY_LEVELS,
            "cooldown_round_s": COOLDOWN_BETWEEN_ROUNDS_S,
            "cooldown_level_s": COOLDOWN_BETWEEN_LEVELS_S,
        },
        "summary": summary_by_level,
        "raw_rounds": all_rounds,
    }
    out_path = RESULTS_DIR / f"load_test_concurrency_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n💾 Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
