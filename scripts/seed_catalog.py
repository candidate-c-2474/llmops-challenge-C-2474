#!/usr/bin/env python3
"""
Sovereign Catalog Seeder: Creates SQL schemas, compiles pgvector indexing,
loads catalog.jsonl, and generates 384-dim vector embeddings with zero external download requirements.
"""
import os
import sys
import json
import math
import random
from pathlib import Path
import asyncio
import asyncpg

CATALOG_PATH = Path(__file__).parent.parent / "data" / "catalog.jsonl"
DB_URL = os.getenv("DATABASE_URL", "postgresql://roomfit:roomfit@localhost:5432/roomfit")

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    currency TEXT DEFAULT 'USD',
    stock INTEGER NOT NULL DEFAULT 0,
    width DOUBLE PRECISION,
    height DOUBLE PRECISION,
    depth DOUBLE PRECISION,
    weight_kg DOUBLE PRECISION,
    description TEXT,
    tags TEXT[],
    embedding vector(384),
    search_vector tsvector,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_products_embedding ON products USING hnsw(embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_products_search_vector ON products USING gin (search_vector);
"""

TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION products_search_vector_update() RETURNS trigger AS $$
begin
  new.search_vector :=
     setweight(to_tsvector('english', coalesce(new.name, '')), 'A') ||
     setweight(to_tsvector('english', coalesce(new.description, '')), 'B') ||
     setweight(to_tsvector('english', coalesce(new.category, '')), 'C');
  return new;
end
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_products_search_vector_update ON products;
CREATE TRIGGER trg_products_search_vector_update
BEFORE INSERT OR UPDATE ON products
FOR EACH ROW EXECUTE FUNCTION products_search_vector_update();
"""


def generate_deterministic_embedding(text: str, dim: int = 384) -> list[float]:
    """Generates a deterministic, unit-normalized vector from text (zero network dependencies)."""
    rng = random.Random(text)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [round(x / norm, 6) for x in vec]


async def seed():
    print(f"Connecting to database: {DB_URL}")
    try:
        conn = await asyncpg.connect(DB_URL)
    except Exception as e:
        print(f"Database connection error: {e}")
        print("Ensure postgres container is running (docker compose up -d)")
        sys.exit(1)

    # 1. Provision schemas & extensions
    print("Provisioning Postgres schema and pgvector extensions...")
    await conn.execute(SCHEMA_SQL)
    await conn.execute(TRIGGER_SQL)

    if not CATALOG_PATH.exists():
        print(f"Error: Catalog file not found at {CATALOG_PATH}")
        sys.exit(1)

    # 2. Read and Parse JSONL
    print(f"Reading catalog from {CATALOG_PATH}...")
    products = []
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                products.append(json.loads(line))

    print(f"Found {len(products)} products. Ingesting with 384-dim vector embeddings...")
    for idx, p in enumerate(products):
        dims = p.get("dimensions", {})
        width = dims.get("width_cm", dims.get("width"))
        height = dims.get("height_cm", dims.get("height"))
        depth = dims.get("depth_cm", dims.get("depth"))
        weight = dims.get("weight_kg")

        text_payload = f"Product: {p['name']}. Category: {p['category']}. Description: {p['description']}"
        vector = generate_deterministic_embedding(text_payload, dim=384)
        vector_str = "[" + ",".join(str(x) for x in vector) + "]"

        await conn.execute("""
            INSERT INTO products (id, name, category, price, currency, stock, width, height, depth, weight_kg, description, tags, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::vector)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                price = EXCLUDED.price,
                stock = EXCLUDED.stock,
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                depth = EXCLUDED.depth,
                weight_kg = EXCLUDED.weight_kg,
                description = EXCLUDED.description,
                tags = EXCLUDED.tags,
                embedding = EXCLUDED.embedding,
                updated_at = TIMEZONE('utc', NOW())
        """, p["id"], p["name"], p["category"], float(p["price"]), p.get("currency", "USD"), int(p.get("stock", 0)),
             width, height, depth, weight, p.get("description", ""), p.get("tags", []), vector_str)

        if (idx + 1) % 500 == 0 or (idx + 1) == len(products):
            print(f"  Ingested {idx + 1}/{len(products)} products...")

    print("✅ Catalog successfully seeded, indexed, and vector-embedded!")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
