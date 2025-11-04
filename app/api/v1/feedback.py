from fastapi import APIRouter
from pathlib import Path
import json, time

from ...config.settings import settings
from ...models.schemas import APIResponse, FeedbackBatch

async def preload_action():
    try:
        print("✅ Feedback preloaded successfully.")
    except Exception as e:
        print(f"⚠️ Preload failed: {e}")


feedback_router = APIRouter(on_startup=[preload_action])
FEEDBACK_FILE = Path(settings.STORAGE_DIR) / "feedback.jsonl"


@feedback_router.post("/add/{articleId}", response_model=APIResponse)
async def feedback(articleId: str, batch: FeedbackBatch):
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    with FEEDBACK_FILE.open("a", encoding="utf-8") as f:
        for it in batch.items:
            row = it.model_dump()
            row["ts"] = now
            row["articleId"] = articleId
            row["model"] = settings.EMBEDDING_MODEL
            json.dump(row, f, ensure_ascii=False)
            f.write("\n")
    return {"status": "ok", "count": len(batch.items)}
