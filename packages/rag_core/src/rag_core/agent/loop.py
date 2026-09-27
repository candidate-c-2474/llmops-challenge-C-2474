import json
from typing import AsyncIterator, Protocol, Any
from rag_core.config import AgentConfig
from rag_core.models import ChatMessage, ToolCall
from rag_core.tools.registry import ToolRegistry
from rag_core.agent.prompts import SYSTEM_PROMPTS

class InferenceBackend(Protocol):
    async def generate(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.3, max_tokens: int = 1024, stream: bool = False) -> dict | AsyncIterator[dict]: ...

class AgentLoop:
    def __init__(self, backend: InferenceBackend, tool_registry: ToolRegistry, config: AgentConfig | None = None):
        self._backend = backend
        self._tools = tool_registry
        self._config = config or AgentConfig()

    async def run(self, user_message: str, history: list[ChatMessage] | None = None, request_id: str = "") -> AsyncIterator[dict]:
        messages = [ChatMessage(role="system", content=SYSTEM_PROMPTS["roomfit_copilot"])]
        if history:
            messages.extend(history)
        messages.append(ChatMessage(role="user", content=user_message))
        
        tools_schema = self._tools.get_openai_tools_schema()
        tool_rounds = 0

        while tool_rounds < self._config.max_tool_rounds:
            msg_dicts = [{"role": m.role, "content": m.content} for m in messages if m.content]
            response = await self._backend.generate(messages=msg_dicts, tools=tools_schema if tools_schema else None, stream=False)
            
            assistant_msg = response.get("message", {})
            tool_calls_data = assistant_msg.get("tool_calls", [])
            
            if tool_calls_data:
                tool_rounds += 1
                for tc_data in tool_calls_data:
                    tc = ToolCall(name=tc_data["function"]["name"], arguments=json.loads(tc_data["function"]["arguments"]))
                    yield {"type": "tool_call", "name": tc.name, "arguments": tc.arguments}
                    
                    result = await self._tools.execute(tc)
                    yield {"type": "tool_result", "name": result.name, "content": result.content}
                    messages.append(ChatMessage(role="tool", content=result.content, name=result.name))
                continue
            else:
                content = assistant_msg.get("content", "")
                for i in range(0, len(content), 4):
                    yield {"type": "token", "content": content[i:i+4]}
                break
                
        yield {"type": "done", "usage": {"tool_rounds": tool_rounds}}
