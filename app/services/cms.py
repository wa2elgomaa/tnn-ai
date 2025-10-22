from __future__ import annotations
import re
from typing import Dict, List
from jsonmerge import merge
from starlette.concurrency import run_in_threadpool

import requests
from json import JSONDecodeError, dumps
from ..utils.helpers import clean_html, deep_merge
from ..config.settings import settings

CONTENT_URL = f"{settings.CMS_BASE_URL}" f"{settings.ARTICLE_API}"

# 🔐 Adjust these to your ArcXP setup (site key, optional API key, etc.)
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {settings.CMS_TOKEN}",
}
# If your endpoint requires query params like `website`, add them when you build `query`.


# ---- Sync HTTP using requests ----
_session: requests.Session | None = None


def article_text(a: dict, limit: int = 0, useHeadlines: bool = False) -> str:
    """
    Build compact, high-signal text from the ArcXP content JSON.
    """
    # normalize the data if draft API provided
    responseType = a.get("type")
    if responseType == "DRAFT":
        a = a.get("ans")
        a["_id"] = a.get("document_id") or ""

    parts: list[str] = (
        [
            a.get("headlines", {}).get("basic", "") or "",
            a.get("subheadlines", {}).get("basic", "") or "",
            a.get("taxonomy", {}).get("primary_section", {}).get("name", "") or "",
        ]
        if useHeadlines
        else []
    )

    # Merge content from content_elements (if any)
    elems = a.get("content_elements", [])
    contents = []
    if isinstance(elems, list) and not useHeadlines and limit > 0:
        for el in elems:
            if isinstance(el, dict):
                c = el.get("content")
                if c:
                    contents.append(str(c))

    if len(contents) > 0:
        # select limit text only else generate based on the headline & subheadline
        content = " ".join(contents)[:limit]
        parts.append(content)

    # Join only non-empty chunks
    text = " ".join(p.strip() for p in parts if p and str(p).strip())
    # strip inline html
    return clean_html(text)


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(DEFAULT_HEADERS)
    return _session


def fetch_article_content(query: dict) -> dict | None:
    """
    Sync fetch using `requests`, with strong guards around JSON parsing.
    """
    s = _get_session()
    # tuple timeout: (connect, read)
    resp = s.get(
        CONTENT_URL.format(articleId=query["articleId"] or ""),
        params=query,
        timeout=(5, 20),
    )
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


def autoTagArticleBody(
    articleBody: dict = {}, tags: List[Dict["slug":str, "text":str]] = []
) -> dict:
    content_elements = articleBody.get("ans", {}).get("content_elements", [])
    tags_inserted = []
    if len(content_elements) > 0:
        for elem in content_elements:
            if elem.get("type") != "text":
                continue

            text = elem.get("content", "")

            for tag in tags:
                tag_name = tag.get("text")
                tag_slug = tag.get("slug")
                if not tag_name or not tag_slug or tag_slug in tags_inserted:
                    continue

                # Use regex with word boundaries for exact match (case-insensitive)
                pattern = re.compile(rf"\b({re.escape(tag_name)})\b", re.IGNORECASE)

                # Replace only the first match
                new_text, count = pattern.subn(
                    rf'<a href="{settings.CDN_DOMAIN}/tags/{tag_slug}" class="tag-link">\1</a>',
                    text,
                    count=1,
                )

                if count > 0:
                    text = new_text  # Update text only if we made a substitution

            elem["content"] = text  # Update back to content_elements
            tags_inserted.append(tag_slug)

    return articleBody


async def update_article_content(articleId: str, updates: dict) -> dict | None:
    """
    Update the article content in the CMS.
    """
    s = _get_session()

    articleBody = await run_in_threadpool(
        fetch_article_content, {"articleId": articleId}
    )
    # merge article body with updates dict
    articleBody = autoTagArticleBody(
        articleBody, updates.get("taxonomy", {}).get("tags", [])
    )
    updates = deep_merge(articleBody, {"ans": updates})
    payload = dumps(updates)

    resp = s.put(CONTENT_URL.format(articleId=articleId), data=payload)
    resp.raise_for_status()
    return resp.json()
