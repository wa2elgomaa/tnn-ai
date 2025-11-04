# embed and index
from app.core.celery_app import celery_app
from app.services.embedding_service import EmbeddingsService


@celery_app.task(name="generate_embeddings")
def generate_embeddings(article_id: str, content: str):
    embeddings_service = EmbeddingsService()
    vector = embeddings_service.embed_text(content)
    # store to DB or push to index queue
    return {"article_id": article_id, "status": "ok"}
