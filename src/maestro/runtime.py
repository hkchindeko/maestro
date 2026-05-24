"""Runtime composition and host lifecycle helpers."""

from __future__ import annotations

import asyncio
import contextlib
import signal
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from maestro.agent.base import AgentRunner
from maestro.agent.codex import CodexAgentRunner
from maestro.core.config import WorkflowConfig
from maestro.core.orchestrator import Orchestrator
from maestro.core.state import OrchestratorState
from maestro.core.workflow import WorkflowDefinition
from maestro.prompt.builder import PromptBuilder
from maestro.tracker.base import Tracker
from maestro.tracker.linear import LinearTracker
from maestro.workspace.manager import WorkspaceManager

StartServerFn = Callable[..., Awaitable[None]]


class RuntimeCompositionError(Exception):
    """Raised when runtime components cannot be built from configuration."""


@dataclass
class RuntimeComponents:
    """Concrete objects that make up one Maestro runtime."""

    tracker: Tracker
    workspace_manager: WorkspaceManager
    prompt_builder: PromptBuilder
    agent_runner: AgentRunner
    orchestrator: Orchestrator
    config: WorkflowConfig
    definition: WorkflowDefinition


def apply_cli_overrides(
    config: WorkflowConfig,
    tracker_kind: str | None = None,
    agent_kind: str | None = None,
    sandbox_kind: str | None = None,
    port: int | None = None,
) -> WorkflowConfig:
    """Return a config copy with CLI runtime overrides applied."""
    updated = config.model_copy(deep=True)

    if tracker_kind is not None:
        updated.tracker.kind = tracker_kind
    if agent_kind is not None:
        updated.agent.kind = agent_kind
    if sandbox_kind is not None:
        updated.sandbox.kind = sandbox_kind
    if port is not None:
        updated.server.port = port

    return updated


def build_tracker(config: WorkflowConfig) -> Tracker:
    """Build the configured tracker implementation."""
    if config.tracker.kind == "linear":
        return LinearTracker(config.tracker)
    raise RuntimeCompositionError(f"unsupported_tracker_kind: {config.tracker.kind!r}")


def build_agent_runner(config: WorkflowConfig) -> AgentRunner:
    """Build the configured coding-agent runner."""
    if config.agent.kind != "codex":
        raise RuntimeCompositionError(f"unsupported_agent_kind: {config.agent.kind!r}")

    command = config.agent.command or config.codex.command or "codex app-server"
    return CodexAgentRunner(
        command=command,
        read_timeout_ms=config.codex.read_timeout_ms,
        turn_timeout_ms=config.codex.turn_timeout_ms,
    )


def build_workspace_manager(config: WorkflowConfig) -> WorkspaceManager:
    """Build the workspace manager using the effective workspace root."""
    root = (
        Path(config.workspace.root)
        if config.workspace.root is not None
        else Path(tempfile.gettempdir()) / "symphony_workspaces"
    )
    return WorkspaceManager(root, config.hooks)


def build_components(definition: WorkflowDefinition, config: WorkflowConfig) -> RuntimeComponents:
    """Build all concrete runtime components from effective configuration."""
    if config.sandbox.kind != "local":
        raise RuntimeCompositionError(f"unsupported_sandbox_kind: {config.sandbox.kind!r}")

    tracker = build_tracker(config)
    workspace_manager = build_workspace_manager(config)
    prompt_builder = PromptBuilder()
    agent_runner = build_agent_runner(config)
    orchestrator = Orchestrator(
        tracker=tracker,
        workspace_manager=workspace_manager,
        agent_runner=agent_runner,
        prompt_builder=prompt_builder,
        config=config,
        definition=definition,
    )

    return RuntimeComponents(
        tracker=tracker,
        workspace_manager=workspace_manager,
        prompt_builder=prompt_builder,
        agent_runner=agent_runner,
        orchestrator=orchestrator,
        config=config,
        definition=definition,
    )


async def run_runtime(
    definition: WorkflowDefinition | None = None,
    config: WorkflowConfig | None = None,
    port: int | None = None,
    *,
    components: RuntimeComponents | None = None,
    start_server_fn: StartServerFn | None = None,
    install_signal_handlers: bool = True,
) -> None:
    """Run the orchestrator and optional HTTP server until shutdown or failure."""
    if components is None:
        if definition is None or config is None:
            raise RuntimeCompositionError("definition and config are required")
        components = build_components(definition, config)

    effective_port = port if port is not None else components.config.server.port
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        shutdown_event.set()

    if install_signal_handlers:
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.add_signal_handler(sig, request_shutdown)

    orchestrator_task = asyncio.create_task(
        components.orchestrator.start(),
        name="maestro-orchestrator",
    )
    tasks = {orchestrator_task}

    if effective_port is not None:
        if start_server_fn is None:
            from maestro.web.app import start_server

            start_server_fn = start_server
        server_task: asyncio.Task[None] = asyncio.create_task(
            _run_server(
                start_server_fn,
                components.orchestrator.state,
                effective_port,
                components.orchestrator.request_refresh,
            ),
            name="maestro-http-server",
        )
        tasks.add(server_task)

    shutdown_task = asyncio.create_task(shutdown_event.wait(), name="maestro-shutdown")
    wait_set = tasks | {shutdown_task}
    done, pending = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED)

    failure: BaseException | None = None
    if shutdown_task not in done:
        for task in done:
            with contextlib.suppress(asyncio.CancelledError):
                failure = task.exception()
            if failure is not None:
                break

    await components.orchestrator.stop()

    for task in pending:
        task.cancel()
    for task in tasks:
        if not task.done():
            task.cancel()

    await asyncio.gather(*wait_set, return_exceptions=True)

    if failure is not None:
        raise failure


async def _run_server(
    start_server_fn: StartServerFn,
    state: OrchestratorState,
    port: int,
    refresh_callback: Callable[[], Awaitable[None]],
) -> None:
    """Run the configured HTTP server function."""
    await start_server_fn(state, port, refresh_callback=refresh_callback)
