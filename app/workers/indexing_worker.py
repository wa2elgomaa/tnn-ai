from app.core.celery_app import celery_app
from app.services.related_service import update_index


@celery_app.task(name="update_vector_index")
def update_vector_index(article_id: str):
    update_index(article_id)
    return {"indexed": article_id}
