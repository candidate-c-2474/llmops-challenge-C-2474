"""
Adapter Pattern: Maps vLLM's OpenAI-compatible streaming API to InferenceBackend.
Normalizes response shapes and finish reasons.
"""
from __future__ import annotations
import json
import httpx
import structlog
from typing import AsyncIterator, Any
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse

logger = structlog.get_logger(__name__)


def _normalize_usage(usage: dict) -> dict:
    """Sanitize OpenAI-style usage block.

    vLLM 0.29+ returns `prompt_tokens_details` and `completion_tokens_details`
    as `null` when not computed. Our Pydantic schema is strict, so we filter
    down to the integer token counters the rest of the system actually uses.
    """
    if not usage:
        return {}
    return {k: v for k, v in usage.items() if isinstance(v, int)}


class VLLMBackend(InferenceBackend):
    def __init__(self, base_url: str = "http://vllm:8001/v1", model_name: str = "Qwen/Qwen2.5-3B-Instruct-AWQ"):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    @property
    def name(self) -> str:
        return f"vllm:{self.model_name}"

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        payload = {
            "model": self.model_name,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False
        }
        if request.tools:
            payload["tools"] = request.tools

        resp = await self.client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]

        return InferenceResponse(
            content=choice.get("content"),
            tool_calls=choice.get("tool_calls"),
            role=choice.get("role", "assistant"),
            usage=_normalize_usage(data.get("usage", {})),
            backend_name=self.name,
        )

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        payload = {
            "model": self.model_name,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True
        }
        if request.tools:
            payload["tools"] = request.tools

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