# webhook consumer
from app.core.celery_app import celery_app
from app.workers import embeddings_worker, tag_worker, indexing_worker

@celery_app.task(name="handle_cms_webhook")
def handle_cms_webhook(event: dict):
    article_id = event["article_id"]
    content = event.get("content", "")
    embeddings_worker.generate_embeddings.delay(article_id, content)
    tag_worker.suggest_tags_async.delay(article_id, content)
    indexing_worker.update_vector_index.delay(article_id)
    return {"processed": article_id}
