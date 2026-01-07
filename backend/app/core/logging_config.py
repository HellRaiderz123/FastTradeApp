"""
Enhanced Structured Logging Configuration
"""

import logging
import logging.config
import json
from datetime import datetime
from typing import Any, Dict, Optional
import traceback
import uuid
from contextvars import ContextVar

# Context variable for request ID
request_id_var: ContextVar[str] = ContextVar('request_id', default='')


class StructuredFormatter(logging.Formatter):
    """
    Format logs as JSON for easy parsing
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        extra_data = getattr(record, 'extra_data', None)
        if extra_data is not None:
            log_data["extra"] = extra_data
        
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """
    Colored console formatter for development
    """
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        import sys

        def _sanitize(text: str) -> str:
            try:
                # Attempt cp1252-safe conversion on Windows consoles
                return text.encode('cp1252', 'replace').decode('cp1252')
            except Exception:
                # Fallback: strip non-ASCII
                return ''.join(ch if ord(ch) < 128 else '?' for ch in text)

        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Add request ID if available
        request_id = request_id_var.get()
        request_id_str = f" [req:{request_id[:8]}]" if request_id else ""
        
        # Sanitize message for non-UTF8 consoles
        msg = record.getMessage()
        if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
            msg = _sanitize(msg)

        formatted = (
            f"{color}{record.levelname:8s}{reset} | "
            f"{datetime.now().strftime('%H:%M:%S')}{request_id_str} | "
            f"{record.name:30s} | "
            f"{msg}"
        )
        
        if record.exc_info:
            formatted += f"\n{reset}" + self.formatException(record.exc_info)
        
        return formatted


def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
    log_file: str = "logs/app.log"
):
    """
    Setup logging configuration
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_logs: Use JSON format for logs (production)
        log_file: Path to log file
    """
    
    # Create logs directory if it doesn't exist
    import os
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    formatter_class = StructuredFormatter if json_logs else ColoredFormatter
    
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": formatter_class,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "filename": log_file,
                "encoding": "utf-8",
                "maxBytes": 10_000_000,  # 10MB
                "backupCount": 5
            }
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"]
        },
        "loggers": {
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },
            "sqlalchemy.engine": {
                "level": "WARNING",  # Don't log every SQL query
                "handlers": ["file"],
                "propagate": False
            }
        }
    }
    
    logging.config.dictConfig(logging_config)
    
    logger = logging.getLogger(__name__)
    logger.info(f"✅ Logging configured (level={log_level}, json={json_logs})")


def get_logger(name: str) -> logging.Logger:
    """Get logger with structured logging support"""
    return logging.getLogger(name)


def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs):
    """Log with additional context"""
    extra_data = {k: v for k, v in kwargs.items() if v is not None}
    
    log_func = getattr(logger, level.lower())
    log_func(message, extra={'extra_data': extra_data})


def set_request_id(request_id: Optional[str] = None):
    """Set request ID for current context"""
    if request_id is None:
        request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> str:
    """Get request ID from current context"""
    return request_id_var.get()


# Performance logging decorator
def log_performance(func):
    """Decorator to log function execution time"""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = (time.time() - start) * 1000  # ms
            
            log_with_context(
                logger, "INFO",
                f"{func.__name__} completed",
                duration_ms=round(duration, 2),
                function=func.__name__
            )
            
            return result
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            
            log_with_context(
                logger, "ERROR",
                f"{func.__name__} failed: {str(e)}",
                duration_ms=round(duration, 2),
                function=func.__name__,
                error=str(e)
            )
            raise
    
    return wrapper


# Error tracking
class ErrorTracker:
    """Track and aggregate errors"""
    
    def __init__(self):
        self.errors: Dict[str, list] = {}
    
    def track_error(
        self, 
        error_type: str,
        message: str,
        component: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Track an error"""
        error_key = f"{component}:{error_type}"
        
        if error_key not in self.errors:
            self.errors[error_key] = []
        
        self.errors[error_key].append({
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        })
        
        # Keep only last 100 errors per type
        if len(self.errors[error_key]) > 100:
            self.errors[error_key].pop(0)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary"""
        return {
            error_key: {
                "count": len(errors),
                "latest": errors[-1] if errors else None
            }
            for error_key, errors in self.errors.items()
        }
    
    def clear_errors(self):
        """Clear all tracked errors"""
        self.errors.clear()


# Global error tracker
error_tracker = ErrorTracker()
