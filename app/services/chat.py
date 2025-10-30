import asyncio
from json import dumps
from typing import Any, AsyncGenerator, Dict, List, Optional
from starlette.concurrency import run_in_threadpool
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer
from threading import Thread
import traceback

from app.config.settings import settings
from app.core.logger import get_logger
from app.services.cms import CMSService
from app.services.ollama import OllamaService

logger = get_logger(__name__)


class ChatService:
    """
    Chat service for handling conversational AI interactions.
    Supports both Ollama-based chat and local model completion.
    """

    def __init__(
        self,
    ):
        """
        Initialize ChatService with dependencies.

        Args:
            cms_service: CMSService instance for fetching article content
            ollama_service: OllamaService instance for chat interactions
        """
        self.cms_service = CMSService()
        self.ollama_service = OllamaService()

        # Lazy-load model and tokenizer only when needed
        self._tokenizer: Optional[AutoTokenizer] = None
        self._model: Optional[AutoModelForCausalLM] = None
        self._model_loaded = False

        self.preload_models()

    def preload_models(self):
        """Lazy-load the completion model and tokenizer."""
        if self._model_loaded:
            return

        if not settings.COMPLETION_MODEL:
            raise ValueError("COMPLETION_MODEL not configured")

        logger.info(f"Loading completion model: {settings.COMPLETION_MODEL}")
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                settings.COMPLETION_MODEL,
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                settings.COMPLETION_MODEL,
                device_map="auto",
                dtype="auto",
            )
            self._model_loaded = True
            logger.info("Completion model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load completion model: {e}")
            raise

    async def _enrich_with_article_content(
        self, messages: List[Dict[str, Any]], article_id: str, limit: int = 2000
    ) -> List[Dict[str, Any]]:
        """
        Enrich messages with article content if articleId is provided.

        Args:
            messages: List of message dictionaries
            article_id: Article ID to fetch content for
            limit: Maximum number of characters to include

        Returns:
            Updated messages list with article content
        """
        if not article_id or not self.cms_service:
            return messages

        try:
            params = {"articleId": article_id, "query": dumps({"_id": article_id})}
            content = await run_in_threadpool(
                self.cms_service.fetch_article_content, params
            )
            article_content = self.cms_service.article_text(content, limit=limit)

            if article_content:
                messages.append(
                    {
                        "role": "user",
                        "content": f"The article content is: {article_content}",
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to enrich with article content: {e}")

        return messages

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        article_id: Optional[str] = None,
        stream: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Chat service entrypoint using Ollama.

        Args:
            messages: List of conversation messages
            article_id: Optional article ID to enrich context
            stream: Whether to stream responses

        Yields:
            Chat response chunks or full response
        """
        if not self.ollama_service:
            raise ValueError("OllamaService not provided")

        try:
            # Enrich messages with article content if provided
            enriched_messages = await self._enrich_with_article_content(
                messages.copy(), article_id or ""
            )

            # Stream or get full result
            if stream:
                async for chunk in self.ollama_service.chat_stream(enriched_messages):
                    yield chunk
            else:
                reply = await self.ollama_service.chat_once(enriched_messages)
                yield reply

        except Exception as e:
            logger.error(f"Error while executing chat: {traceback.format_exc()}")
            yield "Error: internal server error"

    async def completion(
        self,
        messages: List[Dict[str, Any]],
        article_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Completion service using local model.

        Args:
            messages: List of conversation messages
            article_id: Optional article ID to enrich context

        Yields:
            Completion chunks as SSE-formatted strings
        """
        try:
            # Ensure model is loaded
            self.preload_models()

            # Work with a copy of messages to avoid mutation
            enriched_messages = messages.copy()

            # Enrich messages with article content if provided
            if article_id:
                if not self.cms_service:
                    logger.warning("CMS service not available for article enrichment")
                else:
                    params = {
                        "articleId": article_id,
                        "query": dumps({"_id": article_id}),
                    }
                    content = await run_in_threadpool(
                        self.cms_service.fetch_article_content, params
                    )
                    article_content = self.cms_service.article_text(content, limit=2000)

                    if article_content:
                        enriched_messages = [
                            {
                                "role": "user",
                                "content": (
                                    "First, reason internally (don't show your reasoning). "
                                    "Then answer directly. Use the following article content to answer the question. "
                                    "If the question is not related to the article, feel free to answer with suitable content."
                                ),
                            },
                            {
                                "role": "user",
                                "content": f"The article content is: {article_content}",
                            },
                            *enriched_messages,
                        ]

            # Prepare inputs
            inputs = self._tokenizer.apply_chat_template(
                enriched_messages,
                add_generation_prompt=True,
                tokenize=True,
                return_tensors="pt",
                return_dict=True,
            ).to(self._model.device)

            streamer = TextIteratorStreamer(
                self._tokenizer, skip_prompt=True, skip_special_tokens=True
            )
            generation_kwargs = dict(
                **inputs,
                max_new_tokens=400,
                streamer=streamer,
                do_sample=True,
                temperature=0.7,
            )

            # Run generation in background thread
            thread = Thread(target=self._model.generate, kwargs=generation_kwargs)
            thread.start()

            # Yield chunks as SSE format
            for new_text in streamer:
                yield f"data: {dumps({'content': new_text})}\n\n"
                await asyncio.sleep(0.05)  # Prevent tight loop

            # Ensure model finished
            thread.join()

            yield dumps({"event": "end"}).encode("utf-8")

        except Exception as e:
            logger.error(f"Error while executing completion: {traceback.format_exc()}")
            yield dumps({"error": "internal server error"}).encode("utf-8")
