from contextlib import asynccontextmanager
from json import dumps
from typing import List, Dict, Any
from fastapi import APIRouter, FastAPI
from pathlib import Path
from fastapi.responses import StreamingResponse

from app.config.settings import settings
from app.services.ollama import OllamaService

from ..services.chat import ChatService
from ..config.models import APIResponse, ChatRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # chatService.load(force_rebuild=False)
    yield
    # Shutdown (nothing to clean up explicitly)


chat_router = APIRouter(prefix="/chat")


@chat_router.post("/new", response_model=APIResponse)
async def chat(req: ChatRequest) -> Dict[str, str]:
    chatService = ChatService()
    # response = await chatService.newChat(req.messages, req.articleId)

    async def event_generator():
        async for chunk in chatService.chat(
            messages=req.messages, articleId=req.articleId, stream=True
        ):
            yield f"data: {chunk}\n\n"

    # async def generate_ollama_stream():
    #     # Ensure Ollama is running and the model is available
    #     # You might need to adjust the model name based on what you have installed
    #     response_stream = await chatService.chat(messages=req.messages, stream=True)
    #     print(f"response_stream: {response_stream}")
    #     yield response_stream
    #     # for chunk in response_stream:
    #     #     if "content" in chunk["message"]:
    #     #         yield dumps({"content": chunk["message"]["content"]}) + "\n"

    # Return a Server-Sent Event (SSE) compatible stream
    return StreamingResponse(event_generator(), media_type="text/event-stream")

    # return {"status": "ok", "response": response}


@chat_router.post("/completion", response_model=APIResponse)
async def completion(req: ChatRequest) -> Dict[str, str]:
    chatService = ChatService()

    event_generator = chatService.completion(
        messages=req.messages, articleId=req.articleId
    )
    # Return a Server-Sent Event (SSE) compatible stream
    return StreamingResponse(event_generator, media_type="text/event-stream")


def get():
    return chat_router
