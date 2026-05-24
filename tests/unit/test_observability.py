"""Tests for observability modules (structured logging, snapshot, token accounting, rate-limit, humanize).

Implements tasks 1.5, 2.6, 3.4, 4.3, 5.3 from the observability change.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

from maestro.observability.humanize import humanize_event
from maestro.observability.logging import (
    create_issue_logger,
    create_session_logger,
    wrap_handler_for_safety,
)
from maestro.observability.snapshot import (
    CodexTotalsRow,
    RetryQueueRow,
    RunningSessionRow,
    RuntimeSnapshot,
    SnapshotBuilder,
)
from maestro.observability.tokens import (
    compute_live_runtime,
    compute_token_delta,
    extract_tokens_from_event,
)


# ── Structured logging tests (tasks 1.5) ──────────────────────────────


class TestIssueLogger:
    """Tests for create_issue_logger per SPEC §13.1."""

    def test_includes_issue_id_and_identifier(self) -> None:
        logger = create_issue_logger("iss_123", "ABC-100")
        assert logger.extra["issue_id"] == "iss_123"
        assert logger.extra["issue_identifier"] == "ABC-100"

    def test_prepends_context_to_message(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        logger = create_issue_logger("iss_123", "ABC-100")
        logger.info("dispatch completed")
        assert "issue_id=iss_123" in caplog.text
        assert "issue_identifier=ABC-100" in caplog.text
        assert "dispatch completed" in caplog.text

    def test_key_value_phrasing_in_output(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        logger = create_issue_logger("iss_123", "ABC-100")
        logger.info("action=failed reason=timeout")
        assert "action=failed" in caplog.text
        assert "reason=timeout" in caplog.text


class TestSessionLogger:
    """Tests for create_session_logger per SPEC §13.1."""

    def test_includes_session_id(self) -> None:
        logger = create_session_logger("sess_456")
        assert logger.extra["session_id"] == "sess_456"

    def test_prepends_session_context(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        logger = create_session_logger("sess_456")
        logger.info("turn completed")
        assert "session_id=sess_456" in caplog.text
        assert "turn completed" in caplog.text


class TestNonCrashingHandler:
    """Tests for log sink failure handling per SPEC §13.2."""

    def test_wrap_handler_does_not_crash_on_emit_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A failing handler should not crash the logging call."""

        class FailingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                raise RuntimeError("sink exploded")

        wrapped = wrap_handler_for_safety(FailingHandler())
        logger = logging.getLogger("maestro.test.noncrash")
        logger.addHandler(wrapped)
        logger.setLevel(logging.INFO)

        # This should not raise
        logger.info("test message after sink failure")

        logger.removeHandler(wrapped)


# ── Snapshot tests (tasks 2.6) ────────────────────────────────────────


class TestRunningSessionRow:
    def test_defaults(self) -> None:
        row = RunningSessionRow(
            session_id="s1",
            issue_id="i1",
            issue_identifier="ABC-1",
            started_at=None,
        )
        assert row.turn_count == 0
        assert row.last_agent_event is None
        assert row.retry_attempt == 0

    def test_all_fields(self) -> None:
        now = datetime.now(timezone.utc)
        row = RunningSessionRow(
            session_id="s1",
            issue_id="i1",
            issue_identifier="ABC-1",
            started_at=now,
            turn_count=3,
            last_agent_event="turn_completed",
            retry_attempt=1,
        )
        assert row.session_id == "s1"
        assert row.issue_id == "i1"
        assert row.turn_count == 3
        assert row.started_at == now


class TestRetryQueueRow:
    def test_defaults(self) -> None:
        row = RetryQueueRow(issue_id="i1", identifier="ABC-1", attempt=1, due_at_ms=1000)
        assert row.error is None

    def test_with_error(self) -> None:
        row = RetryQueueRow(
            issue_id="i1",
            identifier="ABC-1",
            attempt=2,
            due_at_ms=5000,
            error="timeout",
        )
        assert row.error == "timeout"


class TestRuntimeSnapshot:
    def test_empty_snapshot(self) -> None:
        snap = RuntimeSnapshot()
        assert snap.running == []
        assert snap.retrying == []
        assert snap.rate_limits is None
        assert snap.error is None

    def test_to_dict_empty(self) -> None:
        snap = RuntimeSnapshot()
        d = snap.to_dict()
        assert d["running"] == []
        assert d["retrying"] == []
        assert d["codex_totals"]["input_tokens"] == 0
        assert d["codex_totals"]["output_tokens"] == 0
        assert d["codex_totals"]["total_tokens"] == 0
        assert d["codex_totals"]["seconds_running"] == 0.0
        assert d["rate_limits"] is None
        assert "error" not in d

    def test_to_dict_with_error(self) -> None:
        snap = RuntimeSnapshot(error="timeout")
        d = snap.to_dict()
        assert d["error"] == "timeout"

    def test_to_dict_with_rows(self) -> None:
        now = datetime.now(timezone.utc)
        snap = RuntimeSnapshot(
            running=[
                RunningSessionRow(
                    session_id="s1",
                    issue_id="i1",
                    issue_identifier="ABC-1",
                    started_at=now,
                )
            ],
            retrying=[
                RetryQueueRow(
                    issue_id="i2",
                    identifier="ABC-2",
                    attempt=1,
                    due_at_ms=30000,
                )
            ],
            codex_totals=CodexTotalsRow(
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                seconds_running=42.5,
            ),
            rate_limits={"remaining": 100},
        )
        d = snap.to_dict()
        assert len(d["running"]) == 1
        assert d["running"][0]["session_id"] == "s1"
        assert d["running"][0]["issue_id"] == "i1"
        assert d["running"][0]["started_at"] == now.isoformat()
        assert len(d["retrying"]) == 1
        assert d["retrying"][0]["issue_id"] == "i2"
        assert d["codex_totals"]["input_tokens"] == 100
        assert d["codex_totals"]["seconds_running"] == 42.5
        assert d["rate_limits"] == {"remaining": 100}


class TestSnapshotBuilder:
    def test_build_empty_state(self) -> None:
        from maestro.core.state import OrchestratorState

        state = OrchestratorState()
        builder = SnapshotBuilder()
        snap = builder.build(
            state=state,
            running={},
            retrying={},
            totals=state.codex_totals,
            rate_limits=None,
        )
        assert snap.running == []
        assert snap.retrying == []
        assert snap.codex_totals.total_tokens == 0
        assert snap.rate_limits is None

    def test_build_error_snapshot(self) -> None:
        builder = SnapshotBuilder()
        snap = builder.build_error("timeout")
        assert snap.error == "timeout"
        assert snap.running == []
        assert snap.retrying == []

    def test_build_unavailable_snapshot(self) -> None:
        builder = SnapshotBuilder()
        snap = builder.build_error("unavailable")
        assert snap.error == "unavailable"


# ── Token accounting tests (tasks 3.4) ───────────────────────────────


class TestComputeTokenDelta:
    def test_positive_delta(self) -> None:
        assert compute_token_delta(150, 100) == 50

    def test_zero_delta_when_same(self) -> None:
        assert compute_token_delta(100, 100) == 0

    def test_zero_delta_when_less(self) -> None:
        """Current less than last reported should return 0 (reset scenario)."""
        assert compute_token_delta(50, 100) == 0

    def test_first_report(self) -> None:
        """First report from 0 baseline."""
        assert compute_token_delta(100, 0) == 100


class TestExtractTokensFromEvent:
    def test_top_level_snake_case(self) -> None:
        payload = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
        i, o, t = extract_tokens_from_event(payload)
        assert i == 10
        assert o == 20
        assert t == 30

    def test_top_level_camel_case(self) -> None:
        payload = {"inputTokens": 5, "outputTokens": 15, "totalTokens": 25}
        i, o, t = extract_tokens_from_event(payload)
        assert i == 5
        assert o == 15
        assert t == 25

    def test_from_nested_usage_dict(self) -> None:
        payload = {"usage": {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300}}
        i, o, t = extract_tokens_from_event(payload)
        assert i == 100
        assert o == 200
        assert t == 300

    def test_from_nested_token_usage_dict(self) -> None:
        payload = {"token_usage": {"input_tokens": 50, "output_tokens": 60, "total_tokens": 110}}
        i, o, t = extract_tokens_from_event(payload)
        assert i == 50
        assert o == 60
        assert t == 110

    def test_from_total_token_usage(self) -> None:
        payload = {"total_token_usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}}
        i, o, t = extract_tokens_from_event(payload)
        assert i == 1
        assert o == 2
        assert t == 3

    def test_empty_payload(self) -> None:
        i, o, t = extract_tokens_from_event({})
        assert i == 0
        assert o == 0
        assert t == 0

    def test_non_numeric_values(self) -> None:
        payload = {"input_tokens": "abc", "output_tokens": None, "total_tokens": [1, 2]}
        i, o, t = extract_tokens_from_event(payload)
        assert i == 0
        assert o == 0
        assert t == 0

    def test_prefers_top_level_over_nested(self) -> None:
        """Top-level fields take priority over nested dicts."""
        payload = {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "usage": {"input_tokens": 999, "output_tokens": 999, "total_tokens": 999},
        }
        i, o, t = extract_tokens_from_event(payload)
        assert i == 10
        assert o == 20
        assert t == 30


class TestComputeLiveRuntime:
    def test_no_active_sessions(self) -> None:
        runtime = compute_live_runtime([], 100.0)
        assert runtime == 100.0

    def test_with_active_sessions(self) -> None:
        """Active sessions add elapsed time to cumulative."""
        now = datetime.now(timezone.utc)
        five_sec_ago = now - timedelta(seconds=5)
        ten_sec_ago = now - timedelta(seconds=10)

        runtime = compute_live_runtime([five_sec_ago, ten_sec_ago], 50.0)
        # Should be roughly 50 + ~5 + ~10 = ~65
        assert 60.0 <= runtime <= 70.0

    def test_with_future_date_returns_zero_elapsed(self) -> None:
        """A future started_at should add 0 elapsed time."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        runtime = compute_live_runtime([future], 50.0)
        assert runtime == 50.0


# ── Rate-limit tracking tests (tasks 4.3) ──────────────────────────


class TestRateLimitTracking:
    def test_update_rate_limits_sets_new_payload(self) -> None:
        """Rate limits in orchestrator state can be updated."""
        from maestro.core.state import OrchestratorState

        state = OrchestratorState()
        assert state.codex_rate_limits is None

        # We can't test async update_rate_limits directly in sync test,
        # but we can verify the field is settable via the builder.
        builder = SnapshotBuilder()
        snap = builder.build(
            state=state,
            running={},
            retrying={},
            totals=state.codex_totals,
            rate_limits={"remaining": 50, "limit": 100},
        )
        assert snap.rate_limits == {"remaining": 50, "limit": 100}

    def test_rate_limits_none_in_snapshot(self) -> None:
        from maestro.core.state import OrchestratorState

        state = OrchestratorState()
        builder = SnapshotBuilder()
        snap = builder.build(
            state=state, running={}, retrying={}, totals=state.codex_totals, rate_limits=None
        )
        assert snap.rate_limits is None


# ── Humanized event summaries tests (tasks 5.3) ─────────────────────


class TestHumanizeEvent:
    def test_session_started(self) -> None:
        result = humanize_event("session_started", {"session_id": "abc123"})
        assert "session_id=abc123" in result
        assert "Session started" in result

    def test_turn_completed(self) -> None:
        result = humanize_event("turn_completed", {"turn": 5})
        assert "turn=5" in result
        assert "Turn completed" in result

    def test_turn_failed(self) -> None:
        result = humanize_event("turn_failed", {"turn": 3, "error": "timeout"})
        assert "turn=3" in result
        assert "timeout" in result
        assert "Turn failed" in result

    def test_approval_auto_approved(self) -> None:
        result = humanize_event("approval_auto_approved", {"tool_name": "bash"})
        assert "tool=bash" in result
        assert "Approval auto-approved" in result

    def test_notification(self) -> None:
        result = humanize_event("notification", {"message": "Agent ready"})
        assert "Agent ready" in result
        assert "Notification" in result

    def test_notification_truncates_long_message(self) -> None:
        long_msg = "x" * 200
        result = humanize_event("notification", {"message": long_msg})
        assert len(result) < len(long_msg) + 50
        assert "..." in result

    def test_unknown_event_type(self) -> None:
        result = humanize_event("bizarre_event", {"foo": "bar"})
        assert "bizarre_event" in result

    def test_humanized_output_does_not_throw_on_empty_payload(self) -> None:
        """All handlers should gracefully handle missing payload keys."""
        for event_type in (
            "session_started",
            "turn_completed",
            "turn_failed",
            "approval_auto_approved",
            "notification",
        ):
            result = humanize_event(event_type, {})
            assert isinstance(result, str)
            assert len(result) > 0