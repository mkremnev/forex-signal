"""Configuration for structured logging."""

import logging
import json
from datetime import datetime
from typing import Dict, Any
import os


class StructuredFormatter(logging.Formatter):
    """Custom formatter to output logs in JSON format."""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Add extra fields if present
        if hasattr(record, 'event_type'):
            log_entry['event_type'] = record.event_type
        if hasattr(record, 'symbol'):
            log_entry['symbol'] = record.symbol
        if hasattr(record, 'timeframe'):
            log_entry['timeframe'] = record.timeframe
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO", log_file: str = "logs/agent.log"):
    """
    Set up structured logging for the application.
    """
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Create file handler with structured formatter
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(StructuredFormatter())

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter())

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Prevent duplicate logs from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)