from __future__ import annotations

import logging
import requests
from json import dumps
from ..config.models import SuggestRequest
from ..services.cms import article_text, fetch_article_content
from ..utils.tagger import TagSuggester
from starlette.concurrency import run_in_threadpool

log = logging.getLogger(__name__)


# ---- Public API (keeps your async signature but uses requests under the hood) ----
async def suggestTags(req: SuggestRequest, suggester: TagSuggester):
    try:
        articleContent = req.text
        articleId = req.articleId

        # query article content if no text
        if articleId is not None and articleContent is None:
            # Build the query your Arc endpoint expects. Add `website` if required.
            params = {
                "articleId": articleId,
                "query" : dumps({
                    "_id": articleId
                })
            }
            # Run sync requests call without blocking the event loop
            content = await run_in_threadpool(fetch_article_content, params)
            articleContent = article_text(content)

        if articleContent is not None:
            items, meta = suggester.suggest(
                text=articleContent,
                k=req.k,
                min_score=req.min_score,
                use_reranker=req.use_reranker,
            )
            return items, meta
        else:
            return [], {}

    except requests.HTTPError as e:
        # HTTP layer problem (403/404/etc.)
        log.exception(f"HTTP error while fetching article content: {e}")
        return [], {}
    except Exception as e:
        # JSON/content-type/other unexpected issues
        import traceback
        log.error(f"Error --> {traceback.format_exc()}")
        return [], {}