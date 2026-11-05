"""Structured logging configuration for AIroom CLI."""

import json
import logging
import sys
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

from airoom.core.types import GlobalOptions


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (excluding standard LogRecord attributes)
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data, default=str)


def _get_log_level(verbose: int) -> int:
    """Map verbose count to logging level."""
    if verbose == 0:
        return logging.WARNING
    elif verbose == 1:
        return logging.INFO
    else:  # verbose >= 2
        return logging.DEBUG


def configure_logging(global_opts: GlobalOptions) -> None:
    """Configure global logging based on CLI options.

    Args:
        global_opts: Global CLI options containing verbose count and json_output flag.
    """
    root_logger = logging.getLogger()
    log_level = _get_log_level(global_opts.verbose)

    # Clear existing handlers to avoid duplicates on reconfiguration
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    if global_opts.json_output:
        # JSON formatter to stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
    else:
        # Rich handler for pretty console output
        console = Console(stderr=True)  # Use stderr for Rich output
        handler = RichHandler(
            console=console,
            show_time=False,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )

    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given module name.

    Args:
        name: Logger name, typically __name__.

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
