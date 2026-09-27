import json
import uuid
import structlog
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

router = APIRouter(tags=["Chat Copilot"])

class ChatRequest(BaseModel):
    message: str = Field(..., description="User query or instruction")
    history: list[dict] = Field(default_factory=list, description="Previous conversation turns")

@router.post("/chat")
async def chat_endpoint(request: Request, body: ChatRequest):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    agent = request.app.state.agent

    async def event_generator():
        try:
            async for event in agent.run(body.message, request_id=request_id):
                yield {
                    "event": "message",
                    "data": json.dumps(event)
                }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)})
            }

    return EventSourceResponse(event_generator())
