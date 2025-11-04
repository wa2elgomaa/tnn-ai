from app.core.celery_app import celery_app
from app.services.suggest_service import suggest_tags


@celery_app.task(name="suggest_tags_async")
def suggest_tags_async(article_id: str, content: str):
    tags = suggest_tags(content)
    # save back to DB or CMS
    return {"article_id": article_id, "tags": tags}
