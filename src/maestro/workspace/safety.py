"""Path safety utilities for workspace management.

Implements SPEC §9.5 (Safety Invariants):
- Invariant 2: Workspace path MUST stay inside workspace root
- Invariant 3: Workspace key is sanitized
"""

from __future__ import annotations

import re
from pathlib import Path

# Only these characters are allowed in workspace directory names
_SAFE_KEY_PATTERN = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_key(identifier: str) -> str:
    """Sanitize an issue identifier to a workspace-safe key.

    Replaces any character not in [A-Za-z0-9._-] with '_'.

    Per SPEC §4.2 and §9.5.

    Args:
        identifier: The raw issue identifier (e.g., "ABC-123", "feat/some-issue").

    Returns:
        Sanitized key safe for use as a directory name.
    """
    return _SAFE_KEY_PATTERN.sub("_", identifier)


def is_path_under_root(path: Path, root: Path) -> bool:
    """Check if a resolved path is strictly under a resolved root directory.

    Per SPEC §9.5 Invariant 2: workspace_path must have workspace_root as a prefix.

    Args:
        path: The path to check.
        root: The root directory that must contain the path.

    Returns:
        True if the resolved path is under the resolved root.
    """
    resolved_path = path.resolve()
    resolved_root = root.resolve()

    # The path must be a descendant of root (not equal to root itself)
    try:
        resolved_path.relative_to(resolved_root)
        return True
    except ValueError:
        return False


def validate_workspace_path(workspace_path: Path, workspace_root: Path) -> None:
    """Validate that a workspace path is safely under the workspace root.

    Raises an error if the path is outside the root.

    Per SPEC §9.5 Invariant 2.

    Args:
        workspace_path: The workspace path to validate.
        workspace_root: The workspace root directory.

    Raises:
        WorkspacePathError: If the workspace path is not under the workspace root.
    """
    if not is_path_under_root(workspace_path, workspace_root):
        raise WorkspacePathError(
            f"Workspace path {workspace_path} is not under workspace root {workspace_root}"
        )


class WorkspacePathError(Exception):
    """Raised when a workspace path is not under the configured workspace root."""

    pass
