from typing import AsyncIterator, Any
import httpx
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse

class LlamaCppBackend(InferenceBackend):
    def __init__(self, base_url: str = "http://llamacpp:8080/v1"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    @property
    def name(self) -> str:
        return "llamacpp"

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        payload = {
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
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
        yield {"type": "token", "content": "llama.cpp streaming response chunk"}
