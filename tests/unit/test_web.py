"""Unit tests for web/HTTP dashboard module.

Tests the FastAPI application, REST API endpoints, error handling, and dashboard rendering.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from maestro.core.state import OrchestratorState, RetryEntry, RunningEntry
from maestro.tracker.base import Issue
from maestro.web.app import create_app


@pytest.fixture
def state() -> OrchestratorState:
    """Return a fresh orchestrator state for each test."""
    return OrchestratorState(poll_interval_ms=30000, max_concurrent_agents=10)


@pytest.fixture
def client(state: OrchestratorState) -> TestClient:
    """Return a FastAPI TestClient wired to the orchestrator state."""
    app = create_app(state)
    return TestClient(app)


@pytest.fixture
def sample_issue() -> Issue:
    """Return a sample issue for testing."""
    return Issue(
        id="abc-123",
        identifier="MT-649",
        title="Test Issue",
        state="In Progress",
    )


class TestStateEndpoint:
    """Tests for GET /api/v1/state."""

    def test_empty_state(self, client: TestClient) -> None:
        """State endpoint works with no running sessions."""
        response = client.get("/api/v1/state")
        assert response.status_code == 200
        data = response.json()
        assert "generated_at" in data
        assert data["counts"]["running"] == 0
        assert data["counts"]["retrying"] == 0
        assert data["running"] == []
        assert data["retrying"] == []
        assert "codex_totals" in data
        assert data["rate_limits"] is None

    def test_with_running_session(
        self, client: TestClient, state: OrchestratorState, sample_issue: Issue
    ) -> None:
        """State endpoint includes running sessions."""
        entry = RunningEntry(
            issue_id=sample_issue.id,
            issue_identifier=sample_issue.identifier,
            issue=sample_issue,
            session_id="thread-1-turn-1",
            last_agent_event="turn_completed",
            last_agent_message="Done",
            last_agent_timestamp=datetime.now(timezone.utc),
            agent_input_tokens=500,
            agent_output_tokens=200,
            agent_total_tokens=700,
        )
        state.running[sample_issue.id] = entry

        response = client.get("/api/v1/state")
        assert response.status_code == 200
        data = response.json()
        assert data["counts"]["running"] == 1
        assert data["counts"]["retrying"] == 0
        assert len(data["running"]) == 1
        row = data["running"][0]
        assert row["issue_id"] == "abc-123"
        assert row["issue_identifier"] == "MT-649"
        assert row["session_id"] == "thread-1-turn-1"
        assert row["last_event"] == "turn_completed"
        assert row["tokens"]["input_tokens"] == 500
        assert row["tokens"]["output_tokens"] == 200
        assert row["tokens"]["total_tokens"] == 700

    def test_with_retry_queue(
        self, client: TestClient, state: OrchestratorState
    ) -> None:
        """State endpoint includes retry queue entries."""
        due_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + 30000
        entry = RetryEntry(
            issue_id="def-456",
            identifier="MT-650",
            attempt=3,
            due_at_ms=due_ms,
            error="no available slots",
        )
        state.retry_attempts["def-456"] = entry

        response = client.get("/api/v1/state")
        assert response.status_code == 200
        data = response.json()
        assert data["counts"]["running"] == 0
        assert data["counts"]["retrying"] == 1
        assert len(data["retrying"]) == 1
        row = data["retrying"][0]
        assert row["issue_id"] == "def-456"
        assert row["issue_identifier"] == "MT-650"
        assert row["attempt"] == 3
        assert row["error"] == "no available slots"
        assert "due_at" in row

    def test_with_multiple_running_and_retrying(
        self,
        client: TestClient,
        state: OrchestratorState,
        sample_issue: Issue,
    ) -> None:
        """State endpoint handles multiple running sessions and retry entries."""
        # Two running
        entry1 = RunningEntry(
            issue_id="abc-123",
            issue_identifier="MT-649",
            issue=sample_issue,
            session_id="s1",
        )
        entry2 = RunningEntry(
            issue_id="abc-456",
            issue_identifier="MT-650",
            issue=Issue(id="abc-456", identifier="MT-650", title="Issue 2", state="Todo"),
            session_id="s2",
        )
        state.running["abc-123"] = entry1
        state.running["abc-456"] = entry2

        # One retrying
        retry = RetryEntry(
            issue_id="abc-789",
            identifier="MT-651",
            attempt=2,
            due_at_ms=1000000,
            error="some error",
        )
        state.retry_attempts["abc-789"] = retry

        response = client.get("/api/v1/state")
        assert response.status_code == 200
        data = response.json()
        assert data["counts"]["running"] == 2
        assert data["counts"]["retrying"] == 1


class TestIssueEndpoint:
    """Tests for GET /api/v1/{issue_identifier}."""

    def test_running_issue(
        self, client: TestClient, state: OrchestratorState, sample_issue: Issue
    ) -> None:
        """Issue endpoint returns details for a running issue."""
        entry = RunningEntry(
            issue_id="abc-123",
            issue_identifier="MT-649",
            issue=sample_issue,
            session_id="thread-1",
            last_agent_event="turn_completed",
            last_agent_timestamp=datetime.now(timezone.utc),
            last_agent_message="Working...",
            agent_input_tokens=100,
            agent_output_tokens=50,
            agent_total_tokens=150,
            retry_attempt=2,
        )
        state.running["abc-123"] = entry

        response = client.get("/api/v1/MT-649")
        assert response.status_code == 200
        data = response.json()
        assert data["issue_identifier"] == "MT-649"
        assert data["issue_id"] == "abc-123"
        assert data["status"] == "running"
        assert data["running"]["session_id"] == "thread-1"
        assert data["running"]["tokens"]["total_tokens"] == 150
        assert data["retry"] is None

    def test_retrying_issue(
        self, client: TestClient, state: OrchestratorState
    ) -> None:
        """Issue endpoint returns details for a retrying issue."""
        due_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + 5000
        entry = RetryEntry(
            issue_id="def-456",
            identifier="MT-650",
            attempt=3,
            due_at_ms=due_ms,
            error="stall timeout",
        )
        state.retry_attempts["def-456"] = entry

        response = client.get("/api/v1/MT-650")
        assert response.status_code == 200
        data = response.json()
        assert data["issue_identifier"] == "MT-650"
        assert data["status"] == "retrying"
        assert data["running"] is None
        assert data["retry"]["attempt"] == 3
        assert data["retry"]["error"] == "stall timeout"

    def test_unknown_issue(self, client: TestClient) -> None:
        """Issue endpoint returns 404 for unknown issues."""
        response = client.get("/api/v1/UNKNOWN-999")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "issue_not_found"


class TestRefreshEndpoint:
    """Tests for POST /api/v1/refresh."""

    def test_refresh_invokes_callback(self, state: OrchestratorState) -> None:
        """Refresh endpoint schedules the runtime refresh callback."""
        called = asyncio.Event()

        async def refresh() -> None:
            called.set()

        app = create_app(state, refresh_callback=refresh)
        client = TestClient(app)

        response = client.post("/api/v1/refresh")
        assert response.status_code == 202
        assert called.is_set()

    def test_refresh_accepted(self, client: TestClient) -> None:
        """Refresh endpoint returns 202 Accepted."""
        response = client.post("/api/v1/refresh")
        assert response.status_code == 202
        data = response.json()
        assert data["queued"] is True
        assert "coalesced" in data
        assert "requested_at" in data
        assert data["operations"] == ["poll", "reconcile"]

    def test_refresh_with_empty_body(self, client: TestClient) -> None:
        """Refresh endpoint accepts empty body."""
        response = client.post("/api/v1/refresh", json={})
        assert response.status_code == 202
        data = response.json()
        assert data["queued"] is True

    def test_refresh_coalesce(self, client: TestClient) -> None:
        """Repeated refresh requests are coalesced."""
        response1 = client.post("/api/v1/refresh")
        assert response1.status_code == 202

        response2 = client.post("/api/v1/refresh")
        assert response2.status_code == 202
        # Second request should be coalesced since event is not yet consumed
        assert response2.json()["coalesced"] is True


class TestMethodNotAllowed:
    """Tests for 405 Method Not Allowed responses.

    Note: Starlette's built-in 405 handler returns {"detail": "Method Not Allowed"},
    which is then wrapped by our custom HTTP exception handler into the error envelope.
    """

    def test_post_to_state_endpoint(self, client: TestClient) -> None:
        """POST to /api/v1/state returns 405."""
        response = client.post("/api/v1/state")
        assert response.status_code == 405
        data = response.json()
        # Starlette returns detail, which our handler wraps
        assert "detail" in data or "error" in data

    def test_delete_to_issue_endpoint(self, client: TestClient) -> None:
        """DELETE to /api/v1/{id} returns 405."""
        response = client.delete("/api/v1/MT-649")
        assert response.status_code == 405
        data = response.json()
        assert "detail" in data or "error" in data

    def test_get_to_refresh_endpoint(self, client: TestClient) -> None:
        """GET to /api/v1/refresh returns 404 (no GET route defined)."""
        response = client.get("/api/v1/refresh")
        # POST is the only defined method; GET returns 404 since no route matches
        assert response.status_code in (404, 405)


class TestDashboard:
    """Tests for the HTML dashboard at /."""

    def test_dashboard_renders(self, client: TestClient) -> None:
        """Dashboard returns HTML response."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_empty_state(self, client: TestClient) -> None:
        """Dashboard shows empty state with no sessions."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "No active sessions" in html
        assert "Retry queue empty" in html

    def test_dashboard_with_sessions(
        self, client: TestClient, state: OrchestratorState, sample_issue: Issue
    ) -> None:
        """Dashboard shows running session information."""
        entry = RunningEntry(
            issue_id="abc-123",
            issue_identifier="MT-649",
            issue=sample_issue,
            session_id="thread-1",
            last_agent_event="turn_completed",
            agent_input_tokens=100,
            agent_output_tokens=50,
            agent_total_tokens=150,
        )
        state.running["abc-123"] = entry

        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "MT-649" in html
        assert "thread-1" in html
        assert "150" in html or "Total Tokens" in html
        # Should have refresh button
        assert "refresh" in html.lower()
        assert "/api/v1/refresh" in html

    def test_dashboard_with_retry(
        self, client: TestClient, state: OrchestratorState
    ) -> None:
        """Dashboard shows retry queue entries."""
        retry = RetryEntry(
            issue_id="abc-789",
            identifier="MT-651",
            attempt=2,
            due_at_ms=1000000,
            error="stall timeout",
        )
        state.retry_attempts["abc-789"] = retry

        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "MT-651" in html
        assert "stall timeout" in html


class TestServerConfig:
    """Tests for ServerConfig model and port precedence."""

    def test_server_config_defaults(self) -> None:
        """ServerConfig defaults to port=None."""
        from maestro.core.config import ServerConfig

        sc = ServerConfig()
        assert sc.port is None

    def test_server_config_with_port(self) -> None:
        """ServerConfig accepts explicit port."""
        from maestro.core.config import ServerConfig

        sc = ServerConfig(port=8080)
        assert sc.port == 8080

    def test_workflow_config_includes_server(self) -> None:
        """WorkflowConfig includes server field."""
        from maestro.core.config import WorkflowConfig

        wc = WorkflowConfig()
        assert wc.server.port is None

    def test_port_precedence_cli_overrides_config(self) -> None:
        """CLI --port overrides server.port config."""
        from maestro.core.config import ServerConfig, WorkflowConfig

        # Simulate what the CLI does
        cli_port = 9090
        config = WorkflowConfig(server=ServerConfig(port=8080))

        effective_port = cli_port if cli_port is not None else config.server.port
        assert effective_port == 9090

    def test_port_falls_back_to_config(self) -> None:
        """When CLI port is not provided, use server.port."""
        from maestro.core.config import ServerConfig, WorkflowConfig

        cli_port = None
        config = WorkflowConfig(server=ServerConfig(port=8080))

        effective_port = cli_port if cli_port is not None else config.server.port
        assert effective_port == 8080

    def test_no_port_when_neither_set(self) -> None:
        """When neither CLI nor config has port, effective port is None."""
        from maestro.core.config import WorkflowConfig

        cli_port = None
        config = WorkflowConfig()

        effective_port = cli_port if cli_port is not None else config.server.port
        assert effective_port is None
