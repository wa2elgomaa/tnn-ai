import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "./logs")
LOG_JSON = os.getenv("LOG_JSON", "false").lower() == "true"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

os.makedirs(LOG_DIR, exist_ok=True)


def _setup_handler_json() -> logging.Handler:
    """Configure JSON log handler for structured logs."""
    handler = RotatingFileHandler(LOG_FILE, maxBytes=10_000_000, backupCount=5)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        json_ensure_ascii=False,
    )
    handler.setFormatter(formatter)
    return handler


def _setup_handler_pretty() -> logging.Handler:
    """Configure human-readable console handler."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    return handler


def _setup_logger(name: str) -> logging.Logger:
    """Initialize and return a configured logger."""
    logger = logging.getLogger(name)

    if logger.handlers:
        # Prevent double handlers when re-imported
        return logger

    logger.setLevel(LOG_LEVEL)

    if LOG_JSON:
        handler = _setup_handler_json()
        logger.addHandler(handler)
    else:
        handler_stream = _setup_handler_pretty()
        handler_file = RotatingFileHandler(LOG_FILE, maxBytes=10_000_000, backupCount=5)
        handler_file.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler_stream)
        logger.addHandler(handler_file)

    logger.propagate = False
    logger.debug(f"Logger initialized for {name}")
    return logger


def get_logger(name: str) -> logging.Logger:
    """Public factory to get configured logger."""
    return _setup_logger(name)