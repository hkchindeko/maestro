"""Sandbox manager protocol and domain models.

Defines the abstract ``SandboxManager`` interface per SPEC §3.1, §5.3.5, §10.1-10.2.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


class SandboxError(Exception):
    """Raised when a sandbox operation fails."""


@dataclass
class SandboxResult:
    """Result of sandbox provisioning.

    Attributes:
        sandbox_id: Unique identifier for the provisioned sandbox, used for
            teardown and observability.
        effective_path: The path where the agent subprocess should be launched.
            For local sandbox, this equals the workspace path.
    """

    sandbox_id: str
    effective_path: Path


class SandboxManager(ABC):
    """Abstract base class for AI sandbox provisioners.

    Manages the lifecycle of sandbox environments (local, Docker, Daytona, etc.)
    per SPEC §3.1 and §10.2.

    Each concrete implementation handles one ``sandbox.kind`` value.
    """

    @abstractmethod
    async def provision(self, workspace_path: Path) -> SandboxResult:
        """Provision a sandbox environment for the given workspace path.

        Args:
            workspace_path: Absolute path to the per-issue workspace directory.

        Returns:
            SandboxResult with sandbox identity and effective launch path.

        Raises:
            SandboxError: If provisioning fails.
        """
        ...

    @abstractmethod
    async def teardown(self, sandbox_id: str) -> None:
        """Tear down a previously provisioned sandbox.

        Teardown is best-effort — failures are logged but MUST NOT prevent
        session cleanup or workspace teardown from proceeding.

        Args:
            sandbox_id: The identifier returned by ``provision()``.
        """
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        """Check whether the sandbox backend is available.

        Synchronous pre-flight check suitable for startup validation.

        Returns:
            True if the sandbox backend is ready to provision environments.
        """
        ...