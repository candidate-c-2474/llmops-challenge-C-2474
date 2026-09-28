import json
from rag_core.tools.registry import ToolRegistry
from rag_core.security import sanitize_chunks


def create_search_catalog_tool(pipeline, registry: ToolRegistry):
    async def search_catalog(query: str, top_k: int = 5) -> str:
        chunks = await pipeline.retrieve(query, top_k=top_k)
        if not chunks:
            return json.dumps({"results": [], "message": "No products found."})

        # Defense-in-depth: catalog content is untrusted (seller uploads,
        # catalog syncs). Sanitize before it reaches the LLM context.
        # See packages/rag_core/src/rag_core/security/prompt_guard.py
        chunks = sanitize_chunks(chunks)

        results = [
            {
                "product_id": c.product_id,
                "content": c.content,
                "score": round(c.score, 4),
            }
            for c in chunks
        ]
        return json.dumps({"results": results, "total": len(results)})

    registry.register(
        name="search_catalog",
        desc="Search the furniture catalog using natural language. Returns ranked product IDs with content previews.",
        params={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum number of results to return",
                },
            },
            "required": ["query"],
        },
        func=search_catalog,
    )
    return search_catalog
