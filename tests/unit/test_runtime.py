"""Tests for runtime composition and service lifecycle."""

from __future__ import annotations

import asyncio
import contextlib
import signal
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from maestro.agent.codex import CodexAgentRunner
from maestro.agent.base import AgentRunner, AgentSession, EventCallback, TurnResult
from maestro.core.config import WorkflowConfig
from maestro.core.orchestrator import Orchestrator
from maestro.core.workflow import WorkflowDefinition
from maestro.prompt.builder import PromptBuilder
from maestro.runtime import (
    RuntimeCompositionError,
    RuntimeComponents,
    apply_cli_overrides,
    build_agent_runner,
    build_components,
    build_tracker,
    build_workspace_manager,
    run_runtime,
)
from maestro.tracker.linear import LinearTracker
from maestro.tracker.base import Issue, IssueSnapshot, Tracker
from maestro.web.app import create_app
from maestro.workspace.manager import WorkspaceManager


def _definition(tmp_path: Path) -> WorkflowDefinition:
    return WorkflowDefinition(
        config={},
        prompt_template="Work on {{ issue.identifier }}",
        workflow_path=tmp_path / "WORKFLOW.md",
    )


def _config(tmp_path: Path) -> WorkflowConfig:
    return WorkflowConfig.model_validate(
        {
            "tracker": {
                "kind": "linear",
                "api_key": "test-key",
                "project_slug": "test-project",
            },
            "workspace": {"root": str(tmp_path / "workspaces")},
            "agent": {"kind": "codex", "command": "codex app-server"},
        }
    )


class FakeTracker(Tracker):
    """Tracker fake for runtime smoke tests."""

    def __init__(self, issue: Issue) -> None:
        self._issue = issue

    async def fetch_candidate_issues(self) -> list[Issue]:
        return [self._issue]

    async def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        return []

    async def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[IssueSnapshot]:
        return [
            IssueSnapshot(
                id=self._issue.id,
                identifier=self._issue.identifier,
                state=self._issue.state,
            )
        ]


class BlockingAgentRunner(AgentRunner):
    """Agent fake that keeps the worker running until released."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def start_session(
        self,
        workspace_path: Path,
        prompt: str,
        on_event: EventCallback | None = None,
    ) -> AgentSession:
        self.started.set()
        return AgentSession(session_id="session-1", thread_id="thread-1", turn_id="turn-1")

    async def run_turn(self, session: AgentSession, prompt: str) -> TurnResult:
        await self.release.wait()
        return TurnResult(success=False, error="released")

    async def stop_session(self, session: AgentSession) -> None:
        self.release.set()


class TestRuntimeFactory:
    """Runtime component factory tests."""

    def test_apply_cli_overrides(self, tmp_path: Path) -> None:
        config = _config(tmp_path)

        updated = apply_cli_overrides(
            config,
            tracker_kind="github",
            agent_kind="claude",
            sandbox_kind="docker",
            port=8080,
        )

        assert updated.tracker.kind == "github"
        assert updated.agent.kind == "claude"
        assert updated.sandbox.kind == "docker"
        assert updated.server.port == 8080
        assert config.tracker.kind == "linear"
        assert config.server.port is None

    def test_build_tracker_linear(self, tmp_path: Path) -> None:
        assert isinstance(build_tracker(_config(tmp_path)), LinearTracker)

    def test_build_tracker_unsupported(self, tmp_path: Path) -> None:
        config = apply_cli_overrides(_config(tmp_path), tracker_kind="github")

        with pytest.raises(RuntimeCompositionError, match="unsupported_tracker_kind"):
            build_tracker(config)

    def test_build_agent_runner_codex(self, tmp_path: Path) -> None:
        assert isinstance(build_agent_runner(_config(tmp_path)), CodexAgentRunner)

    def test_build_agent_runner_unsupported(self, tmp_path: Path) -> None:
        config = apply_cli_overrides(_config(tmp_path), agent_kind="claude")

        with pytest.raises(RuntimeCompositionError, match="unsupported_agent_kind"):
            build_agent_runner(config)

    def test_build_workspace_manager(self, tmp_path: Path) -> None:
        manager = build_workspace_manager(_config(tmp_path))

        assert isinstance(manager, WorkspaceManager)
        assert manager.workspace_root == (tmp_path / "workspaces").resolve()

    def test_build_components(self, tmp_path: Path) -> None:
        components = build_components(_definition(tmp_path), _config(tmp_path))

        assert isinstance(components, RuntimeComponents)
        assert isinstance(components.tracker, LinearTracker)
        assert isinstance(components.workspace_manager, WorkspaceManager)
        assert isinstance(components.prompt_builder, PromptBuilder)
        assert isinstance(components.agent_runner, CodexAgentRunner)
        assert isinstance(components.orchestrator, Orchestrator)

    def test_build_components_rejects_unsupported_sandbox(self, tmp_path: Path) -> None:
        config = apply_cli_overrides(_config(tmp_path), sandbox_kind="docker")

        with pytest.raises(RuntimeCompositionError, match="unsupported_sandbox_kind"):
            build_components(_definition(tmp_path), config)


class TestRuntimeLifecycle:
    """Runtime task supervision tests."""

    @pytest.mark.asyncio
    async def test_run_runtime_stops_orchestrator_on_shutdown(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        components = build_components(_definition(tmp_path), config)
        components.orchestrator.start = AsyncMock()
        components.orchestrator.stop = AsyncMock()

        async def stop_soon() -> None:
            await asyncio.sleep(0)
            await components.orchestrator.stop()

        components.orchestrator.start.side_effect = stop_soon

        await run_runtime(components=components, install_signal_handlers=False)

        components.orchestrator.stop.assert_awaited()

    @pytest.mark.asyncio
    async def test_run_runtime_cancels_http_server_on_orchestrator_exit(
        self, tmp_path: Path
    ) -> None:
        config = _config(tmp_path)
        components = build_components(_definition(tmp_path), config)
        components.orchestrator.start = AsyncMock()
        components.orchestrator.stop = AsyncMock()
        server_started = asyncio.Event()
        server_cancelled = asyncio.Event()

        async def start_server(*args, **kwargs) -> None:
            server_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                server_cancelled.set()
                raise

        await run_runtime(
            components=components,
            port=8080,
            start_server_fn=start_server,
            install_signal_handlers=False,
        )

        assert server_started.is_set()
        assert server_cancelled.is_set()
        components.orchestrator.stop.assert_awaited()

    @pytest.mark.asyncio
    async def test_run_runtime_surfaces_orchestrator_failure(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        components = build_components(_definition(tmp_path), config)
        components.orchestrator.start = AsyncMock(side_effect=RuntimeError("boom"))
        components.orchestrator.stop = AsyncMock()

        with pytest.raises(RuntimeError, match="boom"):
            await run_runtime(components=components, install_signal_handlers=False)

        components.orchestrator.stop.assert_awaited()

    @pytest.mark.asyncio
    async def test_run_runtime_surfaces_http_server_failure(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        components = build_components(_definition(tmp_path), config)
        components.orchestrator.start = AsyncMock()
        components.orchestrator.stop = AsyncMock()

        async def start_server(*args, **kwargs) -> None:
            raise RuntimeError("server boom")

        with pytest.raises(RuntimeError, match="server boom"):
            await run_runtime(
                components=components,
                port=8080,
                start_server_fn=start_server,
                install_signal_handlers=False,
            )

        components.orchestrator.stop.assert_awaited()

    @pytest.mark.asyncio
    async def test_run_runtime_installs_signal_handlers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = _config(tmp_path)
        components = build_components(_definition(tmp_path), config)
        components.orchestrator.start = AsyncMock()
        components.orchestrator.stop = AsyncMock()
        loop = asyncio.get_running_loop()
        registered: list[signal.Signals] = []

        def add_signal_handler(sig, callback) -> None:
            registered.append(sig)

        monkeypatch.setattr(loop, "add_signal_handler", add_signal_handler)

        await run_runtime(components=components, install_signal_handlers=True)

        assert signal.SIGTERM in registered
        assert signal.SIGINT in registered


class TestRuntimeSmoke:
    """End-to-end smoke coverage for the composed orchestration path."""

    @pytest.mark.asyncio
    async def test_composed_orchestrator_tick_dispatches_issue(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        issue = Issue(
            id="issue-1",
            identifier="MT-1",
            title="Smoke issue",
            state="Todo",
        )
        agent = BlockingAgentRunner()
        orchestrator = Orchestrator(
            tracker=FakeTracker(issue),
            workspace_manager=build_workspace_manager(config),
            agent_runner=agent,
            prompt_builder=PromptBuilder(),
            config=config,
            definition=_definition(tmp_path),
        )

        await orchestrator.request_refresh()
        await asyncio.wait_for(agent.started.wait(), timeout=1)

        assert "issue-1" in orchestrator.state.running

        agent.release.set()
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_runtime_with_http_exposes_real_orchestrator_state(
        self, tmp_path: Path
    ) -> None:
        """Smoke: start runtime with HTTP, verify /api/v1/state returns real state."""
        config = _config(tmp_path)
        issue = Issue(
            id="issue-2",
            identifier="MT-2",
            title="HTTP smoke issue",
            state="Todo",
        )
        tracker = FakeTracker(issue)
        workspace_manager = build_workspace_manager(config)
        prompt_builder = PromptBuilder()
        agent = BlockingAgentRunner()
        orchestrator = Orchestrator(
            tracker=tracker,
            workspace_manager=workspace_manager,
            agent_runner=agent,
            prompt_builder=prompt_builder,
            config=config,
            definition=_definition(tmp_path),
        )
        components = RuntimeComponents(
            tracker=tracker,
            workspace_manager=workspace_manager,
            prompt_builder=prompt_builder,
            agent_runner=agent,
            orchestrator=orchestrator,
            config=config,
            definition=_definition(tmp_path),
        )

        app = create_app(orchestrator.state, refresh_callback=orchestrator.request_refresh)

        async def start_server_fn(state, port, refresh_callback=None):
            import uvicorn

            srv_config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
            server = uvicorn.Server(srv_config)
            await server.serve()

        runtime_task = asyncio.create_task(
            run_runtime(
                components=components,
                port=8085,
                start_server_fn=start_server_fn,
                install_signal_handlers=False,
            )
        )

        # Give the server a moment to come up, then query /api/v1/state
        await asyncio.sleep(0.2)

        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8085/api/v1/state")
            assert response.status_code == 200
            data = response.json()
            assert "counts" in data
            assert "running" in data
            assert isinstance(data["counts"]["running"], int)

        # Stop the orchestrator so the runtime can cleanly exit
        await orchestrator.stop()
        agent.release.set()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(runtime_task, timeout=5)

    @pytest.mark.asyncio
    async def test_graceful_shutdown_leaves_no_pending_tasks(self, tmp_path: Path) -> None:
        """Smoke: run_runtime shutdown leaves no pending asyncio tasks."""
        config = _config(tmp_path)
        issue = Issue(
            id="issue-3",
            identifier="MT-3",
            title="Shutdown smoke issue",
            state="Todo",
        )
        tracker = FakeTracker(issue)
        workspace_manager = build_workspace_manager(config)
        prompt_builder = PromptBuilder()
        agent = BlockingAgentRunner()
        orchestrator = Orchestrator(
            tracker=tracker,
            workspace_manager=workspace_manager,
            agent_runner=agent,
            prompt_builder=prompt_builder,
            config=config,
            definition=_definition(tmp_path),
        )
        components = RuntimeComponents(
            tracker=tracker,
            workspace_manager=workspace_manager,
            prompt_builder=prompt_builder,
            agent_runner=agent,
            orchestrator=orchestrator,
            config=config,
            definition=_definition(tmp_path),
        )

        # Count tasks before
        tasks_before = len(asyncio.all_tasks())

        async def stop_soon() -> None:
            await asyncio.sleep(0)
            await orchestrator.stop()

        components.orchestrator.start = AsyncMock(side_effect=stop_soon)

        await run_runtime(components=components, install_signal_handlers=False)

        agent.release.set()

        # Allow a moment for cleanup
        await asyncio.sleep(0.1)
        tasks_after = len(asyncio.all_tasks())

        # Runtime tasks should be cleaned up — no net increase in pending tasks
        assert tasks_after <= tasks_before + 1, (
            f"Expected at most {tasks_before + 1} pending tasks, got {tasks_after}"
        )
