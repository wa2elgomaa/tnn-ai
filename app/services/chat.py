# Load model directly
from json import dumps
from typing import Any, AsyncGenerator, Dict, List
import requests
from starlette.concurrency import run_in_threadpool
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch
import logging
import traceback

from app.services.cms import article_text, fetch_article_content
from app.config.settings import settings
from app.services.ollama import OllamaService

log = logging.getLogger(__name__)


class ChatService:
    # def __init__(self):
    # tokenizer = AutoTokenizer.from_pretrained(settings.CHAT_MODEL)
    # model = AutoModelForCausalLM.from_pretrained(settings.CHAT_MODEL)
    # self.generator = pipeline(
    #     "text-generation",
    #     model=settings.CHAT_MODEL,
    #     torch_dtype="auto",
    #     device_map="auto",  # Automatically place on available GPUs
    # )

    # self.tokenizer = AutoTokenizer.from_pretrained(
    #     settings.CHAT_MODEL, trust_remote_code=True, use_fast=False
    # )
    # self.model = AutoModelForCausalLM.from_pretrained(
    #     settings.CHAT_MODEL,
    #     torch_dtype=torch.float16,  # or bfloat16 if your GPU supports
    #     device_map="auto",
    #     load_in_4bit=True,  # if quantization is supported
    # )

    async def chat(
        self,
        messages: List[Dict[str, Any]] = [],
        articleId: str = None,
        stream: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Chat service entrypoint. If `stream=True`, yields streaming chunks.
        """
        try:
            # Step 1 — Optionally enrich messages with article content
            if articleId is not None:
                params = {"articleId": articleId, "query": dumps({"_id": articleId})}
                content = await run_in_threadpool(fetch_article_content, params)
                articleContent = article_text(content)

                if articleContent:
                    messages.append(
                        {
                            "role": "user",
                            "content": f"The article content is: {articleContent}",
                        }
                    )

            # Step 2 — Create the Ollama service
            service = OllamaService(model=settings.CHAT_MODEL)
            # Step 3 — Stream or get full result
            if stream:
                async for chunk in service.chat_stream(messages):
                    yield chunk
            else:
                reply = await service.chat_once(messages)
                yield reply

        except Exception:
            log.error(f"Error while executing chat:\n{traceback.format_exc()}")
            yield "Error: internal server error"
