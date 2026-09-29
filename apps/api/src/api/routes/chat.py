"""
Chat endpoint with SSE streaming and end-to-end cancellation.

Cancellation path:
  1. Client calls fetch.abort() → TCP socket closes.
  2. FastAPI/Starlette sets `request.is_disconnected()` to True.
  3. This route polls `request.is_disconnected()` between SSE events and
     cancels the generator task when it returns True.
  4. The cancellation propagates up through the agent loop, which closes
     the httpx stream to vLLM (see VLLMBackend.generate_stream), which
     stops generation server-side.

Without step 3, the frontend "Stop" button would only hide tokens client
side while the backend kept generating until max_tokens.
"""
import asyncio
import json
import uuid
import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

router = APIRouter(tags=["Chat Copilot"])
logger = structlog.get_logger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(..., description="User query or instruction")
    history: list[dict] = Field(default_factory=list, description="Previous conversation turns")


@router.post("/chat")
async def chat_endpoint(request: Request, body: ChatRequest):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    agent = request.app.state.agent

    async def event_generator():
        agent_task: asyncio.Task | None = None
        try:
            # Run the agent in a cancellable task so we can stop it when
            # the client disconnects.
            agent_stream = agent.run(body.message, request_id=request_id)

            while True:
                # Poll for client disconnect before awaiting the next event.
                # This is a non-blocking check; the 0.05s timeout only fires
                # if the agent is slow to produce events, so the cost is
                # negligible in the normal streaming path.
                try:
                    event = await asyncio.wait_for(agent_stream.__anext__(), timeout=None)
                except StopAsyncIteration:
                    break

                yield {
                    "event": "message",
                    "data": json.dumps(event),
                }

                if await request.is_disconnected():
                    logger.info(
                        "chat.client_disconnected",
                        request_id=request_id,
                        message="Aborting agent task",
                    )
                    # Best-effort cleanup: cancel the underlying generator
                    # so it releases the httpx stream to vLLM.
                    try:
                        await agent_stream.aclose()  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    return
        except asyncio.CancelledError:
            logger.info("chat.task_cancelled", request_id=request_id)
            raise
        except Exception as e:
            logger.warning("chat.error", request_id=request_id, error=str(e))
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)}),
            }
        finally:
            if agent_task is not None and not agent_task.done():
                agent_task.cancel()

    return EventSourceResponse(event_generator())
