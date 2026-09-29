#!/usr/bin/env python3
"""
Apply catalog_updates.jsonl against a running RoomFit API.

Reads data/catalog_updates.jsonl and POSTs each event to
POST /admin/catalog/apply-updates, which publishes a CatalogUpdate on the
CatalogEventBus. The CacheInvalidator observer then purges any cached
answers that mention the affected products (Observer pattern).

Usage:
    python3 scripts/apply_updates.py [--api URL] [--file PATH] [--delay SECONDS]

Defaults:
    --api    http://localhost:8000
    --file   data/catalog_updates.jsonl
    --delay  0.0 (no delay between events)

Requires: httpx (already installed in the API container and on the host if
you've run any of the other scripts).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Run this inside the API container:")
    print("  docker compose -f infra/docker-compose.yml run --rm \\")
    print("    -v \"$PWD/data:/app/data:ro\" -v \"$PWD/scripts:/app/scripts:ro\" \\")
    print("    api python /app/scripts/apply_updates.py")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--file", default="data/catalog_updates.jsonl")
    ap.add_argument("--delay", type=float, default=0.0)
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        sys.exit(1)

    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    print(f"Applying {len(events)} catalog update events to {args.api}")

    succeeded = 0
    ignored = 0
    failed = 0

    with httpx.Client(base_url=args.api, timeout=30.0) as client:
        for i, event in enumerate(events, start=1):
            payload = {
                "event": event["event"],
                "product_ids": event["product_ids"],
            }
            try:
                resp = client.post("/admin/catalog/apply-updates", json=payload)
                data = resp.json()
                status = data.get("status")
                if status == "success":
                    succeeded += 1
                    affected = data.get("affected_products", 0)
                    print(
                        f"  [{i:3d}/{len(events)}] {event['event']:24s} "
                        f"{len(event['product_ids']):2d} ids -> OK "
                        f"({affected} affected)"
                    )
                elif status == "ignored":
                    ignored += 1
                    print(
                        f"  [{i:3d}/{len(events)}] {event['event']:24s} "
                        f"-> IGNORED ({data.get('reason', 'unknown')})"
                    )
                else:
                    failed += 1
                    print(f"  [{i:3d}/{len(events)}] unexpected response: {data}")
            except httpx.HTTPError as e:
                failed += 1
                print(f"  [{i:3d}/{len(events)}] HTTP error: {e}")

            if args.delay > 0:
                time.sleep(args.delay)

    print(f"\nDone: {succeeded} succeeded, {ignored} ignored, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
