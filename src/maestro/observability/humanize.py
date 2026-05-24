"""Humanized agent event summaries for observability output.

Implements SPEC §13.6 — OPTIONAL human-readable summaries of raw agent protocol events.
These are observability-only and must not affect orchestrator logic.
"""

from __future__ import annotations

from typing import Any


def humanize_event(event_type: str, payload: dict[str, Any]) -> str:
    """Convert a raw agent event into a human-readable summary.

    Per SPEC §13.6: observability-only output; orchestrator logic must not
    depend on these strings.

    Args:
        event_type: The event type string (e.g. "session_started", "turn_completed").
        payload: The raw event payload dict.

    Returns:
        A human-readable summary string.
    """
    handlers: dict[str, Any] = {
        "session_started": _humanize_session_started,
        "turn_completed": _humanize_turn_completed,
        "turn_failed": _humanize_turn_failed,
        "approval_auto_approved": _humanize_approval_auto_approved,
        "notification": _humanize_notification,
    }

    handler = handlers.get(event_type)
    if handler:
        return handler(payload)
    return f"Agent event: {event_type}"


def _humanize_session_started(payload: dict[str, Any]) -> str:
    session_id = payload.get("session_id", "unknown")
    return f"Session started (session_id={session_id})"


def _humanize_turn_completed(payload: dict[str, Any]) -> str:
    turn = payload.get("turn", "unknown")
    return f"Turn completed (turn={turn})"


def _humanize_turn_failed(payload: dict[str, Any]) -> str:
    turn = payload.get("turn", "unknown")
    error = payload.get("error", "unknown error")
    return f"Turn failed (turn={turn}, error={error})"


def _humanize_approval_auto_approved(payload: dict[str, Any]) -> str:
    tool = payload.get("tool_name") or payload.get("tool", "unknown")
    return f"Approval auto-approved (tool={tool})"


def _humanize_notification(payload: dict[str, Any]) -> str:
    message = payload.get("message", "")
    # Truncate long messages for readability
    if len(message) > 120:
        message = message[:117] + "..."
    return f"Notification: {message}"