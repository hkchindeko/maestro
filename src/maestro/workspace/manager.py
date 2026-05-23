"""Workspace manager for per-issue workspace directories.

Implements SPEC §9.1 (Workspace Layout), §9.2 (Workspace Creation and Reuse),
§9.4 (Workspace Hooks), and §9.5 (Safety Invariants).
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from maestro.core.config import HooksConfig

from maestro.workspace.hooks import HookResult, run_hook, run_hook_best_effort
from maestro.workspace.safety import sanitize_key, validate_workspace_path, WorkspacePathError

logger = logging.getLogger(__name__)


class WorkspaceError(Exception):
    """Base exception for workspace operations."""

    pass


@dataclass
class WorkspaceResult:
    """Result of workspace creation or lookup.

    Attributes:
        path: Absolute workspace path.
        workspace_key: Sanitized issue identifier used as directory name.
        created_now: True if the directory was created during this call.
    """

    path: Path
    workspace_key: str
    created_now: bool


class WorkspaceManager:
    """Manages per-issue workspace directories and lifecycle hooks.

    Per SPEC §9:
    - Creates/reuses workspace directories under a configured root
    - Executes lifecycle hooks with timeout enforcement
    - Enforces path safety invariants
    """

    def __init__(
        self,
        workspace_root: Path,
        hooks_config: HooksConfig | None = None,
    ) -> None:
        """Initialize the workspace manager.

        Args:
            workspace_root: Absolute path to the workspace root directory.
            hooks_config: Optional hooks configuration for lifecycle scripts.
        """
        self._workspace_root = workspace_root.resolve()
        self._hooks = hooks_config or HooksConfig()

        # Ensure workspace root exists
        self._workspace_root.mkdir(parents=True, exist_ok=True)

    @property
    def workspace_root(self) -> Path:
        """The resolved workspace root directory."""
        return self._workspace_root

    def _workspace_path(self, identifier: str) -> tuple[Path, str]:
        """Compute the workspace path for an issue identifier.

        Args:
            identifier: The raw issue identifier.

        Returns:
            Tuple of (workspace_path, workspace_key).
        """
        key = sanitize_key(identifier)
        path = self._workspace_root / key
        return path, key

    def create_for_issue(self, identifier: str) -> WorkspaceResult:
        """Create or reuse a workspace for an issue.

        Per SPEC §9.2:
        1. Sanitize identifier to workspace_key
        2. Compute workspace path under workspace root
        3. Ensure the workspace path exists as a directory
        4. Mark created_now=True only if directory was created during this call
        5. If created_now=True, run after_create hook if configured

        Args:
            identifier: The issue identifier.

        Returns:
            WorkspaceResult with path, key, and created_now flag.

        Raises:
            WorkspacePathError: If the computed path is not under workspace root.
            WorkspaceError: If workspace creation fails or after_create hook fails.
        """
        path, key = self._workspace_path(identifier)

        # Validate path safety (Invariant 2)
        validate_workspace_path(path, self._workspace_root)

        created_now = False

        # Handle existing non-directory path (SPEC §17.2)
        if path.exists() and not path.is_dir():
            logger.warning("Non-directory path at workspace location: %s, removing", path)
            path.unlink()

        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                created_now = True
                logger.info("Created workspace: %s", path)
            except OSError as e:
                raise WorkspaceError(f"Failed to create workspace {path}: {e}") from e

        # Run after_create hook only on new workspace creation
        if created_now and self._hooks.after_create:
            try:
                run_hook(
                    self._hooks.after_create,
                    path,
                    self._hooks.timeout_ms,
                )
            except Exception as e:
                # after_create failure is fatal to workspace creation (SPEC §9.4)
                logger.error("after_create hook failed: %s", e)
                # Clean up partially created directory
                if path.exists():
                    shutil.rmtree(path, ignore_errors=True)
                raise WorkspaceError(f"after_create hook failed: {e}") from e

        return WorkspaceResult(path=path, workspace_key=key, created_now=created_now)

    def run_before_run(self, workspace_path: Path) -> HookResult:
        """Run the before_run hook before an agent attempt.

        Per SPEC §9.4: before_run failure aborts the current run attempt.

        Args:
            workspace_path: The workspace directory to run the hook in.

        Returns:
            HookResult on success.

        Raises:
            WorkspaceError: If the hook fails or times out.
        """
        if not self._hooks.before_run:
            return HookResult(success=True)

        try:
            return run_hook(
                self._hooks.before_run,
                workspace_path,
                self._hooks.timeout_ms,
            )
        except Exception as e:
            raise WorkspaceError(f"before_run hook failed: {e}") from e

    def run_after_run(self, workspace_path: Path) -> None:
        """Run the after_run hook after an agent attempt.

        Per SPEC §9.4: after_run failure is logged but ignored.

        Args:
            workspace_path: The workspace directory to run the hook in.
        """
        if not self._hooks.after_run:
            return

        run_hook_best_effort(
            self._hooks.after_run,
            workspace_path,
            self._hooks.timeout_ms,
        )

    def run_before_remove(self, workspace_path: Path) -> None:
        """Run the before_remove hook before workspace deletion.

        Per SPEC §9.4: before_remove failure is logged but ignored.

        Args:
            workspace_path: The workspace directory to run the hook in.
        """
        if not workspace_path.exists():
            return

        if not self._hooks.before_remove:
            return

        run_hook_best_effort(
            self._hooks.before_remove,
            workspace_path,
            self._hooks.timeout_ms,
        )

    def cleanup_for_issue(self, identifier: str) -> None:
        """Clean up the workspace for a terminal issue.

        Per SPEC §8.6 and §9.4:
        - Run before_remove hook if configured (failure logged and ignored)
        - Remove the workspace directory
        - If directory does not exist, cleanup is a no-op

        Args:
            identifier: The issue identifier.
        """
        path, _ = self._workspace_path(identifier)

        if not path.exists():
            return

        # Run before_remove hook (failure logged and ignored)
        self.run_before_remove(path)

        try:
            shutil.rmtree(path, ignore_errors=True)
            logger.info("Cleaned up workspace: %s", path)
        except OSError as e:
            logger.warning("Failed to remove workspace %s: %s", path, e)

    def validate_agent_cwd(self, workspace_path: Path) -> None:
        """Validate that the agent cwd equals the workspace path.

        Per SPEC §9.5 Invariant 1: Run the coding agent only in the per-issue workspace path.

        Args:
            workspace_path: The workspace path that should be the agent cwd.

        Raises:
            WorkspacePathError: If the path is not under workspace root.
        """
        validate_workspace_path(workspace_path, self._workspace_root)
