from json import JSONDecodeError, loads
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.config.settings import settings


class OllamaService:
    """
    Simple Ollama API client using the /api/chat endpoint.
    Works with local Ollama servers (e.g., http://localhost:11434).
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.CHAT_MODEL

    async def chat_stream(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream responses from Ollama as an async generator.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": temperature, **kwargs},
            "stream": True,
        }

        url = f"{self.base_url}/api/chat"

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = loads(line)
                        # content = chunk.get("message", {}).get("content")
                        content = chunk.get("message", {})
                        if content:
                            yield content
                    except JSONDecodeError:
                        continue

    async def chat_once(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, **kwargs
    ) -> str:
        """
        Non-streaming chat request.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": temperature, **kwargs},
            "stream": False,
        }

        url = f"{self.base_url}/api/chat"

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # return data.get("message", {}).get("content", "")
            return data.get("message", {})

    async def chat(
        self, messages: List[Dict[str, str]], stream: bool = False, **kwargs
    ):
        """
        Unified entrypoint for streaming or full response.
        """
        if stream:
            async for chunk in self.chat_stream(messages, **kwargs):
                yield chunk
        else:
            # Return the whole text
            result = await self.chat_once(messages, **kwargs)
            yield result  # ✅ yield once so the function is an async generator
