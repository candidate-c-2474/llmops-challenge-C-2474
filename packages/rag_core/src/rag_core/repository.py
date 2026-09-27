from __future__ import annotations
from abc import ABC, abstractmethod
import structlog
import asyncpg
import numpy as np
from rag_core.config import PostgresConfig
from rag_core.models import Product, Dimensions, CatalogEvent, CatalogUpdate

logger = structlog.get_logger(__name__)

class CatalogRepository(ABC):
    @abstractmethod
    async def get_product(self, product_id: str) -> Product | None: ...
    @abstractmethod
    async def search_by_text(self, query: str, limit: int = 20) -> list[Product]: ...
    @abstractmethod
    async def search_by_embedding(self, embedding: list[float], limit: int = 20) -> list[tuple[Product, float]]: ...
    @abstractmethod
    async def get_products_by_ids(self, product_ids: list[str]) -> list[Product]: ...

class PostgresCatalogRepository(CatalogRepository):
    def __init__(self, config: PostgresConfig | None = None):
        self._config = config or PostgresConfig()
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        self._pool = await asyncpg.create_pool(dsn=self._config.dsn, min_size=self._config.min_pool_size, max_size=self._config.max_pool_size)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    def _row_to_product(self, row: asyncpg.Record) -> Product:
        dims = None
        if row["width"] is not None:
            dims = Dimensions(width=row["width"], height=row["height"], depth=row["depth"], weight_kg=row["weight_kg"])
        return Product(id=row["id"], name=row["name"], category=row["category"], price=row["price"], currency=row["currency"], stock=row["stock"], dimensions=dims, description=row["description"], tags=list(row["tags"]) if row["tags"] else [], updated_at=row["updated_at"])

    async def get_product(self, product_id: str) -> Product | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
            return self._row_to_product(row) if row else None

    async def get_products_by_ids(self, product_ids: list[str]) -> list[Product]:
        if not product_ids:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM products WHERE id = ANY($1::text[])", product_ids)
            return [self._row_to_product(r) for r in rows]

    async def search_by_text(self, query: str, limit: int = 20) -> list[Product]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT *, ts_rank_cd(search_vector, websearch_to_tsquery('english', $1)) AS rank
                FROM products WHERE search_vector @@ websearch_to_tsquery('english', $1)
                ORDER BY rank DESC LIMIT $2
            """, query, limit)
            if not rows:
                rows = await conn.fetch("""
                    SELECT *, similarity(name || ' ' || description, $1) AS rank
                    FROM products WHERE similarity(name || ' ' || description, $1) > 0.1
                    ORDER BY rank DESC LIMIT $2
                """, query, limit)
            return [self._row_to_product(r) for r in rows]

    async def search_by_embedding(self, embedding: list[float], limit: int = 20) -> list[tuple[Product, float]]:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT *, 1 - (embedding <=> $1::vector) AS similarity
                FROM products WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector LIMIT $2
            """, embedding_str, limit)
            return [(self._row_to_product(r), float(r["similarity"])) for r in rows]

class InMemoryCatalogRepository(CatalogRepository):
    def __init__(self):
        self._products: dict[str, Product] = {}

    async def get_product(self, product_id: str) -> Product | None:
        return self._products.get(product_id)

    async def get_products_by_ids(self, product_ids: list[str]) -> list[Product]:
        return [self._products[pid] for pid in product_ids if pid in self._products]

    async def search_by_text(self, query: str, limit: int = 20) -> list[Product]:
        q = query.lower()
        res = [p for p in self._products.values() if q in f"{p.name} {p.description} {p.category}".lower()]
        return res[:limit]

    async def search_by_embedding(self, embedding: list[float], limit: int = 20) -> list[tuple[Product, float]]:
        res = []
        q_vec = np.array(embedding)
        for p in self._products.values():
            if p.embedding:
                p_vec = np.array(p.embedding)
                sim = float(np.dot(q_vec, p_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(p_vec) + 1e-10))
                res.append((p, sim))
        res.sort(key=lambda x: x[1], reverse=True)
        return res[:limit]

    async def upsert_product(self, product: Product) -> None:
        self._products[product.id] = product
