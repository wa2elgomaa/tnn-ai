from app.core.celery_app import celery_app
from app.services.video_service import generate_video_script

@celery_app.task(name="generate_video_script")
def generate_video_script_task(article_id: str, content: str):
    script = generate_video_script(content)
    return {"article_id": article_id, "script": script}
