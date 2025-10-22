from __future__ import annotations

import logging, os, json, hashlib, unicodedata, re, base64
import requests
from json import dumps
from typing import Any, Tuple, List

from starlette.concurrency import run_in_threadpool
from redis import asyncio as aioredis

from ..config.settings import settings

from ..config.models import SuggestRequest, SuggestResponse
from ..services.cms import article_text, fetch_article_content
from ..utils.tagger import TagSuggester
from ..services.cache import cache_get_json, cache_set_json

log = logging.getLogger(__name__)


def _canonicalize_text(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text).replace("\u00A0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def compute_text_hash(text: str) -> str:
    return hashlib.sha1(_canonicalize_text(text).encode("utf-8")).hexdigest()

def _cache_key(model: str, dim: int, text_hash: str, widen: bool, min_score: float) -> str:
    # include knobs that affect pool composition
    return f"sug:{model}:{dim}:{text_hash}:{int(widen)}:{min_score:.2f}"

def _encode_cursor(key: str, pos: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"k": key, "p": pos}).encode()).decode()

def _decode_cursor(cur: str) -> tuple[str, int] | None:
    try:
        d = json.loads(base64.urlsafe_b64decode(cur.encode()).decode())
        return d["k"], int(d["p"])
    except Exception:
        return None

# ---- Public API (keeps your async signature but uses requests under the hood) ----
async def suggestTags(req: SuggestRequest, suggester: TagSuggester) -> Tuple[List[dict], dict]:
    """
    Returns (items, meta). Adds Redis caching for the reranked shortlist.
    Supports optional req.offset / req.cursor / req.exclude_slugs / req.widen if present.
    """
    try:
        articleContent = req.text
        articleId = getattr(req, "articleId", None)

        # If no text, fetch from CMS
        if articleId is not None and not articleContent:
            params = {"articleId": articleId, "query": dumps({"_id": articleId})}
            content = await run_in_threadpool(fetch_article_content, params)
            articleContent = article_text(content, useHeadlines=req.useHeadlines, limit=req.words_limit)

        if not articleContent:
            return SuggestResponse(data=[], meta={})

        # Optional inputs (exist if you extended SuggestRequest)
        k = getattr(req, "limit", 5) or 5
        min_score = getattr(req, "min_score", 0.4)
        use_reranker = getattr(req, "use_reranker", None)
        widen = bool(getattr(req, "widen", False))
        exclude_slugs = set(getattr(req, "exclude_slugs", []) or [])
        cursor = getattr(req, "cursor", None)
        offset = int(getattr(req, "offset", 0) or 0)

        # If client passes a cursor, prefer it over offset
        start_pos = offset
        key_from_cursor = None
        if cursor:
            dec = _decode_cursor(cursor)
            if not dec:
                log.warning("Bad cursor; ignoring")
            else:
                key_from_cursor, start_pos = dec

        # Build cache key
        text_hash = compute_text_hash(articleContent)
        model_name = getattr(suggester, "model_name", "embedder")
        emb_dim = getattr(suggester, "dim", None) or (
            getattr(suggester, "embeddings", None).shape[1] if getattr(suggester, "embeddings", None) is not None else 0
        )
        cache_key = key_from_cursor or _cache_key(model_name, int(emb_dim), text_hash, widen, float(min_score))

        # Try Redis for cached pool
        pool = None
        try:
            cached = await cache_get_json(cache_key)
            if cached:
                pool = json.loads(cached)
        except Exception as e:
            log.warning(f"[redis] get failed: {e}")

        # Compute once if no cached pool
        meta = {}
        if pool is None:
            bigK = settings.TOPK_CANDIDATES
            # Loosen threshold a bit if widen=true
            effective_min = max(0.0, float(min_score) - 0.15) if widen else float(min_score)

            # Heavy work (sync) is fine; TagSuggester.suggest is CPU-bound
            items, meta = suggester.suggest(
                text=articleContent,
                k=int(bigK),
                min_score=effective_min,
                use_reranker=use_reranker,
            )

            # Exclude already shown/disliked if provided
            if exclude_slugs:
                items = [it for it in items if it.get("slug") and it["slug"] not in exclude_slugs]

            pool = items

            # Cache the full pool for pagination
            try:
                await cache_set_json(cache_key, json.dumps(pool, ensure_ascii=False), ex=settings.CACHE_TTL_SECONDS)
            except Exception as e:
                log.warning(f"[redis] set failed: {e}")

        # Page results
        end_pos = min(len(pool), start_pos + k)
        page = pool[start_pos:end_pos]
        has_more = end_pos < len(pool)
        next_cursor = _encode_cursor(cache_key, end_pos) if has_more else None

        # Merge/augment meta
        meta = {
            **(meta or {}),
            "text_hash": text_hash,
            "start": start_pos,
            "total": len(pool),
            "has_more": has_more,
            "next_cursor": next_cursor,
            "model": model_name,
            "dim": emb_dim,
        }

        return SuggestResponse(data=page, meta=meta)

    except requests.HTTPError as e:
        log.exception(f"HTTP error while fetching article content: {e}")
        return SuggestResponse(data=[], meta={})
    except Exception as e:
        import traceback
        log.error(f"Error --> {traceback.format_exc()}")
        return SuggestResponse(data=[], meta={})