"""Structured logging configuration with structlog."""

import sys
import structlog
from pathlib import Path


def configure_logging(
    level: str = "INFO",
    json_logs: bool = False,
    log_file: str | None = None
):
    """
    Configure structured logging for OpsPilot.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_logs: Output logs as JSON (machine-readable)
        log_file: Optional file path to write logs to
    """
    
    processors = [
        # Add log level
        structlog.stdlib.add_log_level,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add context
        structlog.contextvars.merge_contextvars,
        # Stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if json_logs:
        # JSON output for production/parsing
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Human-readable console output
        processors.extend([
            structlog.dev.ConsoleRenderer(
                colors=sys.stdout.isatty(),
                exception_formatter=structlog.dev.plain_traceback,
            )
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog.stdlib.logging, level.upper(), structlog.stdlib.logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    
    # Also configure file logging if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add file handler
        import logging
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(getattr(logging, level.upper()))
        logging.root.addHandler(file_handler)


def get_logger(name: str | None = None):
    """Get a structured logger instance."""
    return structlog.get_logger(name)
