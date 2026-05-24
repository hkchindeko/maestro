"""Token accounting utilities for delta tracking and live runtime.

Implements SPEC §13.5.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def compute_token_delta(current_total: int, last_reported_total: int) -> int:
    """Compute delta from absolute totals to avoid double-counting.

    Per SPEC §13.5: for absolute totals, track deltas relative to last reported totals.

    Args:
        current_total: Current absolute token total from agent update.
        last_reported_total: Last recorded absolute total.

    Returns:
        Positive delta if current > last_reported, otherwise 0.
    """
    if current_total > last_reported_total:
        return current_total - last_reported_total
    return 0


def extract_tokens_from_event(payload: dict[str, Any]) -> tuple[int, int, int]:
    """Extract input/output/total token counts leniently from event payload.

    Per SPEC §13.5: extract token counts leniently from common field names.

    Looks for ``input_tokens``, ``output_tokens``, ``total_tokens`` (or variants
    like ``inputTokens``, ``outputTokens``, ``totalTokens``) at the top level of
    the payload.

    Also checks nested dicts like ``usage``, ``token_usage``, ``total_token_usage``.

    Args:
        payload: Raw agent event payload dict.

    Returns:
        Tuple of (input_tokens, output_tokens, total_tokens).
    """
    # Top-level keys
    input_tokens = _coerce_int(payload.get("input_tokens") or payload.get("inputTokens"))
    output_tokens = _coerce_int(payload.get("output_tokens") or payload.get("outputTokens"))
    total_tokens = _coerce_int(payload.get("total_tokens") or payload.get("totalTokens"))

    # If not found at top level, check common nested locations
    if not any([input_tokens, output_tokens, total_tokens]):
        for nested_key in ("usage", "token_usage", "total_token_usage"):
            nested = payload.get(nested_key)
            if isinstance(nested, dict):
                input_tokens = _coerce_int(
                    nested.get("input_tokens") or nested.get("inputTokens")
                )
                output_tokens = _coerce_int(
                    nested.get("output_tokens") or nested.get("outputTokens")
                )
                total_tokens = _coerce_int(
                    nested.get("total_tokens") or nested.get("totalTokens")
                )
                if any([input_tokens, output_tokens, total_tokens]):
                    break

    # Do NOT treat generic usage maps as cumulative totals unless the event type
    # defines them that way (SPEC §13.5). If we extracted from a nested key that
    # is not total_token_usage, only use it if total_tokens > 0.
    return input_tokens, output_tokens, total_tokens


def compute_live_runtime(
    started_at_entries: list[datetime],
    cumulative_seconds: float,
) -> float:
    """Compute live runtime including active sessions.

    Per SPEC §13.5: add active-session elapsed time from started_at entries
    to cumulative ended-session runtime.

    Args:
        started_at_entries: List of started_at timestamps for active sessions.
        cumulative_seconds: Aggregate runtime from completed sessions.

    Returns:
        Total live runtime in seconds.
    """
    now = datetime.now(timezone.utc)
    active_seconds = 0.0
    for started_at in started_at_entries:
        elapsed = (now - started_at).total_seconds()
        active_seconds += max(0.0, elapsed)
    return cumulative_seconds + active_seconds


def _coerce_int(value: Any) -> int:
    """Coerce a value to int, returning 0 for anything non-numeric."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0