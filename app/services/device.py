import torch

from app.core.logger import get_logger

logger = get_logger(__name__)


def get_device() -> torch.device:
    """
    Automatically selects the best available device:
    1. CUDA GPU (NVIDIA)
    2. MPS (Apple Silicon / macOS)
    3. CPU fallback
    """
    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"✅ Using CUDA GPU: {gpu_name}")
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        device = torch.device("mps")
        logger.info("✅ Using Apple MPS (Metal Performance Shaders) backend")
    else:
        device = torch.device("cpu")
        logger.info("⚙️  Using CPU (no GPU acceleration available)")

    return device
