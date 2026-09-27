from abc import ABC, abstractmethod
from rag_core.models import RetrievedChunk

class Retriever(ABC):
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 20) -> list[RetrievedChunk]: ...
    
    @property
    @abstractmethod
    def name(self) -> str: ...
