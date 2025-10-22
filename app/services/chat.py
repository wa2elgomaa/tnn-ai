# Load model directly
import asyncio
from json import dumps
from typing import Any, AsyncGenerator, Dict, List
import requests
from starlette.concurrency import run_in_threadpool
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer
from threading import Thread
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
    #     dtype="auto",
    #     device_map="auto",  # Automatically place on available GPUs
    # )
    tokenizer = AutoTokenizer.from_pretrained(
        settings.COMPLETION_MODEL,
    )
    model = AutoModelForCausalLM.from_pretrained(
        settings.COMPLETION_MODEL,
        device_map="auto",
        dtype="auto",
        # Optimize MoE layers with downloadable` MegaBlocksMoeMLP
        # use_kernels=True,
        # attn_implementation="kernels-community/vllm-flash-attn3",
    )
    # self.tokenizer = AutoTokenizer.from_pretrained(
    #     settings.CHAT_MODEL, trust_remote_code=True, use_fast=False
    # )
    # self.model = AutoModelForCausalLM.from_pretrained(
    #     settings.CHAT_MODEL,
    #     dtype=torch.float16,  # or bfloat16 if your GPU supports
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
                articleContent = article_text(content, limit=2000)

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

    async def completion(
        self,
        messages: List[Dict[str, Any]] = [],
        articleId: str = None,
    ):
        """
        Chat service entrypoint. If `stream=True`, yields streaming chunks.
        """
        try:
            # Step 1 — Optionally enrich messages with article content
            if articleId is not None:
                params = {"articleId": articleId, "query": dumps({"_id": articleId})}
                content = await run_in_threadpool(fetch_article_content, params)
                articleContent = article_text(content, limit=2000)

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "You are a reasoning model. Think step by step between <think>...</think> tags, "
                            "but only your thoughts go there. Then produce your final answer between <content>...</content>."
                        ),
                    }
                )
                if articleContent:
                    messages = [
                        {
                            "role": "user",
                            "content": "Use the following article content to answer the question. If the question is not related to the article, feel free to answer with suitable content.",
                        },
                        {
                            "role": "user",
                            "content": f"The article content is: {articleContent}",
                        },
                        *messages,
                    ]

                    inputs = self.tokenizer.apply_chat_template(
                        messages,
                        add_generation_prompt=True,
                        tokenize=True,
                        return_tensors="pt",
                        return_dict=True,
                    ).to(self.model.device)

                    streamer = TextIteratorStreamer(
                        self.tokenizer, skip_prompt=True, skip_special_tokens=True
                    )
                    generation_kwargs = dict(
                        **inputs,
                        max_new_tokens=400,
                        streamer=streamer,
                        do_sample=True,
                        temperature=0.7,
                    )

                    # Run in background thread
                    thread = Thread(
                        target=self.model.generate, kwargs=generation_kwargs
                    )
                    thread.start()

                    buffer = ""
                    # Pull all available chunks
                    for new_text in streamer:
                        buffer += new_text

                        # Detect reasoning vs final tags
                        print(f'new text is thinking: {new_text}')
                        if "<think>" in buffer:
                            buffer = buffer.replace("<think>", "")
                        elif "</think>" in buffer:
                            yield f"data: {dumps({'thinking': buffer.split('</think>')[0]})}\n\n"
                            buffer = buffer.split("</think>")[-1]
                        elif "<content>" in buffer:
                            buffer = buffer.replace("<content>", "")
                        elif "</content>" in buffer:
                            yield f"data: {dumps({ 'content': buffer.split('</content>')[0]})}\n\n"
                            buffer = buffer.split("</content>")[-1]

                        # Stream partial text
                        if buffer.strip():
                            yield f"data: {dumps({'content': buffer})}\n\n"
                            buffer = ""

                        await asyncio.sleep(0.05)  # prevent tight loop

                    # Ensure model finished
                    thread.join()

                    yield dumps({"event": "end"}).encode("utf-8")

        except Exception:
            log.error(f"Error while executing chat:\n{traceback.format_exc()}")
            yield dumps({"error": "internal server error"}).encode("utf-8")
