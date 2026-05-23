"""Event parsing, token accounting, and rate-limit tracking.

Implements SPEC §10.4 (Emitted Runtime Events) and §13.5 (Token Accounting).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from maestro.agent.base import AgentEvent, AgentEventType, TokenUsage

logger = logging.getLogger(__name__)

# Common field names for token extraction
_INPUT_TOKEN_FIELDS = ("input_tokens", "inputTokens", "prompt_tokens", "promptTokens")
_OUTPUT_TOKEN_FIELDS = ("output_tokens", "outputTokens", "completion_tokens", "completionTokens")
_TOTAL_TOKEN_FIELDS = ("total_tokens", "totalTokens", "total_token_usage")


def extract_token_usage(payload: dict[str, Any]) -> TokenUsage | None:
    """Extract token usage from an agent event payload.

    Per SPEC §13.5: extract input/output/total token counts leniently from
    common field names. Prefer absolute thread totals when available.

    Args:
        payload: The agent event payload dict.

    Returns:
        TokenUsage if token fields are found, None otherwise.
    """
    # Look for nested usage object first
    usage_data = payload.get("usage") or payload.get("tokenUsage") or payload
    if not isinstance(usage_data, dict):
        return None

    input_tokens = _find_field(usage_data, _INPUT_TOKEN_FIELDS)
    output_tokens = _find_field(usage_data, _OUTPUT_TOKEN_FIELDS)
    total_tokens = _find_field(usage_data, _TOTAL_TOKEN_FIELDS)

    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    return TokenUsage(
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        total_tokens=total_tokens or 0,
    )


def _find_field(data: dict[str, Any], field_names: tuple[str, ...]) -> int | None:
    """Find the first matching field in a dict, returning its int value."""
    for name in field_names:
        if name in data:
            value = data[name]
            if isinstance(value, (int, float)):
                return int(value)
    return None


def extract_rate_limit(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract rate-limit payload from an agent event.

    Args:
        payload: The agent event payload dict.

    Returns:
        Rate-limit dict if found, None otherwise.
    """
    for key in ("rateLimit", "rate_limit", "rateLimits", "rate_limits"):
        if key in payload:
            return payload[key]
    return None


def parse_agent_event(raw: dict[str, Any]) -> AgentEvent:
    """Parse a raw agent event dict into an AgentEvent.

    Args:
        raw: Raw event dict from the agent protocol.

    Returns:
        Parsed AgentEvent.
    """
    event_type_str = raw.get("event", raw.get("type", "other_message"))

    # Map string to enum
    try:
        event_type = AgentEventType(event_type_str)
    except ValueError:
        event_type = AgentEventType.OTHER_MESSAGE

    # Parse timestamp
    timestamp_str = raw.get("timestamp")
    if timestamp_str:
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)
    else:
        timestamp = datetime.now(timezone.utc)

    # Extract token usage
    usage = extract_token_usage(raw)

    # Extract session_id
    session_id = raw.get("session_id") or raw.get("sessionId")

    # Extract PID
    pid = raw.get("codex_app_server_pid") or raw.get("pid")
    if pid is not None:
        pid = str(pid)

    return AgentEvent(
        event_type=event_type,
        timestamp=timestamp,
        payload=raw,
        usage=usage,
        session_id=session_id,
        codex_app_server_pid=pid,
    )


def parse_json_line(line: str) -> dict[str, Any] | None:
    """Parse a single newline-delimited JSON line.

    Args:
        line: A line of JSON text.

    Returns:
        Parsed dict, or None if the line is empty or invalid.
    """
    line = line.strip()
    if not line:
        return None
    try:
        result = json.loads(line)
        if isinstance(result, dict):
            return result
        return None
    except json.JSONDecodeError:
        logger.debug("Failed to parse JSON line: %s", line[:100])
        return None
