"""
Structured logging configuration.

Features:
- JSON logs (structlog) to stdout + rotating file
- Audit log for business events
- Request-ID contextvar binding
- PII/key redaction filter
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import re
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import structlog

# ── Context var for request-ID propagation ───────────────────────────────────
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# ── Redaction patterns ────────────────────────────────────────────────────────
_REDACT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token|bearer)\s*[:=]\s*\S+"),
    re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),      # base64 blobs (keys/tokens)
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),  # emails
]
_REDACT_REPLACEMENT = "[REDACTED]"


def redact(value: str) -> str:
    """Redact sensitive patterns from a string."""
    for pattern in _REDACT_PATTERNS:
        value = pattern.sub(_REDACT_REPLACEMENT, value)
    return value


def _redact_processor(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor that redacts sensitive values in the event dict."""
    for key in list(event_dict.keys()):
        if key in ("event", "_record"):
            continue
        val = event_dict[key]
        if isinstance(val, str):
            event_dict[key] = redact(val)
    return event_dict


def _add_request_id(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    event_dict["request_id"] = request_id_var.get()
    return event_dict


def configure_logging(log_level: str, log_file: str, audit_log_file: str,
                      max_bytes: int, backup_count: int) -> None:
    """
    Set up structlog + stdlib handlers.

    If the log directory is not writable (e.g. volume not mounted yet), we log
    a clear warning and fall back to stdout-only — the app keeps running.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # ── Stdlib root logger ────────────────────────────────────────────────────
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter("%(message)s")  # structlog renders JSON

    # stdout — always present
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # rotating app log — skipped gracefully if not writable
    def _try_add_file_handler(path: str, target_logger: logging.Logger) -> bool:
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
            fh.setFormatter(formatter)
            target_logger.addHandler(fh)
            return True
        except OSError as exc:
            print(
                f"[WARN] Cannot write log file {path}: {exc}. "
                "Falling back to stdout-only logging.",
                flush=True,
            )
            return False

    _try_add_file_handler(log_file, root_logger)

    # ── Audit logger ──────────────────────────────────────────────────────────
    audit_logger = logging.getLogger("audit")
    audit_logger.propagate = False
    if not _try_add_file_handler(audit_log_file, audit_logger):
        # Ensure audit events still flow to stdout via root logger propagation
        audit_logger.propagate = True

    # ── structlog configuration ───────────────────────────────────────────────
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_request_id,
            _redact_processor,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "contextkeeper") -> structlog.BoundLogger:
    return structlog.get_logger(name)


def get_audit_logger() -> structlog.BoundLogger:
    return structlog.get_logger("audit")

