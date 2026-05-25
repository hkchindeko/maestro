"""Agent runner protocol and domain models.

Defines the abstract `AgentRunner` interface and session/event models per SPEC §10.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from maestro.sandbox.base import SandboxManager


class AgentEventType(str, Enum):
    """Types of events emitted by the agent runner per SPEC §10.4."""

    SESSION_STARTED = "session_started"
    STARTUP_FAILED = "startup_failed"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    TURN_CANCELLED = "turn_cancelled"
    TURN_ENDED_WITH_ERROR = "turn_ended_with_error"
    TURN_INPUT_REQUIRED = "turn_input_required"
    APPROVAL_AUTO_APPROVED = "approval_auto_approved"
    UNSUPPORTED_TOOL_CALL = "unsupported_tool_call"
    NOTIFICATION = "notification"
    OTHER_MESSAGE = "other_message"
    MALFORMED = "malformed"


@dataclass
class TokenUsage:
    """Token usage from an agent event.

    Per SPEC §13.5: prefer absolute thread totals, track deltas.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AgentEvent:
    """Structured event emitted by the agent runner to the orchestrator.

    Per SPEC §10.4.
    """

    event_type: AgentEventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)
    usage: TokenUsage | None = None
    session_id: str | None = None
    codex_app_server_pid: str | None = None


@dataclass
class AgentSession:
    """State tracked while a coding-agent subprocess is running.

    Per SPEC §4.1.6.
    """

    session_id: str
    thread_id: str
    turn_id: str
    sandbox_id: str | None = None
    codex_app_server_pid: str | None = None
    last_codex_event: str | None = None
    last_codex_timestamp: datetime | None = None
    last_codex_message: str | None = None
    codex_input_tokens: int = 0
    codex_output_tokens: int = 0
    codex_total_tokens: int = 0
    last_reported_input_tokens: int = 0
    last_reported_output_tokens: int = 0
    last_reported_total_tokens: int = 0
    turn_count: int = 0

    def update_tokens(self, usage: TokenUsage) -> None:
        """Update token counters using delta tracking from absolute totals.

        Per SPEC §13.5: track deltas relative to last reported totals to avoid double-counting.
        """
        if usage.total_tokens > 0 and self.last_reported_total_tokens > 0:
            delta = usage.total_tokens - self.last_reported_total_tokens
            if delta > 0:
                self.codex_total_tokens += delta
        else:
            # First report or no previous total — use absolute values
            self.codex_input_tokens = usage.input_tokens
            self.codex_output_tokens = usage.output_tokens
            self.codex_total_tokens = usage.total_tokens

        self.last_reported_input_tokens = usage.input_tokens
        self.last_reported_output_tokens = usage.output_tokens
        self.last_reported_total_tokens = usage.total_tokens


@dataclass
class TurnResult:
    """Result of a single agent turn.

    Per SPEC §10.3 completion conditions.
    """

    success: bool
    error: str | None = None
    error_category: str | None = None
    usage: TokenUsage | None = None


# Callback type for event dispatch
EventCallback = Callable[[AgentEvent], None]


class AgentRunner(ABC):
    """Abstract base class for coding agent runners.

    Per SPEC §10.7, the agent runner wraps workspace + prompt + sandbox + app-server client.
    """

    def __init__(self, sandbox: SandboxManager | None = None) -> None:
        """Initialize the agent runner.

        Args:
            sandbox: Optional sandbox manager for provisioning sandbox
                environments. If None, implementations MAY use the workspace
                path directly as the execution environment (equivalent to
                ``sandbox.kind == "local"``).
        """
        self._sandbox = sandbox

    @abstractmethod
    async def start_session(
        self,
        workspace_path: Path,
        prompt: str,
        on_event: EventCallback | None = None,
    ) -> AgentSession:
        """Start a coding agent session.

        Per SPEC §10.2. Implementations SHOULD provision the sandbox
        environment before launching the agent subprocess.

        Args:
            workspace_path: Absolute path to the per-issue workspace.
            prompt: Rendered issue prompt for the first turn.
            on_event: Callback for events emitted to the orchestrator.

        Returns:
            AgentSession with session identifiers and initial state.
        """
        ...

    @abstractmethod
    async def run_turn(
        self,
        session: AgentSession,
        prompt: str,
    ) -> TurnResult:
        """Run a single coding agent turn.

        Args:
            session: The active agent session.
            prompt: The prompt for this turn (full prompt for first turn,
                continuation guidance for subsequent turns).

        Returns:
            TurnResult with success/failure status.
        """
        ...

    @abstractmethod
    async def stop_session(self, session: AgentSession) -> None:
        """Stop the coding agent session and clean up resources.

        Args:
            session: The active agent session to stop.
        """
        ...
