"""Logging utilities for the application."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# Global logger instance
_logger: Optional[logging.Logger] = None
_log_file_path: Optional[Path] = None


def setup_logger(
    name: str = "notebook_lm_generation",
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    output_dir: Optional[Path] = None
) -> logging.Logger:
    """
    Set up and configure the application logger.

    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file name
        output_dir: Directory for log file output

    Returns:
        Configured logger instance
    """
    global _logger, _log_file_path

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with Rich formatting
    console_handler = RichHandler(
        console=Console(stderr=True),
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
    )
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        if output_dir:
            log_path = output_dir / log_file
        else:
            log_path = Path(log_file)

        _log_file_path = log_path

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

        # Log session start
        logger.info(f"Log session started at {datetime.now().isoformat()}")
        logger.info(f"Log file: {log_path.absolute()}")

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Get the configured logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


def get_log_file_path() -> Optional[Path]:
    """Get the current log file path."""
    return _log_file_path


class LogContext:
    """Context manager for logging operations with timing."""

    def __init__(self, operation: str, logger: Optional[logging.Logger] = None):
        self.operation = operation
        self.logger = logger or get_logger()
        self.start_time: Optional[datetime] = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()

        if exc_type is None:
            self.logger.info(f"Completed: {self.operation} ({duration:.2f}s)")
        else:
            self.logger.error(
                f"Failed: {self.operation} ({duration:.2f}s) - {exc_type.__name__}: {exc_val}"
            )

        return False  # Don't suppress exceptions


def log_step(step_name: str):
    """Decorator to log function execution as a step."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger()
            logger.info(f"Step: {step_name}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Step completed: {step_name}")
                return result
            except Exception as e:
                logger.error(f"Step failed: {step_name} - {e}")
                raise
        return wrapper
    return decorator
