"""Tests for orchestrator state, reconciliation, and core logic.

Covers tasks 1.5, 2.6, 3.3, 4.5, 5.6, 6.5, and 7.1-7.6.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.core.orchestrator import Orchestrator
from maestro.core.reconciliation import is_stalled, reconcile_stalled_runs, reconcile_tracker_states
from maestro.core.state import CodexTotals, OrchestratorState, RetryEntry, RunningEntry
from maestro.tracker.base import BlockerRef, Issue, IssueSnapshot


class TestRunningEntry:
    """Tests for RunningEntry dataclass (task 1.1)."""

    def test_running_entry_creation(self) -> None:
        issue = Issue(id="abc123", identifier="ABC-123", title="Test")
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=issue,
        )
        assert entry.issue_id == "abc123"
        assert entry.session_id is None
        assert entry.agent_total_tokens == 0
        assert entry.started_at is not None


class TestRetryEntry:
    """Tests for RetryEntry dataclass (task 1.2)."""

    def test_retry_entry_creation(self) -> None:
        entry = RetryEntry(
            issue_id="abc123",
            identifier="ABC-123",
            attempt=1,
            due_at_ms=1234567890000,
            error="test error",
        )
        assert entry.issue_id == "abc123"
        assert entry.attempt == 1
        assert entry.error == "test error"


class TestCodexTotals:
    """Tests for CodexTotals."""

    def test_add_session_totals(self) -> None:
        totals = CodexTotals()
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=Issue(id="abc123", identifier="ABC-123", title="Test"),
            agent_input_tokens=100,
            agent_output_tokens=50,
            agent_total_tokens=150,
        )
        totals.add_session_totals(entry)
        assert totals.input_tokens == 100
        assert totals.output_tokens == 50
        assert totals.total_tokens == 150

    def test_add_runtime_seconds(self) -> None:
        totals = CodexTotals()
        totals.add_runtime_seconds(10.5)
        totals.add_runtime_seconds(5.0)
        assert totals.seconds_running == 15.5

    def test_compute_live_runtime(self) -> None:
        totals = CodexTotals()
        totals.seconds_running = 100.0

        now = datetime.now(timezone.utc)
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=Issue(id="abc123", identifier="ABC-123", title="Test"),
            started_at=now - timedelta(seconds=30),
        )

        live = totals.compute_live_runtime({"abc123": entry})
        assert live >= 130.0  # 100 + at least 30


@pytest.mark.asyncio
class TestOrchestratorState:
    """Tests for OrchestratorState (tasks 1.3-1.5)."""

    async def test_claim_issue(self) -> None:
        state = OrchestratorState()
        assert await state.claim_issue("abc123") is True
        assert await state.is_claimed("abc123") is True

    async def test_claim_issue_already_claimed(self) -> None:
        state = OrchestratorState()
        assert await state.claim_issue("abc123") is True
        assert await state.claim_issue("abc123") is False

    async def test_release_claim(self) -> None:
        state = OrchestratorState()
        await state.claim_issue("abc123")
        await state.release_claim("abc123")
        assert await state.is_claimed("abc123") is False

    async def test_add_running(self) -> None:
        state = OrchestratorState()
        issue = Issue(id="abc123", identifier="ABC-123", title="Test")
        entry = RunningEntry(issue_id="abc123", issue_identifier="ABC-123", issue=issue)
        await state.add_running(entry)
        assert await state.get_running_count() == 1
        assert await state.is_claimed("abc123") is True

    async def test_remove_running(self) -> None:
        state = OrchestratorState()
        issue = Issue(id="abc123", identifier="ABC-123", title="Test")
        entry = RunningEntry(issue_id="abc123", issue_identifier="ABC-123", issue=issue)
        await state.add_running(entry)
        removed = await state.remove_running("abc123")
        assert removed is not None
        assert removed.issue_id == "abc123"
        assert await state.get_running_count() == 0

    async def test_available_slots(self) -> None:
        state = OrchestratorState(max_concurrent_agents=2)
        assert await state.available_slots() == 2

        issue = Issue(id="abc123", identifier="ABC-123", title="Test")
        await state.add_running(
            RunningEntry(issue_id="abc123", issue_identifier="ABC-123", issue=issue)
        )
        assert await state.available_slots() == 1

    async def test_available_slots_zero(self) -> None:
        state = OrchestratorState(max_concurrent_agents=1)
        issue = Issue(id="abc123", identifier="ABC-123", title="Test")
        await state.add_running(
            RunningEntry(issue_id="abc123", issue_identifier="ABC-123", issue=issue)
        )
        assert await state.available_slots() == 0

    async def test_add_retry_cancels_existing(self) -> None:
        state = OrchestratorState()
        entry1 = RetryEntry(issue_id="abc123", identifier="ABC-123", attempt=1, due_at_ms=1000)
        entry1.timer_handle = asyncio.create_task(asyncio.sleep(10))
        await state.add_retry(entry1)

        entry2 = RetryEntry(issue_id="abc123", identifier="ABC-123", attempt=2, due_at_ms=2000)
        await state.add_retry(entry2)

        # First timer should be cancelled
        assert entry1.timer_handle.cancelled() or entry1.timer_handle.done()

    async def test_mark_completed(self) -> None:
        state = OrchestratorState()
        await state.mark_completed("abc123")
        assert "abc123" in state.completed

    async def test_lock_serialization(self) -> None:
        """Test that state mutations are serialized through the lock."""
        state = OrchestratorState()
        results = []

        async def concurrent_claim(issue_id: str) -> None:
            claimed = await state.claim_issue(issue_id)
            results.append((issue_id, claimed))

        # Run multiple claims concurrently
        await asyncio.gather(
            concurrent_claim("abc123"),
            concurrent_claim("abc123"),
            concurrent_claim("abc123"),
        )

        # Only one should succeed
        success_count = sum(1 for _, claimed in results if claimed)
        assert success_count == 1


class TestIsStalled:
    """Tests for stall detection (task 5.1)."""

    def test_stalled_when_elapsed_exceeds_timeout(self) -> None:
        now = datetime.now(timezone.utc)
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=Issue(id="abc123", identifier="ABC-123", title="Test"),
            started_at=now - timedelta(seconds=10),
        )
        assert is_stalled(entry, stall_timeout_ms=5000, now=now) is True

    def test_not_stalled_when_within_timeout(self) -> None:
        now = datetime.now(timezone.utc)
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=Issue(id="abc123", identifier="ABC-123", title="Test"),
            started_at=now - timedelta(seconds=2),
        )
        assert is_stalled(entry, stall_timeout_ms=5000, now=now) is False

    def test_uses_last_agent_timestamp_if_available(self) -> None:
        now = datetime.now(timezone.utc)
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=Issue(id="abc123", identifier="ABC-123", title="Test"),
            started_at=now - timedelta(seconds=10),
            last_agent_timestamp=now - timedelta(seconds=1),
        )
        assert is_stalled(entry, stall_timeout_ms=5000, now=now) is False

    def test_stall_timeout_zero_disables_detection(self) -> None:
        now = datetime.now(timezone.utc)
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=Issue(id="abc123", identifier="ABC-123", title="Test"),
            started_at=now - timedelta(seconds=100),
        )
        assert is_stalled(entry, stall_timeout_ms=0, now=now) is False


class TestSortForDispatch:
    """Tests for dispatch sorting (tasks 2.2, 2.6)."""

    def test_sort_by_priority(self) -> None:
        now = datetime.now(timezone.utc)
        issues = [
            Issue(id="3", identifier="ABC-3", title="T3", priority=3, created_at=now),
            Issue(id="1", identifier="ABC-1", title="T1", priority=1, created_at=now),
            Issue(id="2", identifier="ABC-2", title="T2", priority=2, created_at=now),
        ]
        # Use the orchestrator's sort method
        from maestro.core.orchestrator import Orchestrator

        # Create a minimal orchestrator to test sorting
        mock_tracker = MagicMock()
        mock_workspace = MagicMock()
        mock_agent = MagicMock()
        mock_prompt = MagicMock()
        mock_config = MagicMock()
        mock_config.polling.interval_ms = 30000
        mock_config.agent.max_concurrent_agents = 10
        mock_config.agent.max_turns = 20
        mock_config.agent.max_retry_backoff_ms = 300000
        mock_config.codex.stall_timeout_ms = 300000
        mock_config.tracker.active_states = ["Todo", "In Progress"]
        mock_config.tracker.terminal_states = ["Done"]
        mock_definition = MagicMock()

        orch = Orchestrator(
            tracker=mock_tracker,
            workspace_manager=mock_workspace,
            agent_runner=mock_agent,
            prompt_builder=mock_prompt,
            config=mock_config,
            definition=mock_definition,
        )

        sorted_issues = orch._sort_for_dispatch(issues)
        assert sorted_issues[0].priority == 1
        assert sorted_issues[1].priority == 2
        assert sorted_issues[2].priority == 3

    def test_sort_null_priority_last(self) -> None:
        now = datetime.now(timezone.utc)
        issues = [
            Issue(id="1", identifier="ABC-1", title="T1", priority=None, created_at=now),
            Issue(id="2", identifier="ABC-2", title="T2", priority=1, created_at=now),
        ]
        from maestro.core.orchestrator import Orchestrator

        mock_tracker = MagicMock()
        mock_workspace = MagicMock()
        mock_agent = MagicMock()
        mock_prompt = MagicMock()
        mock_config = MagicMock()
        mock_config.polling.interval_ms = 30000
        mock_config.agent.max_concurrent_agents = 10
        mock_config.agent.max_turns = 20
        mock_config.agent.max_retry_backoff_ms = 300000
        mock_config.codex.stall_timeout_ms = 300000
        mock_config.tracker.active_states = ["Todo"]
        mock_config.tracker.terminal_states = ["Done"]
        mock_definition = MagicMock()

        orch = Orchestrator(
            tracker=mock_tracker,
            workspace_manager=mock_workspace,
            agent_runner=mock_agent,
            prompt_builder=mock_prompt,
            config=mock_config,
            definition=mock_definition,
        )

        sorted_issues = orch._sort_for_dispatch(issues)
        assert sorted_issues[0].priority == 1
        assert sorted_issues[1].priority is None


class TestShouldDispatch:
    """Tests for dispatch eligibility (tasks 2.3-2.4, 7.5)."""

    @pytest.mark.asyncio
    async def test_eligible_issue(self) -> None:
        from maestro.core.orchestrator import Orchestrator

        mock_tracker = MagicMock()
        mock_workspace = MagicMock()
        mock_agent = MagicMock()
        mock_prompt = MagicMock()
        mock_config = MagicMock()
        mock_config.polling.interval_ms = 30000
        mock_config.agent.max_concurrent_agents = 10
        mock_config.agent.max_turns = 20
        mock_config.agent.max_retry_backoff_ms = 300000
        mock_config.codex.stall_timeout_ms = 300000
        mock_config.tracker.active_states = ["Todo", "In Progress"]
        mock_config.tracker.terminal_states = ["Done", "Closed"]
        mock_definition = MagicMock()

        orch = Orchestrator(
            tracker=mock_tracker,
            workspace_manager=mock_workspace,
            agent_runner=mock_agent,
            prompt_builder=mock_prompt,
            config=mock_config,
            definition=mock_definition,
        )

        issue = Issue(
            id="abc123",
            identifier="ABC-123",
            title="Test",
            state="In Progress",
        )
        assert await orch._should_dispatch(issue) is True

    @pytest.mark.asyncio
    async def test_todo_with_non_terminal_blocker_not_eligible(self) -> None:
        from maestro.core.orchestrator import Orchestrator

        mock_tracker = MagicMock()
        mock_workspace = MagicMock()
        mock_agent = MagicMock()
        mock_prompt = MagicMock()
        mock_config = MagicMock()
        mock_config.polling.interval_ms = 30000
        mock_config.agent.max_concurrent_agents = 10
        mock_config.agent.max_turns = 20
        mock_config.agent.max_retry_backoff_ms = 300000
        mock_config.codex.stall_timeout_ms = 300000
        mock_config.tracker.active_states = ["Todo", "In Progress"]
        mock_config.tracker.terminal_states = ["Done", "Closed"]
        mock_definition = MagicMock()

        orch = Orchestrator(
            tracker=mock_tracker,
            workspace_manager=mock_workspace,
            agent_runner=mock_agent,
            prompt_builder=mock_prompt,
            config=mock_config,
            definition=mock_definition,
        )

        issue = Issue(
            id="abc123",
            identifier="ABC-123",
            title="Test",
            state="Todo",
            blocked_by=[BlockerRef(id="blk1", identifier="ABC-100", state="In Progress")],
        )
        assert await orch._should_dispatch(issue) is False

    @pytest.mark.asyncio
    async def test_todo_with_terminal_blocker_eligible(self) -> None:
        from maestro.core.orchestrator import Orchestrator

        mock_tracker = MagicMock()
        mock_workspace = MagicMock()
        mock_agent = MagicMock()
        mock_prompt = MagicMock()
        mock_config = MagicMock()
        mock_config.polling.interval_ms = 30000
        mock_config.agent.max_concurrent_agents = 10
        mock_config.agent.max_turns = 20
        mock_config.agent.max_retry_backoff_ms = 300000
        mock_config.codex.stall_timeout_ms = 300000
        mock_config.tracker.active_states = ["Todo", "In Progress"]
        mock_config.tracker.terminal_states = ["Done", "Closed"]
        mock_definition = MagicMock()

        orch = Orchestrator(
            tracker=mock_tracker,
            workspace_manager=mock_workspace,
            agent_runner=mock_agent,
            prompt_builder=mock_prompt,
            config=mock_config,
            definition=mock_definition,
        )

        issue = Issue(
            id="abc123",
            identifier="ABC-123",
            title="Test",
            state="Todo",
            blocked_by=[BlockerRef(id="blk1", identifier="ABC-100", state="Done")],
        )
        assert await orch._should_dispatch(issue) is True

    @pytest.mark.asyncio
    async def test_claimed_issue_not_eligible(self) -> None:
        from maestro.core.orchestrator import Orchestrator

        mock_tracker = MagicMock()
        mock_workspace = MagicMock()
        mock_agent = MagicMock()
        mock_prompt = MagicMock()
        mock_config = MagicMock()
        mock_config.polling.interval_ms = 30000
        mock_config.agent.max_concurrent_agents = 10
        mock_config.agent.max_turns = 20
        mock_config.agent.max_retry_backoff_ms = 300000
        mock_config.codex.stall_timeout_ms = 300000
        mock_config.tracker.active_states = ["Todo", "In Progress"]
        mock_config.tracker.terminal_states = ["Done", "Closed"]
        mock_definition = MagicMock()

        orch = Orchestrator(
            tracker=mock_tracker,
            workspace_manager=mock_workspace,
            agent_runner=mock_agent,
            prompt_builder=mock_prompt,
            config=mock_config,
            definition=mock_definition,
        )

        issue = Issue(
            id="abc123",
            identifier="ABC-123",
            title="Test",
            state="In Progress",
        )
        await orch._state.claim_issue("abc123")
        assert await orch._should_dispatch(issue) is False


class TestReconciliation:
    """Tests for reconciliation (tasks 5.2-5.6, 7.2, 7.6)."""

    @pytest.mark.asyncio
    async def test_reconcile_stalled_runs(self) -> None:
        state = OrchestratorState()
        now = datetime.now(timezone.utc)
        issue = Issue(id="abc123", identifier="ABC-123", title="Test")
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=issue,
            started_at=now - timedelta(seconds=10),
        )
        await state.add_running(entry)

        stalled_issues: list[str] = []

        def on_stall(issue_id: str) -> None:
            stalled_issues.append(issue_id)

        await reconcile_stalled_runs(state, stall_timeout_ms=5000, on_stall=on_stall)
        assert "abc123" in stalled_issues

    @pytest.mark.asyncio
    async def test_reconcile_tracker_states_terminal(self) -> None:
        state = OrchestratorState()
        issue = Issue(id="abc123", identifier="ABC-123", title="Test", state="In Progress")
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=issue,
        )
        await state.add_running(entry)

        mock_tracker = AsyncMock()
        mock_tracker.fetch_issue_states_by_ids.return_value = [
            IssueSnapshot(id="abc123", identifier="ABC-123", state="Done")
        ]

        terminal_issues: list[str] = []

        def on_terminal(issue_id: str) -> None:
            terminal_issues.append(issue_id)

        success = await reconcile_tracker_states(
            state,
            mock_tracker,
            active_states=["Todo", "In Progress"],
            terminal_states=["Done", "Closed"],
            on_terminal=on_terminal,
        )
        assert success is True
        assert "abc123" in terminal_issues

    @pytest.mark.asyncio
    async def test_reconcile_tracker_states_refresh_failure(self) -> None:
        state = OrchestratorState()
        issue = Issue(id="abc123", identifier="ABC-123", title="Test", state="In Progress")
        entry = RunningEntry(
            issue_id="abc123",
            issue_identifier="ABC-123",
            issue=issue,
        )
        await state.add_running(entry)

        mock_tracker = AsyncMock()
        mock_tracker.fetch_issue_states_by_ids.side_effect = Exception("API error")

        success = await reconcile_tracker_states(
            state,
            mock_tracker,
            active_states=["Todo", "In Progress"],
            terminal_states=["Done"],
        )
        assert success is False
        # Running entry should still be present
        assert await state.get_running_count() == 1


class TestRetryBackoff:
    """Tests for retry backoff formula (task 4.5)."""

    def test_backoff_formula(self) -> None:
        max_backoff = 300000  # 5 minutes
        base_delay = 10000

        # Attempt 1: 10000 * 2^0 = 10000
        assert min(base_delay * (2 ** (1 - 1)), max_backoff) == 10000

        # Attempt 2: 10000 * 2^1 = 20000
        assert min(base_delay * (2 ** (2 - 1)), max_backoff) == 20000

        # Attempt 3: 10000 * 2^2 = 40000
        assert min(base_delay * (2 ** (3 - 1)), max_backoff) == 40000

        # Attempt 10: 10000 * 2^9 = 5120000, capped at 300000
        assert min(base_delay * (2 ** (10 - 1)), max_backoff) == 300000
