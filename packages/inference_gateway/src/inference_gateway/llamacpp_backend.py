"""
Adapter Pattern: Maps llama.cpp GGUF server API to InferenceBackend.
Normalizes streaming tokens and output structures.
"""
from __future__ import annotations
import json
import httpx
from typing import AsyncIterator, Any
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse

class LlamaCppBackend(InferenceBackend):
    def __init__(self, base_url: str = "http://llamacpp:8080/v1"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    @property
    def name(self) -> str:
        return "llamacpp:cpu"

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        payload = {
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False
        }
        resp = await self.client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        return InferenceResponse(
            content=choice.get("content"),
            tool_calls=choice.get("tool_calls"),
            role=choice.get("role", "assistant"),
            usage=data.get("usage", {}),
            backend_name=self.name,
        )

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        payload = {
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True
        }
        req = self.client.build_request("POST", "/chat/completions", json=payload)
        resp = await self.client.send(req, stream=True)
        
        try:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    choice = chunk["choices"][0]
                    delta = choice.get("delta", {})
                    
                    yield {
                        "type": "token",
                        "content": delta.get("content", ""),
                        "tool_calls": delta.get("tool_calls"),
                        "finish_reason": choice.get("finish_reason")
                    }
        finally:
            await resp.aclose()