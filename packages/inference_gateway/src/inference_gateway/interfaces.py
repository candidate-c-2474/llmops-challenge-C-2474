from abc import ABC, abstractmethod
from typing import AsyncIterator, Any
from pydantic import BaseModel, Field


class InferenceRequest(BaseModel):
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    temperature: float = 0.3
    max_tokens: int = 1024
    stream: bool = False


class InferenceResponse(BaseModel):
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    role: str = "assistant"
    usage: dict[str, Any] = Field(default_factory=dict)
    backend_name: str = ""


class InferenceBackend(ABC):
    @abstractmethod
    async def generate(self, request: InferenceRequest) -> InferenceResponse: ...

    @abstractmethod
    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]: ...

    @property
    @abstractmethod
    def name(self) -> str: ...