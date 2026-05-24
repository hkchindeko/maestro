"""Core orchestrator: poll loop, dispatch, reconcile, retry.

Implements SPEC §7 (Orchestration State Machine), §8 (Polling, Scheduling, Reconciliation),
and §16 (Reference Algorithms).
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maestro.agent.base import AgentRunner, AgentSession, EventCallback
from maestro.core.config import WorkflowConfig
from maestro.core.reconciliation import reconcile_stalled_runs, reconcile_tracker_states
from maestro.core.state import OrchestratorState, RetryEntry, RunningEntry
from maestro.core.validation import validate_dispatch_config
from maestro.core.workflow import WorkflowDefinition, resolve_config
from maestro.prompt.builder import PromptBuilder
from maestro.tracker.base import Issue, Tracker
from maestro.workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)

# Continuation retry delay (1 second) per SPEC §8.4
CONTINUATION_RETRY_DELAY_MS = 1000


class Orchestrator:
    """Central coordination layer for Maestro.

    Owns the poll tick loop, in-memory runtime state, dispatch decisions,
    retry scheduling, and reconciliation.

    Per SPEC §7, §8, §16.
    """

    def __init__(
        self,
        tracker: Tracker,
        workspace_manager: WorkspaceManager,
        agent_runner: AgentRunner,
        prompt_builder: PromptBuilder,
        config: WorkflowConfig,
        definition: WorkflowDefinition,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            tracker: Issue tracker adapter.
            workspace_manager: Workspace manager for per-issue directories.
            agent_runner: Coding agent runner.
            prompt_builder: Prompt template renderer.
            config: Resolved workflow configuration.
            definition: Parsed workflow definition.
        """
        self._tracker = tracker
        self._workspace = workspace_manager
        self._agent = agent_runner
        self._prompt_builder = prompt_builder
        self._config = config
        self._definition = definition
        self._state = OrchestratorState(
            poll_interval_ms=config.polling.interval_ms,
            max_concurrent_agents=config.agent.max_concurrent_agents,
        )
        self._running = False
        self._tick_task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()

    @property
    def state(self) -> OrchestratorState:
        """The orchestrator's runtime state."""
        return self._state

    async def start(self) -> None:
        """Start the orchestrator service.

        Per SPEC §16.1:
        1. Validate config
        2. Perform startup terminal cleanup
        3. Schedule immediate tick
        4. Enter event loop
        """
        logger.info("Starting orchestrator")

        # Validate config
        result = validate_dispatch_config(self._config, self._definition)
        if not result.ok:
            logger.error("Startup validation failed: %s", result.errors)
            raise RuntimeError(f"Startup validation failed: {result.errors}")

        # Startup terminal workspace cleanup
        await self._startup_terminal_cleanup()

        # Start the poll loop
        self._running = True
        self._tick_task = asyncio.create_task(self._poll_loop())

        # Wait for shutdown
        await self._shutdown_event.wait()

    async def stop(self) -> None:
        """Stop the orchestrator gracefully."""
        logger.info("Stopping orchestrator")
        self._running = False

        if self._tick_task and not self._tick_task.done():
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass

        self._shutdown_event.set()

    async def _poll_loop(self) -> None:
        """Main poll loop.

        Per SPEC §8.1 and §16.2.
        """
        while self._running:
            try:
                await self._on_tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Poll tick error: %s", e)

            # Sleep until next tick
            try:
                await asyncio.sleep(self._state.poll_interval_ms / 1000.0)
            except asyncio.CancelledError:
                break

    async def _on_tick(self) -> None:
        """Execute a single poll tick.

        Per SPEC §16.2:
        1. Reconcile running issues
        2. Run dispatch preflight validation
        3. Fetch candidate issues
        4. Sort by dispatch priority
        5. Dispatch eligible issues while slots remain
        """
        # Step 1: Reconcile
        await self._reconcile()

        # Step 2: Validate
        validation = validate_dispatch_config(self._config, self._definition)
        if not validation.ok:
            logger.warning("Dispatch validation failed: %s", validation.errors)
            return

        # Step 3: Fetch candidates
        try:
            candidates = await self._tracker.fetch_candidate_issues()
        except Exception as e:
            logger.warning("Tracker candidate fetch failed: %s", e)
            return

        # Step 4: Sort
        sorted_issues = self._sort_for_dispatch(candidates)

        # Step 5: Dispatch
        for issue in sorted_issues:
            slots = await self._state.available_slots()
            if slots <= 0:
                break

            if await self._should_dispatch(issue):
                await self._dispatch_issue(issue, attempt=None)

    async def _reconcile(self) -> None:
        """Reconcile running issues.

        Per SPEC §8.5:
        - Part A: Stall detection
        - Part B: Tracker state refresh
        """
        stall_timeout_ms = self._config.codex.stall_timeout_ms

        # Part A: Stall detection
        def on_stall(issue_id: str) -> None:
            logger.warning("Stalled issue %s — scheduling retry", issue_id)
            # Cancel the worker task
            asyncio.create_task(self._terminate_issue(issue_id, cleanup_workspace=True))

        await reconcile_stalled_runs(self._state, stall_timeout_ms, on_stall)

        # Part B: Tracker state refresh
        active_states = self._config.tracker.active_states
        terminal_states = self._config.tracker.terminal_states

        def on_terminal(issue_id: str) -> None:
            asyncio.create_task(self._terminate_issue(issue_id, cleanup_workspace=True))

        def on_non_active(issue_id: str) -> None:
            asyncio.create_task(self._terminate_issue(issue_id, cleanup_workspace=False))

        await reconcile_tracker_states(
            self._state,
            self._tracker,
            active_states,
            terminal_states,
            on_terminal,
            on_non_active,
        )

    async def _terminate_issue(self, issue_id: str, cleanup_workspace: bool) -> None:
        """Terminate a running issue.

        Args:
            issue_id: The issue to terminate.
            cleanup_workspace: Whether to clean up the workspace.
        """
        entry = await self._state.remove_running(issue_id)
        if entry is None:
            return

        # Cancel the worker task
        if entry.worker_task and not entry.worker_task.done():
            entry.worker_task.cancel()
            try:
                await entry.worker_task
            except (asyncio.CancelledError, Exception):
                pass

        # Add runtime to totals
        if entry.started_at:
            elapsed = (datetime.now(timezone.utc) - entry.started_at).total_seconds()
            self._state.codex_totals.add_runtime_seconds(elapsed)
            self._state.codex_totals.add_session_totals(entry)

        # Clean up workspace if terminal
        if cleanup_workspace:
            self._workspace.cleanup_for_issue(entry.issue_identifier)

        # Release claim
        await self._state.release_claim(issue_id)

        # Schedule retry
        await self._schedule_retry(
            issue_id,
            entry.issue_identifier,
            entry.retry_attempt + 1,
            error="terminated_by_reconciliation",
        )

    def _sort_for_dispatch(self, issues: list[Issue]) -> list[Issue]:
        """Sort issues by dispatch priority.

        Per SPEC §8.2:
        1. priority ascending (1..4 preferred; null/unknown sorts last)
        2. created_at oldest first
        3. identifier lexicographic tie-breaker
        """

        def sort_key(issue: Issue) -> tuple[int, float, str]:
            priority = issue.priority if issue.priority is not None else 999
            created = issue.created_at.timestamp() if issue.created_at else float("inf")
            identifier = issue.identifier or ""
            return (priority, created, identifier)

        return sorted(issues, key=sort_key)

    async def _should_dispatch(self, issue: Issue) -> bool:
        """Check if an issue is eligible for dispatch.

        Per SPEC §8.2.
        """
        # Must have required fields
        if not issue.id or not issue.identifier or not issue.title or not issue.state:
            return False

        # Must be in active state and not terminal
        active_lower = {s.lower() for s in self._config.tracker.active_states}
        terminal_lower = {s.lower() for s in self._config.tracker.terminal_states}
        state_lower = issue.state.lower()

        if state_lower not in active_lower or state_lower in terminal_lower:
            return False

        # Must not be running or claimed
        if await self._state.is_claimed(issue.id):
            return False

        # Todo blocker gating
        if state_lower == "todo":
            for blocker in issue.blocked_by:
                if blocker.state and blocker.state.lower() not in terminal_lower:
                    return False

        return True

    async def _dispatch_issue(self, issue: Issue, attempt: int | None) -> None:
        """Dispatch an issue to a worker.

        Per SPEC §16.4.

        Args:
            issue: The issue to dispatch.
            attempt: Retry attempt number (None for first run).
        """
        # Claim the issue
        claimed = await self._state.claim_issue(issue.id)
        if not claimed:
            return

        # Spawn worker task
        task = asyncio.create_task(self._run_worker(issue, attempt))
        task.add_done_callback(
            lambda t: asyncio.create_task(self._on_worker_done(issue.id, t))
        )

        entry = RunningEntry(
            issue_id=issue.id,
            issue_identifier=issue.identifier,
            issue=issue,
            retry_attempt=attempt or 0,
        )
        entry.worker_task = task

        await self._state.add_running(entry)
        logger.info(
            "Dispatched issue: id=%s identifier=%s attempt=%s",
            issue.id,
            issue.identifier,
            attempt,
        )

    async def _run_worker(self, issue: Issue, attempt: int | None) -> None:
        """Run a full worker attempt lifecycle.

        Per SPEC §16.5:
        1. Create/reuse workspace
        2. Build prompt
        3. Start agent session
        4. Run turns
        5. Clean up
        """
        workspace_result = None
        session: AgentSession | None = None

        try:
            # Step 1: Create/reuse workspace
            workspace_result = self._workspace.create_for_issue(issue.identifier)

            # Step 2: Run before_run hook
            self._workspace.run_before_run(workspace_result.path)

            # Step 3: Build prompt
            prompt = self._prompt_builder.render(
                self._definition.prompt_template,
                issue=self._build_issue_context(issue),
                attempt=attempt,
            )

            # Step 4: Start agent session
            def on_event(event: Any) -> None:
                # Update running entry with event data
                asyncio.create_task(self._on_agent_event(issue.id, event))

            session = await self._agent.start_session(
                workspace_path=workspace_result.path,
                prompt=prompt,
                on_event=on_event,
            )

            # Step 5: Run turns (up to max_turns)
            max_turns = self._config.agent.max_turns
            for turn_number in range(1, max_turns + 1):
                turn_prompt = prompt if turn_number == 1 else "Continue working on this issue."

                result = await self._agent.run_turn(session, turn_prompt)
                if not result.success:
                    logger.warning(
                        "Turn %d failed for issue %s: %s",
                        turn_number,
                        issue.identifier,
                        result.error,
                    )
                    break

                # Check if issue is still active
                try:
                    snapshots = await self._tracker.fetch_issue_states_by_ids([issue.id])
                    if snapshots:
                        snap = snapshots[0]
                        active_lower = {s.lower() for s in self._config.tracker.active_states}
                        if snap.state.lower() not in active_lower:
                            logger.info(
                                "Issue %s is no longer active (state=%s), stopping",
                                issue.identifier,
                                snap.state,
                            )
                            break
                except Exception as e:
                    logger.warning("Issue state refresh failed during turn: %s", e)

            # Normal exit
            self._workspace.run_after_run(workspace_result.path)
            await self._on_worker_exit(issue.id, normal=True)

        except Exception as e:
            logger.error("Worker failed for issue %s: %s", issue.identifier, e)
            if workspace_result:
                self._workspace.run_after_run(workspace_result.path)
            await self._on_worker_exit(issue.id, normal=False, error=str(e))

        finally:
            if session:
                await self._agent.stop_session(session)

    async def _on_agent_event(self, issue_id: str, event: Any) -> None:
        """Handle an event from the agent runner.

        Updates the running entry with event data.
        """
        entry = await self._state.get_running_entry(issue_id)
        if entry is None:
            return

        entry.last_agent_event = getattr(event, "event_type", None) or event.get("event")
        entry.last_agent_timestamp = getattr(event, "timestamp", None) or datetime.now(timezone.utc)
        entry.last_agent_message = str(
            getattr(event, "payload", event).get("message", "")
        )[:200]

        # Update token accounting
        usage = getattr(event, "usage", None)
        if usage:
            entry.agent_input_tokens = getattr(usage, "input_tokens", 0)
            entry.agent_output_tokens = getattr(usage, "output_tokens", 0)
            entry.agent_total_tokens = getattr(usage, "total_tokens", 0)

    async def _on_worker_done(self, issue_id: str, task: asyncio.Task[None]) -> None:
        """Callback when a worker task completes."""
        # Handled by _on_worker_exit
        pass

    async def _on_worker_exit(
        self,
        issue_id: str,
        normal: bool,
        error: str | None = None,
    ) -> None:
        """Handle worker exit.

        Per SPEC §16.6:
        - Normal exit: schedule continuation retry (attempt 1, 1s delay)
        - Abnormal exit: schedule exponential-backoff retry
        """
        entry = await self._state.remove_running(issue_id)
        if entry is None:
            return

        # Add runtime to totals
        if entry.started_at:
            elapsed = (datetime.now(timezone.utc) - entry.started_at).total_seconds()
            self._state.codex_totals.add_runtime_seconds(elapsed)
            self._state.codex_totals.add_session_totals(entry)

        # Mark as completed (bookkeeping)
        await self._state.mark_completed(issue_id)

        if normal:
            # Continuation retry: fixed 1s delay, attempt 1
            await self._schedule_retry(
                issue_id,
                entry.issue_identifier,
                1,
                delay_ms=CONTINUATION_RETRY_DELAY_MS,
            )
        else:
            # Failure-driven retry: exponential backoff
            next_attempt = entry.retry_attempt + 1
            await self._schedule_retry(
                issue_id,
                entry.issue_identifier,
                next_attempt,
                error=error or "worker_exited_abnormally",
            )

        # Release claim
        await self._state.release_claim(issue_id)

    async def _schedule_retry(
        self,
        issue_id: str,
        identifier: str,
        attempt: int,
        delay_ms: int | None = None,
        error: str | None = None,
    ) -> None:
        """Schedule a retry for an issue.

        Per SPEC §8.4.

        Args:
            issue_id: The issue ID.
            identifier: Human-readable identifier.
            attempt: Retry attempt number (1-based).
            delay_ms: Delay in milliseconds (computed if None).
            error: Error message for failure-driven retries.
        """
        if delay_ms is None:
            # Exponential backoff: min(10000 * 2^(attempt-1), max_retry_backoff_ms)
            base_delay = 10000
            max_backoff = self._config.agent.max_retry_backoff_ms
            delay_ms = min(base_delay * (2 ** (attempt - 1)), max_backoff)

        due_at_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + delay_ms

        entry = RetryEntry(
            issue_id=issue_id,
            identifier=identifier,
            attempt=attempt,
            due_at_ms=due_at_ms,
            error=error,
        )

        # Schedule the retry timer
        timer_task = asyncio.create_task(self._retry_timer(issue_id, delay_ms / 1000.0))
        entry.timer_handle = timer_task

        await self._state.add_retry(entry)

        logger.info(
            "Scheduled retry: issue_id=%s identifier=%s attempt=%d delay_ms=%d",
            issue_id,
            identifier,
            attempt,
            delay_ms,
        )

    async def _retry_timer(self, issue_id: str, delay_sec: float) -> None:
        """Sleep until retry time, then attempt re-dispatch."""
        try:
            await asyncio.sleep(delay_sec)
        except asyncio.CancelledError:
            return

        # Retry timer fired — attempt re-dispatch
        await self._on_retry_timer_fired(issue_id)

    async def _on_retry_timer_fired(self, issue_id: str) -> None:
        """Handle retry timer firing.

        Per SPEC §8.4 and §16.6:
        1. Fetch active candidates
        2. Find the specific issue
        3. If not found, release claim
        4. If eligible and slots available, dispatch
        5. If eligible but no slots, requeue
        """
        retry_entry = await self._state.remove_retry(issue_id)
        if retry_entry is None:
            return

        try:
            candidates = await self._tracker.fetch_candidate_issues()
        except Exception as e:
            logger.warning("Retry poll failed for issue %s: %s", issue_id, e)
            await self._schedule_retry(
                issue_id,
                retry_entry.identifier,
                retry_entry.attempt + 1,
                error="retry_poll_failed",
            )
            return

        # Find the issue
        issue = next((i for i in candidates if i.id == issue_id), None)
        if issue is None:
            logger.info("Issue %s not found in candidates, releasing claim", issue_id)
            await self._state.release_claim(issue_id)
            return

        # Check slots
        slots = await self._state.available_slots()
        if slots <= 0:
            logger.warning("No slots available for retry of issue %s, requeuing", issue_id)
            await self._schedule_retry(
                issue_id,
                issue.identifier,
                retry_entry.attempt + 1,
                error="no available orchestrator slots",
            )
            return

        # Dispatch
        await self._dispatch_issue(issue, attempt=retry_entry.attempt)

    async def _startup_terminal_cleanup(self) -> None:
        """Clean up workspaces for terminal issues on startup.

        Per SPEC §8.6.
        """
        try:
            terminal_issues = await self._tracker.fetch_issues_by_states(
                self._config.tracker.terminal_states
            )
            for issue in terminal_issues:
                self._workspace.cleanup_for_issue(issue.identifier)
                logger.info("Cleaned up terminal workspace: %s", issue.identifier)
        except Exception as e:
            logger.warning("Startup terminal cleanup failed: %s", e)

    def _build_issue_context(self, issue: Issue) -> Any:
        """Build an issue context for prompt rendering.

        Args:
            issue: The normalized issue.

        Returns:
            An object compatible with the prompt builder's issue parameter.
        """
        from maestro.prompt.models import BlockerRef, IssueContext

        return IssueContext(
            id=issue.id,
            identifier=issue.identifier,
            title=issue.title,
            description=issue.description,
            priority=issue.priority,
            state=issue.state,
            branch_name=issue.branch_name,
            url=issue.url,
            labels=issue.labels,
            blocked_by=[
                BlockerRef(id=b.id, identifier=b.identifier, state=b.state)
                for b in issue.blocked_by
            ],
            created_at=issue.created_at,
            updated_at=issue.updated_at,
        )
