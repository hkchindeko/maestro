"""Reconciliation logic for active runs.

Implements SPEC §8.5 (Active Run Reconciliation):
- Part A: Stall detection
- Part B: Tracker state refresh
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from maestro.tracker.base import IssueSnapshot, Tracker

from maestro.core.state import OrchestratorState, RunningEntry

logger = logging.getLogger(__name__)


def is_stalled(
    entry: RunningEntry,
    stall_timeout_ms: int,
    now: datetime | None = None,
) -> bool:
    """Check if a running entry has stalled.

    Per SPEC §8.5 Part A: compute elapsed_ms since last_codex_timestamp
    if any event has been seen, else since started_at.

    Args:
        entry: The running entry to check.
        stall_timeout_ms: The stall timeout in milliseconds.
        now: Current time (defaults to now).

    Returns:
        True if the entry has stalled.
    """
    if stall_timeout_ms <= 0:
        return False

    now = now or datetime.now(timezone.utc)

    reference_time = entry.last_agent_timestamp or entry.started_at
    elapsed_ms = (now - reference_time).total_seconds() * 1000

    return elapsed_ms > stall_timeout_ms


async def reconcile_stalled_runs(
    state: OrchestratorState,
    stall_timeout_ms: int,
    on_stall: callable[[str], None] | None = None,
) -> None:
    """Detect and handle stalled runs.

    Per SPEC §8.5 Part A.

    Args:
        state: The orchestrator state.
        stall_timeout_ms: The stall timeout in milliseconds.
        on_stall: Callback invoked for each stalled issue_id.
    """
    running_ids = await state.get_running_ids()

    for issue_id in running_ids:
        entry = await state.get_running_entry(issue_id)
        if entry is None:
            continue

        if is_stalled(entry, stall_timeout_ms):
            logger.warning(
                "Stall detected: issue_id=%s elapsed since last event exceeds %dms",
                issue_id,
                stall_timeout_ms,
            )
            if on_stall:
                on_stall(issue_id)


async def reconcile_tracker_states(
    state: OrchestratorState,
    tracker: Tracker,
    active_states: list[str],
    terminal_states: list[str],
    on_terminal: callable[[str], None] | None = None,
    on_non_active: callable[[str], None] | None = None,
) -> bool:
    """Reconcile running issues against tracker states.

    Per SPEC §8.5 Part B.

    Args:
        state: The orchestrator state.
        tracker: The tracker adapter.
        active_states: List of active state names.
        terminal_states: List of terminal state names.
        on_terminal: Callback for terminal state issues.
        on_non_active: Callback for non-active state issues.

    Returns:
        True if reconciliation succeeded, False if tracker fetch failed.
    """
    running_ids = await state.get_running_ids()
    if not running_ids:
        return True

    try:
        snapshots = await tracker.fetch_issue_states_by_ids(running_ids)
    except Exception as e:
        logger.warning("Tracker state refresh failed, keeping workers running: %s", e)
        return False

    # Normalize state names for comparison
    active_lower = {s.lower() for s in active_states}
    terminal_lower = {s.lower() for s in terminal_states}

    snapshot_map: dict[str, IssueSnapshot] = {s.id: s for s in snapshots}

    for issue_id in running_ids:
        snapshot = snapshot_map.get(issue_id)
        if snapshot is None:
            # Issue not found — treat as terminal
            logger.warning("Issue %s not found in tracker state refresh", issue_id)
            if on_terminal:
                on_terminal(issue_id)
            continue

        state_lower = snapshot.state.lower()

        if state_lower in terminal_lower:
            logger.info(
                "Issue %s is terminal (state=%s), terminating with cleanup",
                issue_id,
                snapshot.state,
            )
            if on_terminal:
                on_terminal(issue_id)
        elif state_lower in active_lower:
            # Still active — update the in-memory issue snapshot
            entry = await state.get_running_entry(issue_id)
            if entry and snapshot.identifier:
                entry.issue.state = snapshot.state
                entry.issue.identifier = snapshot.identifier
        else:
            # Neither active nor terminal — terminate without cleanup
            logger.info(
                "Issue %s is non-active (state=%s), terminating without cleanup",
                issue_id,
                snapshot.state,
            )
            if on_non_active:
                on_non_active(issue_id)

    return True
