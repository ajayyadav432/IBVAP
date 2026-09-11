import logging
import re
import sys
from typing import Any, Dict

# Regex pattern for sanitizing common secret keys and RTSP credentials
SECRET_PATTERNS = [
    (re.compile(r'(rtsp://[^:]+:)([^@]+)(@)', re.IGNORECASE), r'\1******\3'),
    (re.compile(r'("?(?:password|secret|api_key|token|access_token)"?\s*[:=]\s*"?[^",\s]+"?)(?!")', re.IGNORECASE), r'"password": "******"'),
]


def sanitize_log_message(message: str) -> str:
    """Mask credentials and sensitive strings from log messages."""
    sanitized = str(message)
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class StructuredFormatter(logging.Formatter):
    """
    Structured formatter that outputs formatted log lines with channel categorization.
    """
    def format(self, record: logging.LogRecord) -> str:
        channel = getattr(record, "channel", "SYSTEM")
        raw_msg = record.getMessage()
        sanitized_msg = sanitize_log_message(raw_msg)
        
        # Standard formatted time
        record.message = sanitized_msg
        record.asctime = self.formatTime(record, self.datefmt)
        
        # Format string: [TIMESTAMP] [LEVEL] [CHANNEL] message
        formatted = f"[{record.asctime}] [{record.levelname:7s}] [{channel:8s}] {sanitized_msg}"
        
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            formatted += f"\n{record.exc_text}"
        if record.stack_info:
            formatted += f"\n{self.formatStack(record.stack_info)}"
            
        return formatted


def setup_logger(name: str = "ibvap") -> logging.Logger:
    """Setup and return the global IBVAP structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = StructuredFormatter(datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    return logger


logger = setup_logger()


class ChannelLogger:
    """
    Helper to log with explicit subsystem channels (SYSTEM, API, DATABASE, etc.)
    """
    def __init__(self, channel: str):
        self.channel = channel
        self._logger = logger

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(msg, *args, extra={"channel": self.channel}, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(msg, *args, extra={"channel": self.channel}, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(msg, *args, extra={"channel": self.channel}, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(msg, *args, extra={"channel": self.channel}, **kwargs)


# Subsystem Loggers
sys_logger = ChannelLogger("SYSTEM")
api_logger = ChannelLogger("API")
db_logger = ChannelLogger("DATABASE")
camera_logger = ChannelLogger("CAMERA")
video_logger = ChannelLogger("VIDEO")
inference_logger = ChannelLogger("INFERENCE")
model_logger = ChannelLogger("MODEL")
