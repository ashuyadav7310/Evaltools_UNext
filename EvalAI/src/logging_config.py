# src/logging_config.py
"""
Centralised structured logging using loguru.

Features:
- Clean console logs for users
- Detailed log files for debugging (rotated & compressed)
- Captures all stdlib logging into loguru
- Supports multi-threaded & multi-process execution
"""

import logging
import os
from typing import Optional
from loguru import logger
from config.settings import LOGS_DIR

_LOGGING_INITIALISED = False


def _get_log_file_path() -> str:
    os.makedirs(LOGS_DIR, exist_ok=True)
    return os.path.join(LOGS_DIR, "evaluator.log")


class InterceptHandler(logging.Handler):
    """
    Redirect stdlib logging to loguru seamlessly.
    """
    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Attempt to map the stdlib level name to a loguru level
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        # walk back until we leave logging module frames
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # Use .opt to preserve exception info if any
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(level: str = "INFO") -> None:
    """
    Initialise application logging once.
    Safe to call repeatedly.
    """
    global _LOGGING_INITIALISED
    if _LOGGING_INITIALISED:
        return

    logger.remove()

    # Console: concise and stable (do not reference extra[...] fields that may be missing)
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=level,
        format="<green>{time:HH:mm:ss}</green> | "
               "<level>{level: <7}</level> | "
               "<cyan>{name}</cyan> | "
               "<level>{message}</level>",
        enqueue=False,
    )

    # Detailed rotating file log for debugging
    log_file = _get_log_file_path()
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "PID={process} TID={thread} | "
            "{name}:{function}:{line} | {message}"
        ),
        enqueue=True,
    )

    # Capture stdlib logging
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    _LOGGING_INITIALISED = True
    # bind a helpful name for the bootstrap message and use loguru '{}' formatting
    logger.bind(name="bootstrap").info("Logging initialised → {}", log_file)


def get_logger(scope: Optional[str] = None):
    """
    Get a scoped logger:
        log = get_logger("pipeline")
        log.info("Evaluation started")
    """
    # Bind both name and scope for compatibility with formatters that use {name}
    scope_name = scope or "app"
    return logger.bind(name=scope_name, scope=scope_name)
