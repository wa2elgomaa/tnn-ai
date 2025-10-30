from celery import Celery
from ..config import settings

celery_app = Celery(
    "tnn_ai",
    broker=settings.REDIS_HOST + ":" + settings.REDIS_PORT,
    backend=settings.REDIS_HOST + ":" + settings.REDIS_PORT,
)
celery_app.autodiscover_tasks(["app.workers"])
