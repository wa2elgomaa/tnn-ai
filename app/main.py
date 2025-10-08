from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .controllers.tags import get as get_tags_router
from .controllers.feedback import get as get_feedback_router
from .controllers.cms import get as get_cms_router
from .controllers.chat import get as get_chat_router



# APIs routers
app = FastAPI(title="tnn-api", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(get_tags_router())
app.include_router(get_feedback_router())
app.include_router(get_cms_router())
app.include_router(get_chat_router())