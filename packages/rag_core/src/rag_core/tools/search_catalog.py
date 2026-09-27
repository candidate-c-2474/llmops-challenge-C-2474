import json
from rag_core.tools.registry import tool

def create_search_catalog_tool(pipeline):
    @tool(
        name="search_catalog",
        description="Search the furniture catalog using natural language.",
        parameters={"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 5}}, "required": ["query"]}
    )
    async def search_catalog(query: str, top_k: int = 5) -> str:
        chunks = await pipeline.retrieve(query, top_k=top_k)
        if not chunks: return json.dumps({"results": [], "message": "No products found."})
        results = [{"product_id": c.product_id, "content": c.content, "score": round(c.score, 4)} for c in chunks]
        return json.dumps({"results": results, "total": len(results)})
    return search_catalog
