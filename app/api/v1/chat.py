from typing import Dict
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.services.ollama import OllamaService
from app.services.chat import ChatService
from app.models.schemas import APIResponse, ChatRequest


async def preload_action():
    try:
        chat_service = ChatService()
        chat_service.preload_models()
        print("✅ Chat service started successfully.")
    except Exception as e:
        print(f"⚠️ Chat service failed to start: {e}")


chat_router = APIRouter(on_startup=[preload_action])


@chat_router.post("/new", response_model=APIResponse)
async def chat(
    req: ChatRequest,
    chat_service: ChatService = Depends(OllamaService),
) -> StreamingResponse:
    """Chat endpoint using Ollama service."""

    async def event_generator():
        async for chunk in chat_service.chat(
            messages=req.messages, article_id=req.articleId, stream=True
        ):
            yield f"data: {chunk}\n\n"

    # Return a Server-Sent Event (SSE) compatible stream
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@chat_router.post("/completion", response_model=APIResponse)
async def completion(
    req: ChatRequest,
    chat_service: ChatService = Depends(ChatService),
) -> StreamingResponse:
    """Completion endpoint using local model."""
    event_generator = chat_service.completion(
        messages=req.messages, article_id=req.articleId
    )
    # Return a Server-Sent Event (SSE) compatible stream
    return StreamingResponse(event_generator, media_type="text/event-stream")
