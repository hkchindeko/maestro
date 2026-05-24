"""Codex app-server agent runner.

Implements SPEC §10.1-10.7 for the Codex app-server stdio protocol.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maestro.agent.base import (
    AgentEvent,
    AgentEventType,
    AgentRunner,
    AgentSession,
    EventCallback,
    TokenUsage,
    TurnResult,
)
from maestro.agent.events import (
    parse_agent_event,
    parse_json_line,
)

logger = logging.getLogger(__name__)

# Default timeouts per SPEC §5.3.7
DEFAULT_READ_TIMEOUT_MS = 5000
DEFAULT_TURN_TIMEOUT_MS = 3600000


class AgentSessionError(Exception):
    """Base exception for agent session errors."""

    pass


class AgentTimeoutError(AgentSessionError):
    """Raised when an agent operation times out."""

    pass


class AgentLaunchError(AgentSessionError):
    """Raised when the agent subprocess fails to launch."""

    pass


class AgentProtocolError(AgentSessionError):
    """Raised when the agent protocol encounters an error."""

    pass


class CodexAgentRunner(AgentRunner):
    """Codex app-server agent runner using stdio JSON-RPC protocol.

    Per SPEC §10.1-10.7.
    """

    def __init__(
        self,
        command: str = "codex app-server",
        read_timeout_ms: int = DEFAULT_READ_TIMEOUT_MS,
        turn_timeout_ms: int = DEFAULT_TURN_TIMEOUT_MS,
    ) -> None:
        """Initialize the Codex agent runner.

        Args:
            command: The shell command to launch the app-server.
            read_timeout_ms: Request/response timeout in milliseconds.
            turn_timeout_ms: Total turn stream timeout in milliseconds.
        """
        self._command = command
        self._read_timeout = read_timeout_ms / 1000.0
        self._turn_timeout = turn_timeout_ms / 1000.0
        self._process: asyncio.subprocess.Process | None = None
        self._on_event: EventCallback | None = None
        self._current_session: AgentSession | None = None
        self._message_id = 0
        self._read_task: asyncio.Task[None] | None = None
        self._event_queue: asyncio.Queue[dict[str, Any]] | None = None

    async def start_session(
        self,
        workspace_path: Path,
        prompt: str,
        on_event: EventCallback | None = None,
    ) -> AgentSession:
        """Start a Codex app-server session.

        Per SPEC §10.2.

        Args:
            workspace_path: Absolute path to the per-issue workspace.
            prompt: Rendered issue prompt for the first turn.
            on_event: Callback for events emitted to the orchestrator.

        Returns:
            AgentSession with session identifiers.

        Raises:
            AgentLaunchError: If the subprocess fails to launch.
        """
        self._on_event = on_event
        self._event_queue = asyncio.Queue()

        # Launch the app-server subprocess
        await self._launch(self._command, workspace_path)

        # Initialize session (thread creation, prompt injection)
        session = await self._initialize_session(workspace_path, prompt)

        self._current_session = session

        # Start the message reader
        self._read_task = asyncio.create_task(self._read_messages())

        return session

    async def _launch(self, command: str, cwd: Path) -> None:
        """Launch the app-server subprocess via `bash -lc`.

        Per SPEC §10.1.

        Args:
            command: The shell command to execute.
            cwd: The working directory (workspace path).
        """
        logger.info("Launching agent: %s in %s", command, cwd)

        try:
            self._process = await asyncio.create_subprocess_exec(
                "bash",
                "-lc",
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                limit=10 * 1024 * 1024,  # 10MB max line size per SPEC §10.1
            )
        except Exception as e:
            raise AgentLaunchError(f"Failed to launch agent: {e}") from e

        logger.info("Agent launched with PID: %s", self._process.pid)

    async def _initialize_session(
        self,
        workspace_path: Path,
        prompt: str,
    ) -> AgentSession:
        """Initialize the agent session: thread creation, prompt injection.

        Per SPEC §10.2.

        Args:
            workspace_path: The workspace directory.
            prompt: The rendered issue prompt.

        Returns:
            AgentSession with thread_id and turn_id.
        """
        # Send thread creation request
        thread_response = await self._send_request(
            {
                "method": "thread/create",
                "params": {
                    "cwd": str(workspace_path),
                    "title": "Maestro session",
                },
            },
            timeout=self._read_timeout,
        )

        thread_id = thread_response.get("result", {}).get("threadId", "unknown")

        # Start first turn with the issue prompt
        turn_response = await self._send_request(
            {
                "method": "turn/start",
                "params": {
                    "threadId": thread_id,
                    "prompt": prompt,
                    "cwd": str(workspace_path),
                },
            },
            timeout=self._read_timeout,
        )

        turn_id = turn_response.get("result", {}).get("turnId", "unknown")

        session_id = f"{thread_id}-{turn_id}"

        session = AgentSession(
            session_id=session_id,
            thread_id=thread_id,
            turn_id=turn_id,
            codex_app_server_pid=str(self._process.pid) if self._process else None,
            turn_count=1,
        )

        # Emit session_started event
        self._emit_event(
            AgentEventType.SESSION_STARTED,
            session_id=session_id,
            payload={"thread_id": thread_id, "turn_id": turn_id},
        )

        return session

    async def run_turn(
        self,
        session: AgentSession,
        prompt: str,
    ) -> TurnResult:
        """Run a single coding agent turn.

        Per SPEC §10.3.

        Args:
            session: The active agent session.
            prompt: The prompt for this turn.

        Returns:
            TurnResult with success/failure status.
        """
        if self._process is None or self._process.stdin is None:
            return TurnResult(
                success=False,
                error="Agent process not available",
                error_category="port_exit",
            )

        try:
            # Wait for turn completion with timeout
            turn_result = await asyncio.wait_for(
                self._wait_for_turn_completion(session),
                timeout=self._turn_timeout,
            )
            return turn_result

        except asyncio.TimeoutError:
            self._emit_event(
                AgentEventType.TURN_FAILED,
                session_id=session.session_id,
                payload={"error": "turn_timeout"},
            )
            return TurnResult(
                success=False,
                error="Turn timed out",
                error_category="turn_timeout",
            )

    async def _wait_for_turn_completion(self, session: AgentSession) -> TurnResult:
        """Wait for the current turn to complete by processing events.

        Args:
            session: The active agent session.

        Returns:
            TurnResult with success/failure status.
        """
        if self._event_queue is None:
            return TurnResult(success=False, error="Event queue not available")

        while True:
            raw_event = await self._event_queue.get()
            event = parse_agent_event(raw_event)

            # Update session state
            session.last_codex_event = event.event_type.value
            session.last_codex_timestamp = event.timestamp
            session.last_codex_message = str(raw_event.get("message", ""))[:200]

            # Update token accounting
            if event.usage:
                session.update_tokens(event.usage)

            # Handle event types
            if event.event_type == AgentEventType.TURN_COMPLETED:
                return TurnResult(
                    success=True,
                    usage=event.usage,
                )

            if event.event_type == AgentEventType.TURN_FAILED:
                return TurnResult(
                    success=False,
                    error=str(raw_event.get("error", "unknown")),
                    error_category="turn_failed",
                )

            if event.event_type == AgentEventType.TURN_CANCELLED:
                return TurnResult(
                    success=False,
                    error="Turn cancelled",
                    error_category="turn_cancelled",
                )

            if event.event_type == AgentEventType.TURN_INPUT_REQUIRED:
                # High-trust policy: fail on user input required
                self._emit_event(
                    AgentEventType.TURN_INPUT_REQUIRED,
                    session_id=session.session_id,
                    payload=raw_event,
                )
                return TurnResult(
                    success=False,
                    error="User input required (high-trust policy: fail)",
                    error_category="turn_input_required",
                )

            if event.event_type == AgentEventType.APPROVAL_AUTO_APPROVED:
                self._emit_event(
                    AgentEventType.APPROVAL_AUTO_APPROVED,
                    session_id=session.session_id,
                    payload=raw_event,
                )
                # Auto-approve: continue processing

            if event.event_type == AgentEventType.UNSUPPORTED_TOOL_CALL:
                self._emit_event(
                    AgentEventType.UNSUPPORTED_TOOL_CALL,
                    session_id=session.session_id,
                    payload=raw_event,
                )
                # Continue session (don't stall)

            # Emit other events to orchestrator
            self._emit_event(
                event.event_type,
                session_id=session.session_id,
                payload=raw_event,
                usage=event.usage,
            )

    async def stop_session(self, session: AgentSession) -> None:
        """Stop the agent session and clean up.

        Per SPEC §10.7.

        Args:
            session: The active agent session to stop.
        """
        # Cancel the read task
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        # Terminate the process
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except (ProcessLookupError, asyncio.TimeoutError):
                self._process.kill()
                try:
                    await self._process.wait()
                except ProcessLookupError:
                    pass

        self._process = None
        self._current_session = None
        logger.info("Agent session stopped: %s", session.session_id)

    async def _send_request(
        self,
        message: dict[str, Any],
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the response.

        Args:
            message: The request message dict.
            timeout: Timeout in seconds.

        Returns:
            The response message dict.

        Raises:
            AgentTimeoutError: If the response times out.
            AgentProtocolError: If the response is an error.
        """
        if self._process is None or self._process.stdin is None:
            raise AgentProtocolError("Agent process not available")

        self._message_id += 1
        message["id"] = self._message_id

        # Write the message as newline-delimited JSON
        line = json.dumps(message) + "\n"
        self._process.stdin.write(line.encode("utf-8"))
        await self._process.stdin.drain()

        # Read response with timeout
        if self._process.stdout is None:
            raise AgentProtocolError("Agent stdout not available")

        try:
            response_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise AgentTimeoutError(f"Read timed out after {timeout}s") from None

        response = parse_json_line(response_line.decode("utf-8"))
        if response is None:
            raise AgentProtocolError("Invalid response from agent")

        # Check for error response
        if "error" in response:
            raise AgentProtocolError(f"Agent error: {response['error']}")

        return response

    async def _read_messages(self) -> None:
        """Read messages from the agent stdout in a background task."""
        if self._process is None or self._process.stdout is None:
            return

        while True:
            try:
                line = await self._process.stdout.readline()
                if not line:
                    break  # EOF

                raw = parse_json_line(line.decode("utf-8"))
                if raw is None:
                    continue

                if self._event_queue is not None:
                    await self._event_queue.put(raw)

            except Exception as e:
                logger.warning("Error reading agent messages: %s", e)
                break

    def _emit_event(
        self,
        event_type: AgentEventType,
        session_id: str | None = None,
        payload: dict[str, Any] | None = None,
        usage: TokenUsage | None = None,
    ) -> None:
        """Emit an event to the orchestrator callback.

        Args:
            event_type: The type of event.
            session_id: The session identifier.
            payload: The event payload.
            usage: Token usage data.
        """
        if self._on_event is None:
            return

        event = AgentEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            payload=payload or {},
            usage=usage,
            session_id=session_id,
            codex_app_server_pid=(
                str(self._process.pid) if self._process else None
            ),
        )

        try:
            self._on_event(event)
        except Exception as e:
            logger.warning("Event callback failed: %s", e)
