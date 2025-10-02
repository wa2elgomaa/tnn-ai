


from contextlib import asynccontextmanager
from ..utils.helpers import deep_merge
from json import dumps
from fastapi import APIRouter, FastAPI, Request
from typing import Dict, Optional
import time
import traceback
from ..config.settings import settings
from ..config.models import APIResponse
from ..utils.tagger import TagSuggester
from ..services.cms import update_article_content, fetch_article_content
suggester = TagSuggester()

    
cms_router = APIRouter(prefix="/cms")

@cms_router.put("/update/{articleId}", response_model=APIResponse)
async def update(articleId: str, request: Request) -> APIResponse:
    t0 = time.time()
    updates = await request.json()
    print(f"Updating article: {articleId} with updates: {updates}")
    try:
        await update_article_content(articleId, updates)
        dt = time.time() - t0
        return APIResponse(
            data={"message": "Article updated successfully", "success" : True },
            meta={"elapsed_ms": int(dt * 1000)}
        )
    except Exception as e:
        dt = time.time() - t0
        print(f'error {traceback.format_exc()}')
        return APIResponse(
            data={"message": "Article updated failed", "success" : False},
            meta={"elapsed_ms": int(dt * 1000), "error": str(e)}
        )

def get():
    return cms_router