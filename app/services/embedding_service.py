"""
Embeddings Service
------------------
Provides centralized access to text embeddings using a preloaded model.
This service is initialized once at app startup and injected into request handlers.
"""

from typing import List, Union
from app.core.logger import get_logger
import torch
from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)


class EmbeddingsService:
    def __init__(self):
        # initialize DB, clients, etc.
        pass
    """
    Wrapper around an embedding model (e.g., all-MiniLM-L6-v2, openai/gpt-embedding-3-large).
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def load(self):
        """
        Loads the embedding model into memory.
        """
        try:
            logger.info(f"Loading embeddings model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info("✅ Embedding model loaded successfully.")
        except Exception as e:
            logger.exception(f"⚠️ Failed to load embedding model: {e}")
            raise RuntimeError(f"Failed to load embeddings model: {e}")

    async def embed(self, texts: Union[str, List[str]]) -> List[float]:
        """
        Generate embeddings for one or multiple texts.
        """
        if self.model is None:
            raise RuntimeError("Embedding model not loaded. Call load() first.")

        # Normalize to list
        if isinstance(texts, str):
            texts = [texts]

        try:
            embeddings = self.model.encode(texts, convert_to_tensor=True)
            return embeddings.tolist()
        except Exception as e:
            logger.exception(f"Error generating embeddings: {e}")
            raise


# ---------- Global Lifecycle Helpers ----------


async def preload_embeddings(app):
    """
    Called once at FastAPI startup to preload model.
    """
    try:
        service = EmbeddingsService()
        service.load()
        app.state.embeddings = service
        logger.info("✅ EmbeddingsService preloaded and attached to app.state")
    except Exception as e:
        logger.error(f"Failed to preload embeddings: {e}")
