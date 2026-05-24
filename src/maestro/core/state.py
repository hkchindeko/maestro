"""Orchestrator runtime state models.

Implements SPEC §4.1.5-4.1.8 (Run Attempt, Live Session, Retry Entry, Orchestrator State)
and §7.4 (Idempotency and Recovery Rules).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from maestro.tracker.base import Issue

logger = logging.getLogger(__name__)


@dataclass
class RunningEntry:
    """State tracked while a coding-agent subprocess is running.

    Per SPEC §4.1.6 and §16.4.
    """

    issue_id: str
    issue_identifier: str
    issue: Issue
    session_id: str | None = None
    agent_pid: str | None = None
    last_agent_event: str | None = None
    last_agent_timestamp: datetime | None = None
    last_agent_message: str | None = None
    agent_input_tokens: int = 0
    agent_output_tokens: int = 0
    agent_total_tokens: int = 0
    last_reported_input_tokens: int = 0
    last_reported_output_tokens: int = 0
    last_reported_total_tokens: int = 0
    retry_attempt: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    worker_task: asyncio.Task[None] | None = None


@dataclass
class RetryEntry:
    """Scheduled retry state for an issue.

    Per SPEC §4.1.7.
    """

    issue_id: str
    identifier: str
    attempt: int
    due_at_ms: int
    timer_handle: asyncio.Task[None] | None = None
    error: str | None = None


@dataclass
class CodexTotals:
    """Aggregate token and runtime counters.

    Per SPEC §4.1.8 and §13.5.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    seconds_running: float = 0.0

    def add_session_totals(self, entry: RunningEntry) -> None:
        """Add a completed session's tokens to the aggregate totals."""
        self.input_tokens += entry.agent_input_tokens
        self.output_tokens += entry.agent_output_tokens
        self.total_tokens += entry.agent_total_tokens

    def add_runtime_seconds(self, seconds: float) -> None:
        """Add runtime seconds to the aggregate total."""
        self.seconds_running += seconds

    def compute_live_runtime(self, running: dict[str, RunningEntry]) -> float:
        """Compute live runtime including active sessions.

        Returns the aggregate ended-session runtime plus active session elapsed time.
        """
        now = datetime.now(timezone.utc)
        active_seconds = 0.0
        for entry in running.values():
            if entry.started_at:
                elapsed = (now - entry.started_at).total_seconds()
                active_seconds += max(0.0, elapsed)
        return self.seconds_running + active_seconds


class OrchestratorState:
    """Single authoritative in-memory state owned by the orchestrator.

    Per SPEC §4.1.8 and §7.4.
    All state mutations are serialized through an asyncio.Lock.
    """

    def __init__(
        self,
        poll_interval_ms: int = 30000,
        max_concurrent_agents: int = 10,
    ) -> None:
        self.poll_interval_ms = poll_interval_ms
        self.max_concurrent_agents = max_concurrent_agents
        self.running: dict[str, RunningEntry] = {}
        self.claimed: set[str] = set()
        self.retry_attempts: dict[str, RetryEntry] = {}
        self.completed: set[str] = set()
        self.codex_totals = CodexTotals()
        self.codex_rate_limits: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    async def claim_issue(self, issue_id: str) -> bool:
        """Claim an issue to prevent duplicate dispatch.

        Returns True if the claim was successful, False if already claimed.
        Per SPEC §7.4.
        """
        async with self._lock:
            if issue_id in self.claimed:
                return False
            self.claimed.add(issue_id)
            # Remove from retry if present
            self.retry_attempts.pop(issue_id, None)
            return True

    async def release_claim(self, issue_id: str) -> None:
        """Release a claim on an issue."""
        async with self._lock:
            self.claimed.discard(issue_id)

    async def add_running(self, entry: RunningEntry) -> None:
        """Add a running entry to the state."""
        async with self._lock:
            self.running[entry.issue_id] = entry
            self.claimed.add(entry.issue_id)
            self.retry_attempts.pop(entry.issue_id, None)

    async def remove_running(self, issue_id: str) -> RunningEntry | None:
        """Remove a running entry from the state."""
        async with self._lock:
            return self.running.pop(issue_id, None)

    async def add_retry(self, entry: RetryEntry) -> None:
        """Add or update a retry entry."""
        async with self._lock:
            # Cancel existing timer if present
            existing = self.retry_attempts.get(entry.issue_id)
            if existing and existing.timer_handle and not existing.timer_handle.done():
                existing.timer_handle.cancel()
            self.retry_attempts[entry.issue_id] = entry
            self.claimed.add(entry.issue_id)

    async def remove_retry(self, issue_id: str) -> RetryEntry | None:
        """Remove a retry entry."""
        async with self._lock:
            return self.retry_attempts.pop(issue_id, None)

    async def mark_completed(self, issue_id: str) -> None:
        """Mark an issue as completed (bookkeeping only)."""
        async with self._lock:
            self.completed.add(issue_id)

    async def available_slots(self) -> int:
        """Calculate available global concurrency slots.

        Per SPEC §8.3: max(max_concurrent_agents - running_count, 0)
        """
        async with self._lock:
            return max(self.max_concurrent_agents - len(self.running), 0)

    async def is_claimed(self, issue_id: str) -> bool:
        """Check if an issue is already claimed."""
        async with self._lock:
            return issue_id in self.claimed

    async def get_running_count(self) -> int:
        """Get the number of currently running issues."""
        async with self._lock:
            return len(self.running)

    async def get_running_entry(self, issue_id: str) -> RunningEntry | None:
        """Get a running entry by issue ID."""
        async with self._lock:
            return self.running.get(issue_id)

    async def get_running_ids(self) -> list[str]:
        """Get all running issue IDs."""
        async with self._lock:
            return list(self.running.keys())

    async def update_rate_limits(self, rate_limits: dict[str, Any] | None) -> None:
        """Update the latest rate-limit snapshot."""
        async with self._lock:
            self.codex_rate_limits = rate_limits
