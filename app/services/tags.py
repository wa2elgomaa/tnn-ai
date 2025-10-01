from __future__ import annotations

import logging
import requests
from json import JSONDecodeError, dumps
from app.config.models import SuggestRequest
from app.utils.helpers import clean_html
from app.utils.tagger import TagSuggester
from starlette.concurrency import run_in_threadpool

log = logging.getLogger(__name__)

CONTENT_URL = (
    "https://thenational-the-national-sandbox.cdn.arcpublishing.com"
    "/pf/api/v3/content/fetch/content-api"
)

# 🔐 Adjust these to your ArcXP setup (site key, optional API key, etc.)
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "x-arc-site": "the-national",  # <-- change if your site key differs
}
# If your endpoint requires query params like `website`, add them when you build `query`.


def article_text(a: dict) -> str:
    """
    Build compact, high-signal text from the ArcXP content JSON.
    """
    parts: list[str] = [
        a.get("headlines", {}).get("basic", "") or "",
        a.get("subheadlines", {}).get("basic", "") or "",
    ]

    # Merge content from content_elements (if any)
    elems = a.get("content_elements", [])
    if isinstance(elems, list):
        contents = []
        for el in elems:
            if isinstance(el, dict):
                c = el.get("content")
                if c:
                    contents.append(str(c))
        if contents:
            parts.append(" ".join(contents))

    # Fallback: body (trimmed)
    body = a.get("body", "")
    if isinstance(body, str) and body.strip():
        parts.append(body[:2000])

    # Join only non-empty chunks
    text = " ".join(p.strip() for p in parts if p and str(p).strip())
    # strip inline html
    return clean_html(text)


# ---- Sync HTTP using requests ----
_session: requests.Session | None = None

def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(DEFAULT_HEADERS)
    return _session


def _fetch_article_content_sync(query: dict) -> dict | None:
    """
    Sync fetch using `requests`, with strong guards around JSON parsing.
    """
    s = _get_session()
    # tuple timeout: (connect, read)
    resp = s.get(CONTENT_URL, params=query, timeout=(5, 20))
    # Raise for 4xx/5xx so we see root cause
    resp.raise_for_status()

    # Ensure body exists and looks like JSON
    if not resp.text or not resp.text.strip():
        return None

    ct = resp.headers.get("content-type", "")
    if "json" not in ct.lower():
        snippet = resp.text[:200].replace("\n", " ")
        raise RuntimeError(f"Expected JSON, got {ct}. Body starts: {snippet!r}")

    try:
        return resp.json()
    except JSONDecodeError as e:
        snippet = resp.text[:200].replace("\n", " ")
        raise RuntimeError(f"JSON decode failed. Body starts: {snippet!r}") from e


# ---- Public API (keeps your async signature but uses requests under the hood) ----
async def suggestTags(req: SuggestRequest, suggester: TagSuggester):
    try:
        articleContent = req.text
        articleId = req.articleId

        # query article content if no text
        if articleId is not None and articleContent is None:
            # Build the query your Arc endpoint expects. Add `website` if required.
            params = {
                "query" : dumps({
                    "_id": articleId
                })
            }
            # Run sync requests call without blocking the event loop
            content = await run_in_threadpool(_fetch_article_content_sync, params)
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