"""Tests for agent runner protocol, events, and Codex client.

Covers tasks 1.5, 2.8, 3.5, 4.5, 5.6, and 6.1-6.6.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.agent.base import (
    AgentEvent,
    AgentEventType,
    AgentRunner,
    AgentSession,
    TokenUsage,
    TurnResult,
)
from maestro.agent.codex import (
    AgentLaunchError,
    AgentProtocolError,
    AgentSessionError,
    AgentTimeoutError,
    CodexAgentRunner,
)
from maestro.agent.events import (
    extract_rate_limit,
    extract_token_usage,
    parse_agent_event,
    parse_json_line,
)


class TestAgentSession:
    """Tests for AgentSession dataclass (task 1.1)."""

    def test_session_creation(self) -> None:
        session = AgentSession(
            session_id="thread-1-turn-1",
            thread_id="thread-1",
            turn_id="turn-1",
        )
        assert session.session_id == "thread-1-turn-1"
        assert session.thread_id == "thread-1"
        assert session.turn_id == "turn-1"
        assert session.turn_count == 0

    def test_token_update_delta_tracking(self) -> None:
        session = AgentSession(
            session_id="thread-1-turn-1",
            thread_id="thread-1",
            turn_id="turn-1",
        )
        # First report
        session.update_tokens(TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150))
        assert session.codex_total_tokens == 150

        # Second report with delta
        session.update_tokens(TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300))
        assert session.codex_total_tokens == 300  # 150 + 150 delta

    def test_token_update_first_report(self) -> None:
        session = AgentSession(
            session_id="thread-1-turn-1",
            thread_id="thread-1",
            turn_id="turn-1",
        )
        session.update_tokens(TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150))
        assert session.codex_input_tokens == 100
        assert session.codex_output_tokens == 50
        assert session.codex_total_tokens == 150


class TestAgentEvent:
    """Tests for AgentEvent dataclass (task 1.2)."""

    def test_event_creation(self) -> None:
        event = AgentEvent(
            event_type=AgentEventType.SESSION_STARTED,
            session_id="thread-1-turn-1",
        )
        assert event.event_type == AgentEventType.SESSION_STARTED
        assert event.session_id == "thread-1-turn-1"
        assert event.timestamp is not None


class TestTurnResult:
    """Tests for TurnResult dataclass (task 1.4)."""

    def test_success_result(self) -> None:
        result = TurnResult(success=True)
        assert result.success is True
        assert result.error is None

    def test_failure_result(self) -> None:
        result = TurnResult(success=False, error="timeout", error_category="turn_timeout")
        assert result.success is False
        assert result.error == "timeout"
        assert result.error_category == "turn_timeout"


class TestAgentRunnerABC:
    """Tests for AgentRunner ABC (task 1.3)."""

    def test_agent_runner_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            AgentRunner()  # type: ignore[abstract]

    def test_agent_runner_requires_three_methods(self) -> None:
        assert hasattr(AgentRunner, "start_session")
        assert hasattr(AgentRunner, "run_turn")
        assert hasattr(AgentRunner, "stop_session")


class TestParseJsonLine:
    """Tests for JSON line parsing."""

    def test_valid_json(self) -> None:
        result = parse_json_line('{"event": "turn_completed"}')
        assert result is not None
        assert result["event"] == "turn_completed"

    def test_empty_line(self) -> None:
        assert parse_json_line("") is None
        assert parse_json_line("   ") is None

    def test_invalid_json(self) -> None:
        assert parse_json_line("not json") is None

    def test_non_dict_json(self) -> None:
        assert parse_json_line("[1, 2, 3]") is None


class TestExtractTokenUsage:
    """Tests for token extraction (task 3.2)."""

    def test_extract_from_usage_field(self) -> None:
        payload = {"usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}}
        usage = extract_token_usage(payload)
        assert usage is not None
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150

    def test_extract_from_top_level(self) -> None:
        payload = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        usage = extract_token_usage(payload)
        assert usage is not None
        assert usage.total_tokens == 150

    def test_extract_from_token_usage_field(self) -> None:
        payload = {"tokenUsage": {"inputTokens": 100, "outputTokens": 50, "totalTokenUsage": 150}}
        usage = extract_token_usage(payload)
        assert usage is not None

    def test_no_token_fields(self) -> None:
        payload = {"event": "turn_completed"}
        assert extract_token_usage(payload) is None


class TestExtractRateLimit:
    """Tests for rate-limit extraction (task 3.3)."""

    def test_extract_rate_limit(self) -> None:
        payload = {"rateLimit": {"remaining": 100, "reset": 1234567890}}
        result = extract_rate_limit(payload)
        assert result is not None
        assert result["remaining"] == 100

    def test_no_rate_limit(self) -> None:
        payload = {"event": "turn_completed"}
        assert extract_rate_limit(payload) is None


class TestParseAgentEvent:
    """Tests for event parsing (task 3.5)."""

    def test_parse_session_started(self) -> None:
        raw = {
            "event": "session_started",
            "timestamp": "2026-05-23T10:00:00Z",
            "session_id": "thread-1-turn-1",
        }
        event = parse_agent_event(raw)
        assert event.event_type == AgentEventType.SESSION_STARTED
        assert event.session_id == "thread-1-turn-1"

    def test_parse_unknown_event_type(self) -> None:
        raw = {"event": "unknown_event_type"}
        event = parse_agent_event(raw)
        assert event.event_type == AgentEventType.OTHER_MESSAGE

    def test_parse_with_token_usage(self) -> None:
        raw = {
            "event": "turn_completed",
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        }
        event = parse_agent_event(raw)
        assert event.usage is not None
        assert event.usage.total_tokens == 150


class TestCodexAgentRunner:
    """Tests for Codex agent runner (tasks 2.1-2.8, 6.1-6.6)."""

    def test_runner_creation(self) -> None:
        runner = CodexAgentRunner(
            command="codex app-server",
            read_timeout_ms=5000,
            turn_timeout_ms=3600000,
        )
        assert runner._command == "codex app-server"
        assert runner._read_timeout == 5.0
        assert runner._turn_timeout == 3600.0

    @pytest.mark.asyncio
    async def test_session_lifecycle_mock(self) -> None:
        """Test full session lifecycle: start → turn → stop with mock (task 6.1)."""
        runner = CodexAgentRunner(command="codex app-server")

        events: list[AgentEvent] = []

        def on_event(event: AgentEvent) -> None:
            events.append(event)

        # Mock the subprocess
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.stdin = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.wait = AsyncMock()

        # Mock responses for thread/create and turn/start
        responses = [
            json.dumps({"id": 1, "result": {"threadId": "thread-1"}}) + "\n",
            json.dumps({"id": 2, "result": {"turnId": "turn-1"}}) + "\n",
        ]
        response_iter = iter(responses)

        async def mock_readline() -> bytes:
            try:
                return next(response_iter).encode("utf-8")
            except StopIteration:
                return b""

        mock_process.stdout.readline = mock_readline

        with patch.object(runner, "_launch", new_callable=AsyncMock):
            runner._process = mock_process
            session = await runner.start_session(
                workspace_path=Path("/tmp/test-workspace"),
                prompt="Test prompt",
                on_event=on_event,
            )

        assert session.session_id == "thread-1-turn-1"
        assert session.thread_id == "thread-1"
        assert session.turn_id == "turn-1"
        assert session.codex_app_server_pid == "12345"

        # Check session_started event was emitted
        session_started_events = [
            e for e in events if e.event_type == AgentEventType.SESSION_STARTED
        ]
        assert len(session_started_events) == 1

        # Stop session
        await runner.stop_session(session)
        assert runner._process is None

    @pytest.mark.asyncio
    async def test_event_streaming_mock(self) -> None:
        """Test event streaming with mock app-server responses (task 6.2)."""
        runner = CodexAgentRunner(command="codex app-server")

        events: list[AgentEvent] = []

        def on_event(event: AgentEvent) -> None:
            events.append(event)

        runner._on_event = on_event
        runner._event_queue = asyncio.Queue()

        # Put mock events in the queue
        await runner._event_queue.put(
            {"event": "turn_completed", "usage": {"total_tokens": 100}}
        )
        await runner._event_queue.put({"event": "notification", "message": "Working"})

        session = AgentSession(
            session_id="thread-1-turn-1",
            thread_id="thread-1",
            turn_id="turn-1",
        )

        # Process events manually
        raw = await runner._event_queue.get()
        event = parse_agent_event(raw)
        runner._emit_event(
            event.event_type,
            session_id=session.session_id,
            payload=raw,
            usage=event.usage,
        )

        assert len(events) == 1
        assert events[0].event_type == AgentEventType.TURN_COMPLETED
        assert events[0].session_id == "thread-1-turn-1"

    @pytest.mark.asyncio
    async def test_turn_timeout(self) -> None:
        """Test timeout handling with slow mock (task 6.3)."""
        runner = CodexAgentRunner(command="codex app-server", turn_timeout_ms=100)

        session = AgentSession(
            session_id="thread-1-turn-1",
            thread_id="thread-1",
            turn_id="turn-1",
        )

        # Create a queue that never produces events
        runner._event_queue = asyncio.Queue()
        runner._process = MagicMock()
        runner._process.stdin = MagicMock()

        result = await runner.run_turn(session, "Test prompt")
        assert result.success is False
        assert result.error_category == "turn_timeout"

    @pytest.mark.asyncio
    async def test_approval_auto_approve(self) -> None:
        """Test approval auto-approval flow (task 6.4)."""
        runner = CodexAgentRunner(command="codex app-server")

        events: list[AgentEvent] = []

        def on_event(event: AgentEvent) -> None:
            events.append(event)

        runner._on_event = on_event
        runner._event_queue = asyncio.Queue()

        # Put approval event in queue
        await runner._event_queue.put(
            {
                "event": "approval_auto_approved",
                "type": "command_execution",
            }
        )

        session = AgentSession(
            session_id="thread-1-turn-1",
            thread_id="thread-1",
            turn_id="turn-1",
        )

        # Process the event
        raw = await runner._event_queue.get()
        event = parse_agent_event(raw)
        runner._emit_event(
            event.event_type,
            session_id=session.session_id,
            payload=raw,
        )

        assert len(events) == 1
        assert events[0].event_type == AgentEventType.APPROVAL_AUTO_APPROVED

    @pytest.mark.asyncio
    async def test_user_input_required_failure(self) -> None:
        """Test user-input-required failure flow (task 6.5)."""
        runner = CodexAgentRunner(command="codex app-server")

        events: list[AgentEvent] = []

        def on_event(event: AgentEvent) -> None:
            events.append(event)

        runner._on_event = on_event
        runner._event_queue = asyncio.Queue()

        # Put user-input-required event in queue
        await runner._event_queue.put(
            {
                "event": "turn_input_required",
                "message": "Need user input",
            }
        )

        session = AgentSession(
            session_id="thread-1-turn-1",
            thread_id="thread-1",
            turn_id="turn-1",
        )

        # Process the event through wait_for_turn_completion
        result = await runner._wait_for_turn_completion(session)
        assert result.success is False
        assert result.error_category == "turn_input_required"
        assert "User input required" in (result.error or "")

    @pytest.mark.asyncio
    async def test_token_accounting_mock(self) -> None:
        """Test token accounting with mock token events (task 6.6)."""
        session = AgentSession(
            session_id="thread-1-turn-1",
            thread_id="thread-1",
            turn_id="turn-1",
        )

        # Simulate token events
        usage1 = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        session.update_tokens(usage1)
        assert session.codex_total_tokens == 150

        usage2 = TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300)
        session.update_tokens(usage2)
        # Delta: 300 - 150 = 150 added
        assert session.codex_total_tokens == 300

    def test_error_classes(self) -> None:
        """Test error class hierarchy (tasks 5.4-5.5)."""
        assert issubclass(AgentSessionError, Exception)
        assert issubclass(AgentTimeoutError, AgentSessionError)
        assert issubclass(AgentLaunchError, AgentSessionError)
        assert issubclass(AgentProtocolError, AgentSessionError)

        err = AgentTimeoutError("timed out")
        assert "timed out" in str(err)

        err = AgentLaunchError("failed to launch")
        assert "failed to launch" in str(err)

        err = AgentProtocolError("protocol error")
        assert "protocol error" in str(err)
