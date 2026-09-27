from typing import AsyncIterator, Any
import httpx
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse

class VLLMBackend(InferenceBackend):
    def __init__(self, base_url: str = "http://vllm:8000/v1", model_name: str = "Qwen/Qwen2.5-3B-Instruct-AWQ"):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    @property
    def name(self) -> str:
        return "vllm"

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        payload = {
            "model": self.model_name,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
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
            usage=data.get("usage", {}),
            backend_name=self.name,
        )

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "token", "content": "vLLM streaming response chunk"}
