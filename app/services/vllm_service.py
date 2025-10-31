import httpx
from typing import List, Dict, Any
from app.config.settings import settings


class VLLMService:
    def __init__(self):
        self.base_url = settings.VLLM_API_BASE
        self.model = settings.VLLM_MODEL_ID

    async def chat_once(self, messages: List[Dict[str, str]]) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 512,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def chat_stream(self, messages: List[Dict[str, str]]):
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield line[6:]
