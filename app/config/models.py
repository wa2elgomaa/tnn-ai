from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Any

class SuggestRequest(BaseModel):
    text: Optional[str] = Field(None, description="Article text (title + body or summary)")
    articleId: str = Field(None, description="Article id")
    k: int = Field(5, ge=1, le=50, description="How many tag suggestions to return")
    min_score: float = Field(0.2, ge=-1.0, le=1.0, description="Minimum cosine score to include")
    use_reranker: Optional[bool] = Field(None, description="Override server default to use cross-encoder reranker")

class TagOut(BaseModel):
    slug: str
    name: str
    url: Optional[str] = None
    description: Optional[str] = None
    score: float
    reason: Optional[str] = None

class SuggestResponse(BaseModel):
    suggestions: List[TagOut]
    meta: Optional[Any] = None

class FeedbackItem(BaseModel):
    article_id: str
    text_hash: str
    slug: str
    label: Literal["like","dislike"]
    score: float | None = None
    reason: str | None = None

class FeedbackBatch(BaseModel):
    items: List[FeedbackItem]
