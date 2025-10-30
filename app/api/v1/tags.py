from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, Depends
from typing import Dict, Optional
import time

from ...config.settings import settings
from ...models.schemas import SuggestRequest, SuggestResponse, TagOut
from ...services.tags import TagService
from ...services.cache import init_cache, close_cache
from ...core.logger import get_logger

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_cache()
    yield
    # Shutdown (nothing to clean up explicitly)
    await close_cache()


async def preload_action():
    try:
        print("✅ Tags preloaded successfully.")
    except Exception as e:
        print(f"⚠️ Preload failed: {e}")


tags_router = APIRouter(lifespan=lifespan, on_startup=[preload_action])


@tags_router.post("/suggest", response_model=SuggestResponse)
async def suggest(
    req: SuggestRequest, service: TagService = Depends(TagService)
) -> SuggestResponse:
    t0 = time.time()
    logger.info(f"Suggesting tags for articleId: {req.articleId}")
    items, meta = await service.suggestTags(req)
    dt = time.time() - t0
    return SuggestResponse(
        data=[TagOut(**i) for i in items], meta={"elapsed_ms": int(dt * 1000), **meta}
    )


@tags_router.get("/suggest/{articleId}", response_model=SuggestResponse)
async def suggest(
    articleId: str,
    limit: int = 5,
    use_headlines: bool = True,
    min_score: float = 0.2,
    use_reranker: Optional[bool] = None,
    cursor: Optional[str] = None,
    words_limit: Optional[int] = 0,
    offset: Optional[int] = 0,
    widen: Optional[bool] = False,
    exclude_slugs: Optional[list[str]] = [],
    service: TagService = Depends(TagService),
) -> SuggestResponse:
    req = SuggestRequest(
        articleId=articleId,
        limit=limit,
        min_score=min_score,
        use_reranker=use_reranker,
        useHeadlines=use_headlines,
        words_limit=words_limit,
        cursor=cursor,
        offset=offset,
        widen=widen,
        exclude_slugs=exclude_slugs,
    )
    items, meta = await service.suggestTags(req)
    return SuggestResponse(
        data=[TagOut(**i) for i in items], meta=meta
    )


@tags_router.post("/reload")
async def reload_index(
    service: TagService = Depends(TagService),
) -> Dict[str, str]:
    return await service.reloadIndex()
