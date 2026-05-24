"""Structured logging helpers with issue/session context fields.

Implements SPEC §13.1 and §13.2.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, MutableMapping


class _ContextAdapter(logging.LoggerAdapter):
    """LoggerAdapter that prepends context fields to log messages in key=value format."""

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        extra = self.extra or {}
        ctx_parts = [f"{k}={v}" for k, v in extra.items() if v is not None]
        prefix = " ".join(ctx_parts)
        if prefix:
            msg = f"{prefix} {msg}"
        return msg, kwargs


def create_issue_logger(issue_id: str, issue_identifier: str) -> logging.LoggerAdapter:
    """Create a logger adapter with issue context fields per SPEC §13.1.

    Args:
        issue_id: Stable tracker-internal issue ID.
        issue_identifier: Human-readable issue key (e.g. ABC-100).

    Returns:
        LoggerAdapter that prepends ``issue_id=... issue_identifier=...`` to log messages.
    """
    logger = logging.getLogger("maestro.issue")
    return _ContextAdapter(logger, {"issue_id": issue_id, "issue_identifier": issue_identifier})


def create_session_logger(session_id: str) -> logging.LoggerAdapter:
    """Create a logger adapter with session context field per SPEC §13.1.

    Args:
        session_id: The coding-agent session ID.

    Returns:
        LoggerAdapter that prepends ``session_id=...`` to log messages.
    """
    logger = logging.getLogger("maestro.session")
    return _ContextAdapter(logger, {"session_id": session_id})


class _NonCrashingHandler(logging.Handler):
    """Log handler that catches exceptions during emit to prevent crashing per SPEC §13.2."""

    def __init__(self, target: logging.Handler) -> None:
        super().__init__()
        self._target = target

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._target.emit(record)
        except Exception:
            # Emit a warning to stderr (fallback sink) per SPEC §13.2
            try:
                sys.stderr.write(
                    f"[maestro] WARNING: log sink {self._target.__class__.__name__} "
                    f"failed for record: {record.getMessage()}\n"
                )
            except Exception:
                pass  # Absolute last resort — cannot crash

    def close(self) -> None:
        try:
            self._target.close()
        except Exception:
            pass
        super().close()


def wrap_handler_for_safety(handler: logging.Handler) -> _NonCrashingHandler:
    """Wrap a log handler with non-crashing behaviour per SPEC §13.2.

    Args:
        handler: The underlying log handler to protect.

    Returns:
        A handler that catches emit failures and warns via stderr.
    """
    return _NonCrashingHandler(handler)
