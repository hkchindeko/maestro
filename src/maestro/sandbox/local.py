"""Local sandbox implementation.

No-op sandbox for ``sandbox.kind == "local"`` — the workspace path IS the sandbox.
Uses the host filesystem directly with no container isolation.

Implements SPEC §5.3.5 (``sandbox.kind == "local"``) and §10.1.
"""

from __future__ import annotations

import logging
from pathlib import Path

from maestro.sandbox.base import SandboxError, SandboxManager, SandboxResult

logger = logging.getLogger(__name__)


class LocalSandbox(SandboxManager):
    """No-op sandbox that uses the local filesystem directly.

    When ``sandbox.kind == "local"``, the workspace path itself is the sandbox
    environment. No container, VM, or remote sandbox is provisioned.

    Workspace cleanup is owned by ``WorkspaceManager``, so ``teardown()`` is a
    no-op.
    """

    async def provision(self, workspace_path: Path) -> SandboxResult:
        """Verify the workspace path exists and return it as the sandbox.

        Args:
            workspace_path: Absolute path to the per-issue workspace directory.

        Returns:
            SandboxResult with sandbox_id = str(workspace_path) and
            effective_path = workspace_path.

        Raises:
            SandboxError: If the workspace path does not exist or is not a directory.
        """
        if not workspace_path.exists():
            logger.error("Workspace path does not exist: %s", workspace_path)
            raise SandboxError(f"Workspace path does not exist: {workspace_path}")

        if not workspace_path.is_dir():
            logger.error("Workspace path is not a directory: %s", workspace_path)
            raise SandboxError(f"Workspace path is not a directory: {workspace_path}")

        sandbox_id = str(workspace_path)
        logger.debug("Local sandbox provisioned: %s", sandbox_id)
        return SandboxResult(sandbox_id=sandbox_id, effective_path=workspace_path)

    async def teardown(self, sandbox_id: str) -> None:
        """No-op teardown — workspace cleanup is owned by WorkspaceManager.

        Args:
            sandbox_id: The sandbox identifier (ignored for local sandbox).
        """
        logger.debug("Local sandbox teardown (no-op): %s", sandbox_id)

    def is_ready(self) -> bool:
        """The local sandbox is always ready.

        Returns:
            True — local execution has no external dependencies.
        """
        return True