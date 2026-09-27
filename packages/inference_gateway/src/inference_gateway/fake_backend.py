import asyncio
from typing import AsyncIterator, Any
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse

class FakeBackend(InferenceBackend):
    def __init__(self, name: str = "fake_backend", default_response: str = "Hello! I am RoomFit Copilot. How can I help you today?"):
        self._name = name
        self.default_response = default_response

    @property
    def name(self) -> str:
        return self._name

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        await asyncio.sleep(0.01)
        return InferenceResponse(
            content=self.default_response,
            role="assistant",
            usage={"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
            backend_name=self.name,
        )

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        words = self.default_response.split()
        for w in words:
            await asyncio.sleep(0.01)
            yield {"type": "token", "content": w + " "}
