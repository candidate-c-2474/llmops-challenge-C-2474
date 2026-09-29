#!/usr/bin/env python3
"""
Failover test: kill the primary, verify traffic moves to the fallback,
verify traffic moves back after recovery.

Requires:
  - The RoomFit API running on http://localhost:8000
  - The vLLM primary running on http://172.25.12.152:8001
  - The fallback (LM Studio on Windows) reachable via the configured
    LLAMACPP_URL (default http://host.docker.internal:1234/v1)

The test does NOT kill the primary itself (that requires host access).
Instead it uses a control script that you invoke manually between phases.

Run:
    docker compose -f infra/docker-compose.yml run --rm \\
      -v "$PWD/bench:/app/bench" \\
      api python /app/bench/run_failover_test.py

The script will print a "PAUSE" prompt at each phase boundary, so you can
kill or restart the vLLM process from another terminal.
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

API = "http://roomfit-api:8000"
RESULTS_DIR = Path("/app/bench/results")
RESULTS_DIR.mkdir(exist_ok=True)

N_REQUESTS_PER_PHASE = 10
TIMEOUT_S = 30.0


async def probe_health(client: httpx.AsyncClient) -> dict:
    r = await client.get("/health", timeout=15.0)
    return r.json()


async def one_chat(client: httpx.AsyncClient) -> dict:
    """Send a chat request and capture whether it succeeded and which
    backend served it (from the SSE 'done' event or the response)."""
    t0 = time.perf_counter()
    try:
        async with client.stream(
            "POST", "/chat",
            json={"message": "hello"},
            timeout=TIMEOUT_S,
        ) as resp:
            if resp.status_code != 200:
                return {"ok": False, "status": resp.status_code,
                        "latency_ms": (time.perf_counter() - t0) * 1000}
            done_seen = False
            error_msg = None
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        payload = json.loads(line[6:])
                    except Exception:
                        continue
                    if payload.get("type") == "done":
                        done_seen = True
                    elif payload.get("type") == "error":
                        error_msg = payload.get("message", "unknown")
            elapsed = (time.perf_counter() - t0) * 1000
            if error_msg:
                return {"ok": False, "error": error_msg, "latency_ms": elapsed}
            return {"ok": done_seen, "latency_ms": elapsed}
    except Exception as e:
        return {"ok": False, "error": str(e),
                "latency_ms": (time.perf_counter() - t0) * 1000}


async def run_phase(client: httpx.AsyncClient, label: str) -> dict:
    print(f"\n[{label}] running {N_REQUESTS_PER_PHASE} requests...")
    results = []
    for i in range(N_REQUESTS_PER_PHASE):
        r = await one_chat(client)
        results.append(r)
        marker = "OK " if r.get("ok") else "ERR"
        print(f"  req {i+1:2d}: {marker}  {r.get('latency_ms', 0):.0f}ms  "
              f"{r.get('error', '')[:60]}")

    health = await probe_health(client)

    oks = [r for r in results if r.get("ok")]
    errs = [r for r in results if not r.get("ok")]
    lat = [r["latency_ms"] for r in results if r.get("ok")]

    summary = {
        "phase": label,
        "n_requests": N_REQUESTS_PER_PHASE,
        "n_ok": len(oks),
        "n_err": len(errs),
        "p50_latency_ms": round(statistics.median(lat), 1) if lat else None,
        "cb_state": health.get("circuit_breaker", {}).get("state"),
        "cb_failure_count": health.get("circuit_breaker", {}).get("failure_count"),
        "primary_reachable": health.get("backends", {}).get("primary", {}).get("reachable"),
        "fallback_reachable": health.get("backends", {}).get("fallback", {}).get("reachable"),
    }
    print(f"  -> OK={summary['n_ok']} ERR={summary['n_err']} "
          f"p50={summary['p50_latency_ms']}ms "
          f"CB={summary['cb_state']} failures={summary['cb_failure_count']}")
    return summary


async def main():
    print("=" * 65)
    print("  Failover Test — kill primary, verify fallback, verify recovery")
    print("=" * 65)

    async with httpx.AsyncClient(base_url=API) as client:
        phases = []

        # Phase 1: baseline (primary alive)
        phases.append(await run_phase(client, "1-baseline"))

        # Phase 2: kill the primary manually
        print("\n" + "!" * 65)
        print("  ACTION REQUIRED: kill the vLLM primary now.")
        print("  In another terminal run:")
        print("    pkill -9 -f 'vllm.entrypoints.openai.api_server'")
        print("  Then press ENTER here to continue.")
        print("!" * 65)
        try:
            input()
        except EOFError:
            pass

        # Phase 3: failover (primary dead, fallback should serve)
        phases.append(await run_phase(client, "3-failover"))

        # Phase 4: restart the primary manually
        print("\n" + "!" * 65)
        print("  ACTION REQUIRED: restart the vLLM primary now.")
        print("  In another terminal run the nohup command from README.md")
        print("  (port 8001, fp8). Wait for 'Application startup complete',")
        print("  then press ENTER here to continue.")
        print("!" * 65)
        try:
            input()
        except EOFError:
            pass

        # Phase 5: recovery (CB should transition HALF_OPEN -> CLOSED)
        print("\nWaiting 35s for the CircuitBreaker recovery timeout...")
        await asyncio.sleep(35)
        phases.append(await run_phase(client, "5-recovery"))

    # Summary
    out = {
        "timestamp": datetime.now().isoformat(),
        "n_per_phase": N_REQUESTS_PER_PHASE,
        "phases": phases,
    }
    path = RESULTS_DIR / f"failover_test_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)

    print("\n" + "=" * 65)
    print("  SUMMARY")
    print("=" * 65)
    for p in phases:
        print(f"  {p['phase']:15s}  OK={p['n_ok']:2d}  ERR={p['n_err']:2d}  "
              f"CB={p['cb_state']}  primary_reach={p['primary_reachable']}  "
              f"fallback_reach={p['fallback_reachable']}")
    print(f"\n  Saved: {path}")


if __name__ == "__main__":
    asyncio.run(main())
