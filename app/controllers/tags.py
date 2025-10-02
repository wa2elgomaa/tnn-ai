from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI
from typing import Dict, Optional
import time

from ..config.settings import settings
from ..config.models import SuggestRequest, SuggestResponse, TagOut
from ..utils.tagger import TagSuggester
from ..services.tags import suggestTags
from ..services.cache import init_cache, close_cache

suggester = TagSuggester()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    suggester.load(force_rebuild=False)
    await init_cache()
    yield
    # Shutdown (nothing to clean up explicitly)
    await close_cache()


tags_router = APIRouter(prefix="/tags", lifespan=lifespan)


@tags_router.get("/health")
async def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "model": suggester.model_name,
        "tags_csv": settings.TAGS_CSV,
        "count": str(len(suggester.tags)),
    }


@tags_router.post("/suggest", response_model=SuggestResponse)
async def suggest(req: SuggestRequest) -> SuggestResponse:
    t0 = time.time()
    items, meta = await suggestTags(req, suggester)
    dt = time.time() - t0
    return SuggestResponse(
        data=[TagOut(**i) for i in items], meta={"elapsed_ms": int(dt * 1000), **meta}
    )


@tags_router.get("/suggest/{articleId}", response_model=SuggestResponse)
async def suggest(
    articleId: str,
    limit: int = 5,
    min_score: float = 0.2,
    use_reranker: Optional[bool] = None,
    cursor: Optional[str] = None,
    offset: Optional[int] = 0,
    widen: Optional[bool] = False,
    exclude_slugs: Optional[list[str]] = [],
) -> SuggestResponse:
    req = SuggestRequest(
        articleId=articleId,
        limit=limit,
        min_score=min_score,
        use_reranker=use_reranker,
        cursor=cursor,
        offset=offset,
        widen=widen,
        exclude_slugs=exclude_slugs,
    )
    response = await suggestTags(req, suggester)
    return response


@tags_router.post("/reload")
async def reload_index() -> Dict[str, str]:
    suggester.reload()
    return {"status": "reloaded", "count": str(len(suggester.tags))}


def get():
    return tags_router
