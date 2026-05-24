"""Runtime snapshot data models and builder.

Implements SPEC §13.3 — synchronous runtime snapshot for dashboards/monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from maestro.core.state import CodexTotals, OrchestratorState, RetryEntry, RunningEntry


@dataclass
class RunningSessionRow:
    """A single running session row for the snapshot.

    Per SPEC §13.3 running row shape, includes ``turn_count``.
    """

    session_id: str | None
    issue_id: str
    issue_identifier: str
    started_at: datetime | None
    turn_count: int = 0
    last_agent_event: str | None = None
    retry_attempt: int = 0


@dataclass
class RetryQueueRow:
    """A single retry queue row for the snapshot.

    Per SPEC §13.3 retrying row shape.
    """

    issue_id: str
    identifier: str
    attempt: int
    due_at_ms: int
    error: str | None = None


@dataclass
class CodexTotalsRow:
    """Token and runtime totals for the snapshot."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    seconds_running: float = 0.0


@dataclass
class RuntimeSnapshot:
    """Synchronous runtime snapshot for dashboards and monitoring.

    Per SPEC §13.3.
    """

    running: list[RunningSessionRow] = field(default_factory=list)
    retrying: list[RetryQueueRow] = field(default_factory=list)
    codex_totals: CodexTotalsRow = field(default_factory=CodexTotalsRow)
    rate_limits: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the snapshot to a JSON-compatible dict.

        Returns:
            dict with running, retrying, codex_totals, rate_limits, and optional error fields.
        """
        result: dict[str, Any] = {
            "running": [
                {
                    "session_id": r.session_id,
                    "issue_id": r.issue_id,
                    "issue_identifier": r.issue_identifier,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "turn_count": r.turn_count,
                    "last_agent_event": r.last_agent_event,
                    "retry_attempt": r.retry_attempt,
                }
                for r in self.running
            ],
            "retrying": [
                {
                    "issue_id": r.issue_id,
                    "identifier": r.identifier,
                    "attempt": r.attempt,
                    "due_at_ms": r.due_at_ms,
                    "error": r.error,
                }
                for r in self.retrying
            ],
            "codex_totals": {
                "input_tokens": self.codex_totals.input_tokens,
                "output_tokens": self.codex_totals.output_tokens,
                "total_tokens": self.codex_totals.total_tokens,
                "seconds_running": self.codex_totals.seconds_running,
            },
            "rate_limits": self.rate_limits,
        }
        if self.error:
            result["error"] = self.error
        return result


class SnapshotBuilder:
    """Assembles a RuntimeSnapshot from current orchestrator state.

    Per SPEC §13.3.
    """

    def build(
        self,
        state: OrchestratorState,
        running: dict[str, RunningEntry],
        retrying: dict[str, RetryEntry],
        totals: CodexTotals,
        rate_limits: dict[str, Any] | None,
    ) -> RuntimeSnapshot:
        """Build a runtime snapshot from orchestrator state.

        Args:
            state: The orchestrator state (used for live runtime computation).
            running: Current running entries.
            retrying: Current retry entries.
            totals: Aggregate token/runtime totals.
            rate_limits: Latest rate-limit payload, if any.

        Returns:
            A RuntimeSnapshot representing the current runtime state.
        """
        running_rows = [
            RunningSessionRow(
                session_id=entry.session_id,
                issue_id=entry.issue_id,
                issue_identifier=entry.issue_identifier,
                started_at=entry.started_at,
                turn_count=0,  # RunningEntry does not track turn_count; set from agent session if available
                last_agent_event=entry.last_agent_event,
                retry_attempt=entry.retry_attempt,
            )
            for entry in running.values()
        ]

        retrying_rows = [
            RetryQueueRow(
                issue_id=entry.issue_id,
                identifier=entry.identifier,
                attempt=entry.attempt,
                due_at_ms=entry.due_at_ms,
                error=entry.error,
            )
            for entry in retrying.values()
        ]

        # Compute live runtime: aggregate ended-session runtime + active session elapsed
        live_seconds = totals.compute_live_runtime(running)

        return RuntimeSnapshot(
            running=running_rows,
            retrying=retrying_rows,
            codex_totals=CodexTotalsRow(
                input_tokens=totals.input_tokens,
                output_tokens=totals.output_tokens,
                total_tokens=totals.total_tokens,
                seconds_running=live_seconds,
            ),
            rate_limits=rate_limits,
        )

    def build_error(self, error: str) -> RuntimeSnapshot:
        """Build an error snapshot for unavailable/timeout scenarios.

        Per SPEC §13.3 RECOMMENDED error modes: timeout, unavailable.

        Args:
            error: Error description (e.g. "timeout", "unavailable").

        Returns:
            A RuntimeSnapshot with only the error field populated.
        """
        return RuntimeSnapshot(error=error)