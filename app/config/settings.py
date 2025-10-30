from pydantic import BaseModel
from pydantic.functional_validators import field_validator
import os
from pathlib import Path
from dotenv import load_dotenv

# 1) project root .env
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
# 2) current working directory fallback (e.g., when running from another path)
load_dotenv(override=False)

class Settings(BaseModel):
    CDN_DOMAIN: str = os.getenv("CDN_DOMAIN")
    TAGS_CSV: str = os.getenv("TAGS_CSV")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL")
    CHAT_MODEL: str = os.getenv("CHAT_MODEL")
    COMPLETION_MODEL: str = os.getenv("COMPLETION_MODEL")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL")
    TOKENIZERS_PARALLELISM: bool = (
        os.getenv("TOKENIZERS_PARALLELISM", "false").lower() == "true"
    )
    UVICORN_NO_HTTP_TOOLS: bool = os.getenv("UVICORN_NO_HTTP_TOOLS", "0").lower() == "1"
    UVICORN_NO_UVLOOP: bool = os.getenv("UVICORN_NO_UVLOOP", "0").lower() == "1"
    HF_HUB_OFFLINE: bool = os.getenv("HF_HUB_OFFLINE", "0").lower() == "1"
    USE_CROSS_ENCODER: bool = os.getenv("USE_CROSS_ENCODER", "false").lower() == "true"
    CROSS_ENCODER_MODEL: str = os.getenv("CROSS_ENCODER_MODEL")
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "./storage")
    DEVICE: str = os.getenv("DEVICE", "cpu")
    NORMALIZE_ARABIC: bool = os.getenv("NORMALIZE_ARABIC", "false").lower() == "true"
    CMS_BASE_URL: str = os.getenv("CMS_BASE_URL")
    ARTICLE_API: str = os.getenv("ARTICLE_API")
    CMS_TOKEN: str = os.getenv("CMS_TOKEN")
    REDIS_HOST: str = os.getenv("REDIS_HOST")
    REDIS_PORT: str = os.getenv("REDIS_PORT")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD")
    CACHE_TTL_SECONDS: int = os.getenv("CACHE_TTL_SECONDS", "300")
    TOPK_CANDIDATES: int = os.getenv("TOPK_CANDIDATES", 100)
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DBNAME: str = os.getenv("POSTGRES_DBNAME")
    DB_POOL_MAX: int = os.getenv("DB_POOL_MAX", 10)
    DATABASE_URL: str = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DBNAME}"
    )

    @field_validator("STORAGE_DIR")
    @classmethod
    def _ensure_storage(cls, v: str) -> str:
        os.makedirs(v, exist_ok=True)
        return v


settings = Settings()
