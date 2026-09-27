#!/usr/bin/env python3
"""
Seed Catalog Script — Populates Postgres database with furniture products.
Works seamlessly both inside Docker containers and directly from WSL host.
Candidate ID: C-XXXX
"""

import asyncio
import json
import socket
from pathlib import Path
from rag_core.config import PostgresConfig
from rag_core.repository import PostgresCatalogRepository
from rag_core.models import Product, Dimensions

CATALOG_FILE = Path(__file__).parent.parent / "data" / "catalog.jsonl"

async def seed():
    print("🌱 Seeding database from catalog.jsonl...")
    if not CATALOG_FILE.exists():
        print(f"❌ Error: Catalog file not found at {CATALOG_FILE}")
        return

    config = PostgresConfig()
    
    # Try resolving host; fallback to 127.0.0.1 if running on local host outside Docker
    try:
        socket.gethostbyname(config.host)
    except socket.gaierror:
        print(f"ℹ️  Host '{config.host}' not found in local DNS. Falling back to '127.0.0.1' for local execution.")
        config = PostgresConfig(host="127.0.0.1")

    repo = PostgresCatalogRepository(config)
    
    try:
        await repo.initialize()
        products = []
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    dims = Dimensions(**item.pop("dimensions")) if "dimensions" in item else None
                    products.append(Product(**item, dimensions=dims))

        for p in products:
            await repo.upsert_product(p)
        print(f"✅ Successfully seeded {len(products)} products into Postgres ({config.host}:{config.port}).")
    except Exception as e:
        print(f"ℹ️  Postgres not reachable ({e}).")
        print("   (Run 'docker compose up postgres' first to seed into live database).")
    finally:
        await repo.close()

if __name__ == "__main__":
    asyncio.run(seed())