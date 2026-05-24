"""REST API route handlers for the HTTP dashboard extension.

Implements SPEC §13.7.2 JSON REST API endpoints.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from maestro.core.state import OrchestratorState
from maestro.observability.snapshot import SnapshotBuilder

router = APIRouter(prefix="/api/v1")


def _get_state(request: Request) -> OrchestratorState:
    """Retrieve the orchestrator state from the FastAPI app."""
    return request.app.state.maestro_state


def _error(code: str, message: str) -> dict:
    """Build a SPEC §13.7 error envelope."""
    return {"error": {"code": code, "message": message}}


@router.get("/state")
async def get_state(request: Request) -> dict:
    """Return the current system state snapshot.

    Per SPEC §13.7.2: GET /api/v1/state
    """
    state = _get_state(request)
    builder = SnapshotBuilder()

    snapshot = builder.build(
        state=state,
        running=state.running,
        retrying=state.retry_attempts,
        totals=state.codex_totals,
        rate_limits=state.codex_rate_limits,
    )

    snapshot_dict = snapshot.to_dict()

    # Build the SPEC-conformant response shape
    running_rows: list[dict] = []
    for running_row in snapshot.running:
        # Get the full RunningEntry for more details
        entry = state.running.get(running_row.issue_id)
        last_event_at = entry.last_agent_timestamp if entry else running_row.started_at
        running_rows.append(
            {
                "issue_id": running_row.issue_id,
                "issue_identifier": running_row.issue_identifier,
                "state": entry.issue.state if entry else "Unknown",
                "session_id": running_row.session_id,
                "turn_count": running_row.turn_count,
                "last_event": running_row.last_agent_event,
                "last_message": entry.last_agent_message if entry else "",
                "started_at": running_row.started_at.isoformat()
                if running_row.started_at
                else None,
                "last_event_at": last_event_at.isoformat() if last_event_at else None,
                "tokens": {
                    "input_tokens": entry.agent_input_tokens if entry else 0,
                    "output_tokens": entry.agent_output_tokens if entry else 0,
                    "total_tokens": entry.agent_total_tokens if entry else 0,
                },
            }
        )

    retrying_rows: list[dict] = []
    for retry_row in snapshot.retrying:
        retrying_rows.append(
            {
                "issue_id": retry_row.issue_id,
                "issue_identifier": retry_row.identifier,
                "attempt": retry_row.attempt,
                "due_at": datetime.fromtimestamp(
                    retry_row.due_at_ms / 1000.0, tz=timezone.utc
                ).isoformat(),
                "error": retry_row.error,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "running": len(running_rows),
            "retrying": len(retrying_rows),
        },
        "running": running_rows,
        "retrying": retrying_rows,
        "codex_totals": snapshot_dict["codex_totals"],
        "rate_limits": snapshot.rate_limits,
    }


@router.get("/{issue_identifier}")
async def get_issue(issue_identifier: str, request: Request) -> dict:
    """Return per-issue runtime debug details.

    Per SPEC §13.7.2: GET /api/v1/<issue_identifier>
    """
    state = _get_state(request)

    # Find the issue in running entries
    for running_entry in state.running.values():
        if running_entry.issue_identifier == issue_identifier:
            return _build_issue_detail(running_entry, state, "running")

    # Find in retry entries
    for retry_entry in state.retry_attempts.values():
        if retry_entry.identifier == issue_identifier:
            return _build_retry_detail(retry_entry, state)

    # Not found
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=_error("issue_not_found", f"Issue '{issue_identifier}' not found"),
    )


def _build_issue_detail(entry, state: OrchestratorState, issue_status: str) -> dict:
    """Build the per-issue detail response for a running issue."""
    return {
        "issue_identifier": entry.issue_identifier,
        "issue_id": entry.issue_id,
        "status": issue_status,
        "workspace": {
            "path": None,  # Workspace path would need WorkspaceManager reference
        },
        "attempts": {
            "restart_count": 0,
            "current_retry_attempt": entry.retry_attempt,
        },
        "running": {
            "session_id": entry.session_id,
            "turn_count": 0,
            "state": entry.issue.state,
            "started_at": entry.started_at.isoformat() if entry.started_at else None,
            "last_event": entry.last_agent_event,
            "last_message": entry.last_agent_message,
            "last_event_at": entry.last_agent_timestamp.isoformat()
            if entry.last_agent_timestamp
            else None,
            "tokens": {
                "input_tokens": entry.agent_input_tokens,
                "output_tokens": entry.agent_output_tokens,
                "total_tokens": entry.agent_total_tokens,
            },
        },
        "retry": None,
        "recent_events": _build_recent_events(entry),
        "last_error": None,
        "tracked": {},
    }


def _build_retry_detail(entry, state: OrchestratorState) -> dict:
    """Build the per-issue detail response for a retrying issue."""
    return {
        "issue_identifier": entry.identifier,
        "issue_id": entry.issue_id,
        "status": "retrying",
        "workspace": {"path": None},
        "attempts": {
            "restart_count": 0,
            "current_retry_attempt": entry.attempt,
        },
        "running": None,
        "retry": {
            "attempt": entry.attempt,
            "due_at": datetime.fromtimestamp(
                entry.due_at_ms / 1000.0, tz=timezone.utc
            ).isoformat(),
            "error": entry.error,
        },
        "recent_events": [],
        "last_error": entry.error,
        "tracked": {},
    }


def _build_recent_events(entry) -> list[dict]:
    """Build recent events list from a running entry."""
    events = []
    if entry.last_agent_event and entry.last_agent_timestamp:
        events.append(
            {
                "at": entry.last_agent_timestamp.isoformat(),
                "event": entry.last_agent_event,
                "message": entry.last_agent_message or "",
            }
        )
    return events


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh(request: Request) -> dict:
    """Trigger a poll-and-reconciliation cycle.

    Per SPEC §13.7.2: POST /api/v1/refresh
    Best-effort trigger; repeated requests may be coalesced.
    """
    now = datetime.now(timezone.utc)
    coalesced = False
    if getattr(request.app.state, "refresh_pending", False):
        # Previous refresh still pending — coalesce
        coalesced = True
    else:
        callback = getattr(request.app.state, "refresh_callback", None)
        request.app.state.refresh_pending = True
        request.app.state.refresh_task = asyncio.create_task(
            _invoke_refresh(request.app, callback)
        )

    return {
        "queued": True,
        "coalesced": coalesced,
        "requested_at": now.isoformat(),
        "operations": ["poll", "reconcile"],
    }


async def _invoke_refresh(app, callback) -> None:
    """Invoke an optional refresh callback."""
    if callback is None:
        return

    try:
        result = callback()
        if inspect.isawaitable(result):
            await result
    finally:
        app.state.refresh_pending = False
