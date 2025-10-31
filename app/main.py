from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logger import get_logger
from .api.v1.tags import tags_router

# from .api.v1.feedback import feedback_router
# from .api.v1.chat import chat_router
from .api.v1.cms import cms_router
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Preloading singelton services")
    yield
    logger.info("Shutting down singelton services")


# Application Instance
app = FastAPI(title="tnn-api", version="1.0.0", lifespan=lifespan)

# middle wares and CORS enable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routers 
app.include_router(tags_router, prefix="/api/v1/tags", tags=["Tags"])
app.include_router(cms_router, prefix="/api/v1/cms", tags=["CMS"])
# app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])
# app.include_router(feedback_router, prefix="/api/v1/feedback", tags=["Feedback"])
