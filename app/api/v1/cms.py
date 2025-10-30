from fastapi import APIRouter, Request, Depends
import time
import traceback
from ...models.schemas import APIResponse
from ...services.cms import CMSService


async def preload_action():
    try:
        print("✅ CMS preloaded successfully.")
    except Exception as e:
        print(f"⚠️ Preload failed: {e}")

cms_router = APIRouter(on_startup=[preload_action])


@cms_router.put("/update/{articleId}", response_model=APIResponse)
async def update(
    articleId: str,
    request: Request,
    service: CMSService = Depends(CMSService),
) -> APIResponse:
    t0 = time.time()
    updates = await request.json()
    print(f"Updating article: {articleId} with updates: {updates}")
    try:
        await service.update_article_content(articleId, updates)
        dt = time.time() - t0
        return APIResponse(
            data={"message": "Article updated successfully", "success": True},
            meta={"elapsed_ms": int(dt * 1000)},
        )
    except Exception as e:
        dt = time.time() - t0
        print(f"error {traceback.format_exc()}")
        return APIResponse(
            data={"message": "Article updated failed", "success": False},
            meta={"elapsed_ms": int(dt * 1000), "error": str(e)},
        )
