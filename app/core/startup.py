from app.core.logger import get_logger

logger = get_logger(__name__)


async def on_startup():
    logger.info("Startup event triggered")


async def on_shutdown():
    logger.info("Shutdown event triggered")
