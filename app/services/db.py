# app/db/service.py
from __future__ import annotations

import os
import re
import html
import json
import hashlib
from typing import Any, Iterable, Optional, Tuple, List, Callable

from ..config.settings import settings
import psycopg
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector, Vector


# Pool (singleton)
_pool: AsyncConnectionPool | None = None


def _configure_conn(conn: psycopg.Connection) -> None:
    # Runs for every new pooled connection
    register_vector(conn)  # pgvector adapter
    # You can set session settings here if needed:
    # with conn.cursor() as cur:
    #     cur.execute("SET search_path = public;")


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=settings.DATABASE_URL,
            min_size=1,
            max_size=int(settings.DB_POOL_MAX),
            name="tnn-articles-db-pool",
            configure=_configure_conn,  # register pgvector on every connection
            timeout=10.0,
        )
        await _pool.open()
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# -----------------------------
# SQL helpers
# -----------------------------
def _split_sql(statements: str) -> List[str]:
    """
    Split SQL string on semicolons while respecting single-quoted strings and
    dollar-quoted blocks ($$...$$). Suitable for schema.sql/data.sql without functions.
    """
    parts, buf = [], []
    in_single = False
    in_dollar = False
    i = 0
    s = statements
    while i < len(s):
        ch = s[i]
        nxt = s[i + 1] if i + 1 < len(s) else ""

        if in_single:
            buf.append(ch)
            if ch == "'" and nxt != "'":  # end of single-quote ('' is escaped)
                in_single = False
            elif ch == "'" and nxt == "'":
                buf.append(nxt)
                i += 1
        elif in_dollar:
            buf.append(ch)
            if ch == "$" and nxt == "$":
                buf.append(nxt)
                i += 1
                in_dollar = False
        else:
            if ch == "'" and not in_single:
                in_single = True
                buf.append(ch)
            elif ch == "$" and nxt == "$" and not in_dollar:
                in_dollar = True
                buf.append(ch)
                buf.append(nxt)
                i += 1
            elif ch == ";":
                stmt = "".join(buf).strip()
                if stmt:
                    parts.append(stmt)
                buf = []
            else:
                buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


async def apply_sql_file(path: str) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    sql = open(path, "r", encoding="utf-8").read()
    stmts = _split_sql(sql)
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                for s in stmts:
                    await cur.execute(s)


# -----------------------------
# Article utilities
# -----------------------------
_A_RE = re.compile(r"<a [^>]*>(.*?)</a>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(s: str) -> str:
    if not s:
        return ""
    t = s
    t = re.sub(r"<\s*br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</p\s*>", "\n", t, flags=re.I)
    t = _A_RE.sub(r"\1", t)  # keep anchor text
    t = _TAG_RE.sub("", t)
    return html.unescape(t).strip()


def build_content_plain(content_elements: list[dict] | None) -> str:
    parts: List[str] = []
    for el in content_elements or []:
        typ = el.get("type")
        if typ in ("text", "header"):
            txt = html_to_text(el.get("content") or "")
            if txt:
                parts.append(txt)
    return "\n\n".join(parts).strip()


def canonicalize_text(title: str, dek: str, body: str) -> str:
    s = "\n".join([title or "", dek or "", body or ""])
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compute_text_hash(title: str, dek: str, body: str) -> str:
    return hashlib.sha1(canonicalize_text(title, dek, body).encode("utf-8")).hexdigest()


def _ts(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00"
    return s


async def upsert_article_json(data: dict) -> Tuple[int, str]:
    """
    Insert/Update an article row from full JSON payload.
    Returns (article_id, text_hash).
    """
    doc_id = data.get("_id")
    subtype = data.get("subtype")
    can_url = data.get("canonical_url")
    web_url = data.get("website_url") or can_url

    created_date = _ts(data.get("created_date"))
    display_date = _ts(data.get("display_date"))
    first_publish_date = _ts(data.get("first_publish_date"))
    publish_date = _ts(data.get("publish_date"))
    last_updated_date = _ts(data.get("last_updated_date"))

    headlines = data.get("headlines") or {}
    subheadlines = data.get("subheadlines") or {}
    description = data.get("description") or {}
    label = data.get("label") or {}
    content_elems = data.get("content_elements") or []
    promo_items = data.get("promo_items") if "promo_items" in data else None
    credits = data.get("credits") if "credits" in data else None
    taxonomy = data.get("taxonomy") if "taxonomy" in data else None

    title = (headlines or {}).get("basic", "")
    title_mobile = (headlines or {}).get("mobile", "")
    dek = (subheadlines or {}).get("basic", "")
    desc_basic = (description or {}).get("basic", "")

    content_plain = build_content_plain(content_elems)
    text_hash = compute_text_hash(title, dek, content_plain)

    payload = {
        "document_id": doc_id,
        "canonical_url": can_url,
        "website_url": web_url,
        "subtype": subtype,
        "created_date": created_date,
        "display_date": display_date,
        "first_publish_date": first_publish_date,
        "publish_date": publish_date,
        "last_updated_date": last_updated_date,
        "title": title,
        "title_mobile": title_mobile,
        "dek": dek,
        "description_basic": desc_basic,
        "content_plain": content_plain or None,
        "headlines": json.dumps(headlines, ensure_ascii=False),
        "subheadlines": json.dumps(subheadlines, ensure_ascii=False),
        "description": json.dumps(description, ensure_ascii=False),
        "label": json.dumps(label, ensure_ascii=False),
        "content_elements": json.dumps(content_elems, ensure_ascii=False),
        "promo_items": (
            json.dumps(promo_items, ensure_ascii=False)
            if promo_items is not None
            else None
        ),
        "credits": (
            json.dumps(credits, ensure_ascii=False) if credits is not None else None
        ),
        "taxonomy": (
            json.dumps(taxonomy, ensure_ascii=False) if taxonomy is not None else None
        ),
        "raw": json.dumps(data, ensure_ascii=False),
        "text_hash": text_hash,
    }

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO articles (
              document_id, canonical_url, website_url, subtype,
              created_date, display_date, first_publish_date, publish_date, last_updated_date,
              title, title_mobile, dek, description_basic, content_plain,
              headlines, subheadlines, description, label,
              content_elements, promo_items, credits, taxonomy, raw, text_hash
            ) VALUES (
              %(document_id)s, %(canonical_url)s, %(website_url)s, %(subtype)s,
              %(created_date)s::timestamptz, %(display_date)s::timestamptz, %(first_publish_date)s::timestamptz, %(publish_date)s::timestamptz, %(last_updated_date)s::timestamptz,
              %(title)s, %(title_mobile)s, %(dek)s, %(description_basic)s, %(content_plain)s,
              %(headlines)s::jsonb, %(subheadlines)s::jsonb, %(description)s::jsonb, %(label)s::jsonb,
              %(content_elements)s::jsonb, %(promo_items)s::jsonb, %(credits)s::jsonb, %(taxonomy)s::jsonb, %(raw)s::jsonb, %(text_hash)s
            )
            ON CONFLICT (document_id) DO UPDATE SET
              canonical_url      = EXCLUDED.canonical_url,
              website_url        = EXCLUDED.website_url,
              subtype            = EXCLUDED.subtype,
              last_updated_date  = COALESCE(EXCLUDED.last_updated_date, articles.last_updated_date),
              title              = EXCLUDED.title,
              title_mobile       = EXCLUDED.title_mobile,
              dek                = EXCLUDED.dek,
              description_basic  = EXCLUDED.description_basic,
              content_plain      = EXCLUDED.content_plain,
              headlines          = EXCLUDED.headlines,
              subheadlines       = EXCLUDED.subheadlines,
              description        = EXCLUDED.description,
              label              = EXCLUDED.label,
              content_elements   = EXCLUDED.content_elements,
              promo_items        = EXCLUDED.promo_items,
              credits            = EXCLUDED.credits,
              taxonomy           = EXCLUDED.taxonomy,
              raw                = EXCLUDED.raw,
              text_hash          = EXCLUDED.text_hash
            RETURNING id;
            """,
            payload,
        )
        row = await cur.fetchone()
        return int(row[0]), text_hash


# -----------------------------
# Embeddings & ANN queries
# -----------------------------
async def set_article_embedding(document_id: str, vec: Iterable[float]) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE articles SET embedding = %s WHERE document_id = %s",
            (Vector(list(vec)), document_id),
        )


async def set_tag_embedding(tag_set_code: str, slug: str, vec: Iterable[float]) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # resolve tag_set_id
        await cur.execute("SELECT id FROM tag_sets WHERE code = %s", (tag_set_code,))
        ts = await cur.fetchone()
        if not ts:
            raise ValueError(f"tag_set_code not found: {tag_set_code}")
        tsid = ts[0]
        await cur.execute(
            "UPDATE tags SET embedding = %s WHERE tag_set_id = %s AND slug = %s",
            (Vector(list(vec)), tsid, slug),
        )


async def topk_related_articles(
    qvec: Iterable[float], k: int = 10, exclude_document_id: Optional[str] = None
) -> List[dict]:
    """
    Cosine distance: smaller is closer. Convert to similarity score = 1 - distance.
    """
    pool = await get_pool()
    qvecv = Vector(list(qvec))
    sql = """
      SELECT document_id, title, canonical_url, website_url,
             (embedding <=> %s) AS dist
      FROM articles
      WHERE embedding IS NOT NULL {where_excl}
      ORDER BY embedding <=> %s
      LIMIT %s
    """
    where_excl = "AND document_id <> %s" if exclude_document_id else ""
    sql = sql.format(where_excl=where_excl)
    params = (
        (qvecv,)
        + ((exclude_document_id,) if exclude_document_id else tuple())
        + (qvecv, k)
    )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        rows = await cur.fetchall()
    out = []
    for r in rows:
        doc_id, title, can, web, dist = r
        score = 1.0 - float(dist) if dist is not None else None
        out.append(
            {
                "document_id": doc_id,
                "title": title,
                "canonical_url": can,
                "website_url": web,
                "score": score,
            }
        )
    return out


async def topk_tags_for_query(
    qvec: Iterable[float], tag_set_code: str, k: int = 10, min_score: float = 0.0
) -> List[dict]:
    pool = await get_pool()
    qvecv = Vector(list(qvec))
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT id FROM tag_sets WHERE code = %s", (tag_set_code,))
        ts = await cur.fetchone()
        if not ts:
            raise ValueError(f"tag_set_code not found: {tag_set_code}")
        tsid = ts[0]
        await cur.execute(
            """
            SELECT slug, name, description, url, (embedding <=> %s) AS dist
            FROM tags
            WHERE tag_set_id = %s AND active = true AND embedding IS NOT NULL
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (qvecv, tsid, qvecv, k),
        )
        rows = await cur.fetchall()
    out: List[dict] = []
    for slug, name, desc, url, dist in rows:
        score = 1.0 - float(dist) if dist is not None else None
        if score is None or score >= min_score:
            out.append(
                {
                    "slug": slug,
                    "name": name,
                    "description": desc,
                    "url": url,
                    "score": score,
                }
            )
    return out
