from typing import Any, Callable, Awaitable
from rag_core.models import ToolCall, ToolResult

ToolFunction = Callable[..., Awaitable[str]]

class ToolDefinition:
    def __init__(self, name: str, description: str, parameters: dict, function: ToolFunction):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function

    def to_openai_schema(self) -> dict:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}

class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name: str, desc: str, params: dict, func: ToolFunction):
        self._tools[name] = ToolDefinition(name, desc, params, func)
    
    def get_openai_tools_schema(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]
        
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        tool_def = self._tools.get(tool_call.name)
        if not tool_def:
            return ToolResult(tool_call_id=tool_call.id, name=tool_call.name, content="", error="Unknown tool")
        try:
            content = await tool_def.function(**tool_call.arguments)
            return ToolResult(tool_call_id=tool_call.id, name=tool_call.name, content=content)
        except Exception as e:
            return ToolResult(tool_call_id=tool_call.id, name=tool_call.name, content="", error=str(e))

_global_registry = ToolRegistry()
def get_registry() -> ToolRegistry:
    return _global_registry

def tool(name: str, description: str, parameters: dict):
    def decorator(func: ToolFunction):
        _global_registry.register(name, description, parameters, func)
        return func
    return decorator
