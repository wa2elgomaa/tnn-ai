from fastapi import APIRouter
from pathlib import Path
import json, time

from ..config.settings import settings
from ..config.models import FeedbackBatch

feedback_router = APIRouter(prefix="/feedback")
FEEDBACK_FILE = Path(settings.STORAGE_DIR) / "feedback.jsonl"


@feedback_router.post("/add")
async def feedback(batch: FeedbackBatch):
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    with FEEDBACK_FILE.open("a", encoding="utf-8") as f:
        for it in batch.items:
            row = it.model_dump()
            row["ts"] = now
            row["model"] = settings.EMBEDDING_MODEL
            json.dump(row, f, ensure_ascii=False)
            f.write("\n")
    return {"status": "ok", "count": len(batch.items)}

def get():
    return feedback_router