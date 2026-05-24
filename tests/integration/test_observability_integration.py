"""Integration tests for observability (tasks 6.1-6.4).

Tests full snapshot assembly from mock orchestrator state, token accounting
integration, and error modes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from maestro.core.state import (
    CodexTotals,
    OrchestratorState,
    RetryEntry,
    RunningEntry,
)
from maestro.observability.snapshot import SnapshotBuilder
from maestro.observability.tokens import compute_token_delta
from maestro.tracker.base import Issue


def _make_issue(issue_id: str, identifier: str) -> Issue:
    return Issue(id=issue_id, identifier=identifier, title=f"Test {identifier}")


class TestFullSnapshotAssembly:
    """Task 6.1: Full snapshot assembly from mock orchestrator state."""

    def test_full_snapshot_with_running_and_retrying(self) -> None:
        now = datetime.now(timezone.utc)

        running: dict[str, RunningEntry] = {}
        issue1 = _make_issue("i1", "ABC-1")
        running["i1"] = RunningEntry(
            issue_id="i1",
            issue_identifier="ABC-1",
            issue=issue1,
            session_id="sess-1",
            agent_pid="pid-1",
            last_agent_event="turn_completed",
            last_agent_timestamp=now,
            agent_input_tokens=100,
            agent_output_tokens=50,
            agent_total_tokens=150,
            retry_attempt=0,
            started_at=now - timedelta(seconds=30),
        )

        retrying: dict[str, RetryEntry] = {}
        retrying["i2"] = RetryEntry(
            issue_id="i2",
            identifier="ABC-2",
            attempt=1,
            due_at_ms=30000,
            error="stall timeout",
        )

        totals = CodexTotals(
            input_tokens=500,
            output_tokens=250,
            total_tokens=750,
            seconds_running=120.0,
        )

        state = OrchestratorState()
        builder = SnapshotBuilder()
        snap = builder.build(
            state=state,
            running=running,
            retrying=retrying,
            totals=totals,
            rate_limits={"remaining": 42},
        )

        assert len(snap.running) == 1
        assert snap.running[0].session_id == "sess-1"
        assert snap.running[0].issue_id == "i1"
        assert snap.running[0].issue_identifier == "ABC-1"
        assert snap.running[0].last_agent_event == "turn_completed"
        assert snap.running[0].retry_attempt == 0

        assert len(snap.retrying) == 1
        assert snap.retrying[0].issue_id == "i2"
        assert snap.retrying[0].attempt == 1
        assert snap.retrying[0].due_at_ms == 30000
        assert snap.retrying[0].error == "stall timeout"

        # codex_totals should reflect passed totals + live runtime from active session
        assert snap.codex_totals.input_tokens == 500
        assert snap.codex_totals.output_tokens == 250
        assert snap.codex_totals.total_tokens == 750
        # Live runtime should be ~120 + ~30 = ~150
        assert snap.codex_totals.seconds_running >= 120.0

        assert snap.rate_limits == {"remaining": 42}

    def test_snapshot_to_dict_roundtrip(self) -> None:
        """Snapshot to_dict should produce JSON-serializable output."""
        now = datetime.now(timezone.utc)
        running: dict[str, RunningEntry] = {}
        issue1 = _make_issue("i1", "ABC-1")
        running["i1"] = RunningEntry(
            issue_id="i1",
            issue_identifier="ABC-1",
            issue=issue1,
            session_id="sess-1",
            started_at=now,
        )

        state = OrchestratorState()
        builder = SnapshotBuilder()
        snap = builder.build(
            state=state,
            running=running,
            retrying={},
            totals=CodexTotals(),
            rate_limits=None,
        )
        d = snap.to_dict()

        # Verify all expected keys
        assert "running" in d
        assert "retrying" in d
        assert "codex_totals" in d
        assert "rate_limits" in d
        assert "error" not in d

        # Verify it's JSON-serializable
        import json

        json.dumps(d)


class TestSnapshotWithRunningAndRetry:
    """Task 6.2: Snapshot with running sessions and retry queue."""

    def test_multiple_running_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        running: dict[str, RunningEntry] = {}

        for i in range(3):
            issue = _make_issue(f"i{i}", f"ABC-{i}")
            running[f"i{i}"] = RunningEntry(
                issue_id=f"i{i}",
                issue_identifier=f"ABC-{i}",
                issue=issue,
                session_id=f"sess-{i}",
                started_at=now - timedelta(seconds=i * 10),
                retry_attempt=i,
            )

        state = OrchestratorState()
        builder = SnapshotBuilder()
        snap = builder.build(
            state=state,
            running=running,
            retrying={},
            totals=CodexTotals(seconds_running=200.0),
            rate_limits=None,
        )

        assert len(snap.running) == 3
        # Verify all three are present
        ids = {r.issue_id for r in snap.running}
        assert ids == {"i0", "i1", "i2"}

        # Live runtime should be >= 200
        assert snap.codex_totals.seconds_running >= 200.0

    def test_multiple_retry_entries(self) -> None:
        retrying: dict[str, RetryEntry] = {}
        for i in range(5):
            retrying[f"i{i}"] = RetryEntry(
                issue_id=f"i{i}",
                identifier=f"ABC-{i}",
                attempt=i + 1,
                due_at_ms=(i + 1) * 10000,
                error="rate_limited" if i % 2 == 0 else None,
            )

        state = OrchestratorState()
        builder = SnapshotBuilder()
        snap = builder.build(
            state=state,
            running={},
            retrying=retrying,
            totals=CodexTotals(),
            rate_limits=None,
        )

        assert len(snap.retrying) == 5
        # Check alternating errors
        errors = {r.issue_id: r.error for r in snap.retrying}
        assert errors["i0"] == "rate_limited"
        assert errors["i1"] is None
        assert errors["i2"] == "rate_limited"

    def test_combined_running_and_retrying(self) -> None:
        now = datetime.now(timezone.utc)
        running: dict[str, RunningEntry] = {}
        issue = _make_issue("r1", "RUN-1")
        running["r1"] = RunningEntry(
            issue_id="r1",
            issue_identifier="RUN-1",
            issue=issue,
            session_id="sess-run",
            started_at=now - timedelta(seconds=60),
        )

        retrying: dict[str, RetryEntry] = {}
        retrying["q1"] = RetryEntry(
            issue_id="q1",
            identifier="QUEUE-1",
            attempt=2,
            due_at_ms=60000,
            error="stall timeout",
        )

        state = OrchestratorState()
        builder = SnapshotBuilder()
        snap = builder.build(
            state=state,
            running=running,
            retrying=retrying,
            totals=CodexTotals(input_tokens=1000, seconds_running=300.0),
            rate_limits={"limit": 500, "remaining": 499},
        )

        assert len(snap.running) == 1
        assert len(snap.retrying) == 1
        assert snap.codex_totals.input_tokens == 1000
        assert snap.rate_limits == {"limit": 500, "remaining": 499}


class TestTokenAccountingIntegration:
    """Task 6.3: Token accounting integration with orchestrator state."""

    def test_token_delta_across_multiple_updates(self) -> None:
        """Simulate multiple agent updates and verify delta correctness."""
        totals = CodexTotals()

        # Simulate first agent report
        entry = RunningEntry(
            issue_id="i1",
            issue_identifier="ABC-1",
            issue=_make_issue("i1", "ABC-1"),
            agent_input_tokens=0,
            agent_output_tokens=0,
            agent_total_tokens=0,
        )

        # First update: absolute totals are 100
        current_total = 100
        delta = compute_token_delta(current_total, entry.last_reported_total_tokens)
        entry.agent_total_tokens += delta
        entry.last_reported_total_tokens = current_total
        assert delta == 100
        assert entry.agent_total_tokens == 100

        # Second update: absolute totals now 250
        current_total = 250
        delta = compute_token_delta(current_total, entry.last_reported_total_tokens)
        entry.agent_total_tokens += delta
        entry.last_reported_total_tokens = current_total
        assert delta == 150
        assert entry.agent_total_tokens == 250

        # Third update: absolute totals still 250 (no new tokens)
        current_total = 250
        delta = compute_token_delta(current_total, entry.last_reported_total_tokens)
        assert delta == 0

        # Add to aggregate
        totals.add_session_totals(entry)
        assert totals.total_tokens == 250

    def test_aggregate_across_multiple_entries(self) -> None:
        """Multiple completed entries should accumulate."""
        totals = CodexTotals()

        entry1 = RunningEntry(
            issue_id="i1",
            issue_identifier="ABC-1",
            issue=_make_issue("i1", "ABC-1"),
            agent_input_tokens=100,
            agent_output_tokens=50,
            agent_total_tokens=150,
        )
        entry2 = RunningEntry(
            issue_id="i2",
            issue_identifier="ABC-2",
            issue=_make_issue("i2", "ABC-2"),
            agent_input_tokens=200,
            agent_output_tokens=100,
            agent_total_tokens=300,
        )

        totals.add_session_totals(entry1)
        totals.add_session_totals(entry2)

        assert totals.input_tokens == 300
        assert totals.output_tokens == 150
        assert totals.total_tokens == 450

    def test_live_runtime_with_mixed_ended_and_active(self) -> None:
        """Live runtime combines ended-session cumulative + active elapsed."""
        now = datetime.now(timezone.utc)
        totals = CodexTotals(seconds_running=500.0)

        running: dict[str, RunningEntry] = {}
        issue = _make_issue("i1", "ABC-1")
        running["i1"] = RunningEntry(
            issue_id="i1",
            issue_identifier="ABC-1",
            issue=issue,
            started_at=now - timedelta(seconds=120),
        )

        live = totals.compute_live_runtime(running)
        # Should be ~500 + ~120 = ~620
        assert 600.0 <= live <= 640.0


class TestSnapshotErrorModes:
    """Task 6.4: Snapshot timeout/unavailable error modes per SPEC §13.3."""

    def test_timeout_error_mode(self) -> None:
        builder = SnapshotBuilder()
        snap = builder.build_error("timeout")
        assert snap.error == "timeout"
        assert snap.running == []
        assert snap.retrying == []
        assert snap.codex_totals.input_tokens == 0

        d = snap.to_dict()
        assert d["error"] == "timeout"

    def test_unavailable_error_mode(self) -> None:
        builder = SnapshotBuilder()
        snap = builder.build_error("unavailable")
        assert snap.error == "unavailable"

        d = snap.to_dict()
        assert d["error"] == "unavailable"

    def test_error_snapshot_still_serializable(self) -> None:
        """Error snapshots must still produce valid JSON."""
        import json

        builder = SnapshotBuilder()
        for error in ("timeout", "unavailable"):
            snap = builder.build_error(error)
            json_str = json.dumps(snap.to_dict())
            assert error in json_str
            assert "running" in json_str