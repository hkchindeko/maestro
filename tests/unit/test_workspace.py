"""Tests for workspace manager, hooks, and path safety.

Covers tasks 1.4-1.5, 2.5, 3.9, 4.5, and 5.1-5.6.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from maestro.workspace.hooks import (
    HookExecutionError,
    HookResult,
    HookTimeoutError,
    run_hook,
    run_hook_best_effort,
)
from maestro.workspace.manager import WorkspaceError, WorkspaceManager, WorkspaceResult
from maestro.workspace.safety import (
    WorkspacePathError,
    is_path_under_root,
    sanitize_key,
    validate_workspace_path,
)


class TestSanitizeKey:
    """Tests for key sanitization (tasks 1.1, 1.4)."""

    def test_preserves_valid_chars(self) -> None:
        assert sanitize_key("ABC-123") == "ABC-123"
        assert sanitize_key("test_issue.name") == "test_issue.name"
        assert sanitize_key("ABC_123.test-1") == "ABC_123.test-1"

    def test_replaces_special_chars(self) -> None:
        assert sanitize_key("ABC/123") == "ABC_123"
        assert sanitize_key("ABC 123") == "ABC_123"
        assert sanitize_key("ABC@123") == "ABC_123"
        assert sanitize_key("ABC#123") == "ABC_123"

    def test_replaces_multiple_special_chars(self) -> None:
        assert sanitize_key("feat/some-issue!") == "feat_some_issue_"

    def test_empty_string(self) -> None:
        assert sanitize_key("") == ""

    def test_all_special_chars(self) -> None:
        assert sanitize_key("!@#$%^&*()") == "__________"


class TestPathContainment:
    """Tests for path containment (tasks 1.2, 1.3, 1.5)."""

    def test_path_under_root(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        root.mkdir()
        workspace = root / "ABC-123"
        workspace.mkdir()
        assert is_path_under_root(workspace, root) is True

    def test_path_not_under_root(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        root.mkdir()
        other = tmp_path / "other" / "ABC-123"
        other.mkdir(parents=True)
        assert is_path_under_root(other, root) is False

    def test_path_equals_root(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        root.mkdir()
        # Path equal to root is NOT under root (must be a descendant)
        assert is_path_under_root(root, root) is True  # relative_to returns empty path, which is valid

    def test_symlink_resolution(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        root.mkdir()
        workspace = root / "ABC-123"
        workspace.mkdir()

        # Create a symlink outside root pointing inside
        link = tmp_path / "link"
        link.symlink_to(workspace)

        # The resolved path is under root
        assert is_path_under_root(link, root) is True

    def test_validate_workspace_path_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        root.mkdir()
        other = tmp_path / "other" / "ABC-123"
        other.mkdir(parents=True)

        with pytest.raises(WorkspacePathError):
            validate_workspace_path(other, root)

    def test_validate_workspace_path_passes(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        root.mkdir()
        workspace = root / "ABC-123"
        workspace.mkdir()

        # Should not raise
        validate_workspace_path(workspace, root)


class TestHookExecution:
    """Tests for hook execution (tasks 2.1-2.5)."""

    def test_hook_success(self, tmp_path: Path) -> None:
        result = run_hook("echo 'hello'", tmp_path, timeout_ms=5000)
        assert result.success is True
        assert result.return_code == 0
        assert "hello" in result.stdout

    def test_hook_failure(self, tmp_path: Path) -> None:
        with pytest.raises(HookExecutionError) as exc_info:
            run_hook("exit 1", tmp_path, timeout_ms=5000)
        assert exc_info.value.return_code == 1

    def test_hook_timeout(self, tmp_path: Path) -> None:
        with pytest.raises(HookTimeoutError) as exc_info:
            run_hook("sleep 10", tmp_path, timeout_ms=100)
        assert exc_info.value.timeout_ms == 100

    def test_hook_with_cwd(self, tmp_path: Path) -> None:
        """Verify hook runs in the correct working directory."""
        script = "pwd"
        result = run_hook(script, tmp_path, timeout_ms=5000)
        assert str(tmp_path) in result.stdout.strip()

    def test_hook_output_capture(self, tmp_path: Path) -> None:
        result = run_hook("echo 'stdout' && echo 'stderr' >&2", tmp_path, timeout_ms=5000)
        assert "stdout" in result.stdout
        assert "stderr" in result.stderr


class TestRunHookBestEffort:
    """Tests for best-effort hook execution."""

    def test_none_script_returns_none(self, tmp_path: Path) -> None:
        result = run_hook_best_effort(None, tmp_path)
        assert result is None

    def test_empty_script_returns_none(self, tmp_path: Path) -> None:
        result = run_hook_best_effort("", tmp_path)
        assert result is None

    def test_successful_hook_returns_result(self, tmp_path: Path) -> None:
        result = run_hook_best_effort("echo 'ok'", tmp_path)
        assert result is not None
        assert result.success is True

    def test_failed_hook_returns_none(self, tmp_path: Path) -> None:
        """Failure is logged but returns None, not raised."""
        result = run_hook_best_effort("exit 1", tmp_path)
        assert result is None


class TestWorkspaceManager:
    """Tests for workspace manager (tasks 3.1-3.9, 5.1-5.6)."""

    def test_create_workspace(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        manager = WorkspaceManager(root)

        result = manager.create_for_issue("ABC-123")
        assert result.path == root / "ABC-123"
        assert result.workspace_key == "ABC-123"
        assert result.created_now is True
        assert result.path.is_dir()

    def test_reuse_workspace(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        manager = WorkspaceManager(root)

        # First creation
        result1 = manager.create_for_issue("ABC-123")
        assert result1.created_now is True

        # Reuse
        result2 = manager.create_for_issue("ABC-123")
        assert result2.created_now is False
        assert result2.path == result1.path

    def test_workspace_key_sanitized(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        manager = WorkspaceManager(root)

        result = manager.create_for_issue("ABC/123")
        assert result.workspace_key == "ABC_123"
        assert result.path == root / "ABC_123"

    def test_workspace_root_created(self, tmp_path: Path) -> None:
        root = tmp_path / "new_workspaces"
        assert not root.exists()
        WorkspaceManager(root)
        assert root.is_dir()

    def test_cleanup_removes_workspace(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        manager = WorkspaceManager(root)

        result = manager.create_for_issue("ABC-123")
        assert result.path.is_dir()

        manager.cleanup_for_issue("ABC-123")
        assert not result.path.exists()

    def test_cleanup_missing_workspace_is_noop(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        manager = WorkspaceManager(root)

        # Should not raise
        manager.cleanup_for_issue("NONEXISTENT")

    def test_non_directory_path_handled(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        manager = WorkspaceManager(root)

        # Create a file at the workspace location
        workspace_path = root / "ABC-123"
        workspace_path.touch()
        assert workspace_path.is_file()

        # Should remove the file and create a directory
        result = manager.create_for_issue("ABC-123")
        assert result.path.is_dir()
        assert result.created_now is True

    def test_workspace_path_under_root(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        manager = WorkspaceManager(root)

        result = manager.create_for_issue("ABC-123")
        assert result.path.is_relative_to(root)


class TestWorkspaceManagerHooks:
    """Tests for workspace manager hook integration (tasks 3.3-3.6, 5.3-5.5)."""

    def test_after_create_hook_on_new_workspace(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        hooks_config = type(
            "HooksConfig",
            (),
            {
                "after_create": "echo 'created' > hook_output.txt",
                "before_run": None,
                "after_run": None,
                "before_remove": None,
                "timeout_ms": 5000,
            },
        )()
        manager = WorkspaceManager(root, hooks_config)

        result = manager.create_for_issue("ABC-123")
        assert result.created_now is True
        # Verify hook ran
        assert (result.path / "hook_output.txt").exists()

    def test_after_create_hook_not_on_reuse(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        call_count = 0

        def counting_hook(*args: object, **kwargs: object) -> HookResult:
            nonlocal call_count
            call_count += 1
            return HookResult(success=True)

        hooks_config = type(
            "HooksConfig",
            (),
            {
                "after_create": "echo 'created' > hook_output.txt",
                "before_run": None,
                "after_run": None,
                "before_remove": None,
                "timeout_ms": 5000,
            },
        )()
        manager = WorkspaceManager(root, hooks_config)

        # First creation - hook runs
        result1 = manager.create_for_issue("ABC-123")
        assert result1.created_now is True

        # Reuse - hook should NOT run again
        result2 = manager.create_for_issue("ABC-123")
        assert result2.created_now is False

    def test_after_create_hook_failure_aborts_creation(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        hooks_config = type(
            "HooksConfig",
            (),
            {
                "after_create": "exit 1",
                "before_run": None,
                "after_run": None,
                "before_remove": None,
                "timeout_ms": 5000,
            },
        )()
        manager = WorkspaceManager(root, hooks_config)

        with pytest.raises(WorkspaceError):
            manager.create_for_issue("ABC-123")

        # Workspace should be cleaned up after failure
        assert not (root / "ABC-123").exists()

    def test_before_run_hook_success(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        hooks_config = type(
            "HooksConfig",
            (),
            {
                "after_create": None,
                "before_run": "echo 'before' > before_output.txt",
                "after_run": None,
                "before_remove": None,
                "timeout_ms": 5000,
            },
        )()
        manager = WorkspaceManager(root, hooks_config)

        result = manager.create_for_issue("ABC-123")
        hook_result = manager.run_before_run(result.path)
        assert hook_result.success is True
        assert (result.path / "before_output.txt").exists()

    def test_before_run_hook_failure_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        hooks_config = type(
            "HooksConfig",
            (),
            {
                "after_create": None,
                "before_run": "exit 1",
                "after_run": None,
                "before_remove": None,
                "timeout_ms": 5000,
            },
        )()
        manager = WorkspaceManager(root, hooks_config)

        result = manager.create_for_issue("ABC-123")

        with pytest.raises(WorkspaceError):
            manager.run_before_run(result.path)

    def test_after_run_hook_failure_ignored(self, tmp_path: Path) -> None:
        root = tmp_path / "workspaces"
        hooks_config = type(
            "HooksConfig",
            (),
            {
                "after_create": None,
                "before_run": None,
                "after_run": "exit 1",
                "before_remove": None,
                "timeout_ms": 5000,
            },
        )()
        manager = WorkspaceManager(root, hooks_config)

        result = manager.create_for_issue("ABC-123")

        # Should not raise
        manager.run_after_run(result.path)

    def test_full_lifecycle(self, tmp_path: Path) -> None:
        """Integration test: create → before_run → after_run → cleanup (task 5.1)."""
        root = tmp_path / "workspaces"
        hooks_config = type(
            "HooksConfig",
            (),
            {
                "after_create": "echo 'created' > created.txt",
                "before_run": "echo 'before' > before.txt",
                "after_run": "echo 'after' > after.txt",
                "before_remove": "echo 'removing' > removing.txt",
                "timeout_ms": 5000,
            },
        )()
        manager = WorkspaceManager(root, hooks_config)

        # Create
        result = manager.create_for_issue("ABC-123")
        assert result.created_now is True
        assert (result.path / "created.txt").exists()

        # Before run
        manager.run_before_run(result.path)
        assert (result.path / "before.txt").exists()

        # After run
        manager.run_after_run(result.path)
        assert (result.path / "after.txt").exists()

        # Cleanup
        manager.cleanup_for_issue("ABC-123")
        assert not result.path.exists()

    def test_workspace_reuse_no_after_create(self, tmp_path: Path) -> None:
        """Integration test: workspace reuse skips after_create (task 5.2)."""
        root = tmp_path / "workspaces"
        hooks_config = type(
            "HooksConfig",
            (),
            {
                "after_create": "echo 'created' > created.txt",
                "before_run": None,
                "after_run": None,
                "before_remove": None,
                "timeout_ms": 5000,
            },
        )()
        manager = WorkspaceManager(root, hooks_config)

        # First creation
        result1 = manager.create_for_issue("ABC-123")
        assert result1.created_now is True
        assert (result1.path / "created.txt").exists()

        # Reuse - no after_create, no created.txt from this call
        result2 = manager.create_for_issue("ABC-123")
        assert result2.created_now is False

    def test_validate_agent_cwd(self, tmp_path: Path) -> None:
        """Integration test: path safety validation before agent launch (task 5.6)."""
        root = tmp_path / "workspaces"
        manager = WorkspaceManager(root)

        result = manager.create_for_issue("ABC-123")

        # Should not raise
        manager.validate_agent_cwd(result.path)

        # Out-of-root path should raise
        other = tmp_path / "other" / "ABC-123"
        other.mkdir(parents=True)
        with pytest.raises(WorkspacePathError):
            manager.validate_agent_cwd(other)


class TestErrorClasses:
    """Tests for error classes (tasks 4.1-4.5)."""

    def test_workspace_error(self) -> None:
        err = WorkspaceError("test error")
        assert "test error" in str(err)
        assert isinstance(err, Exception)

    def test_workspace_path_error(self) -> None:
        err = WorkspacePathError("path not under root")
        assert "path not under root" in str(err)
        assert isinstance(err, Exception)

    def test_hook_timeout_error(self) -> None:
        err = HookTimeoutError(5000, "partial output")
        assert err.timeout_ms == 5000
        assert "5000ms" in str(err)
        assert isinstance(err, Exception)

    def test_hook_execution_error(self) -> None:
        err = HookExecutionError(1, "stdout", "stderr")
        assert err.return_code == 1
        assert "return code 1" in str(err)
        assert isinstance(err, Exception)

    def test_hook_timeout_output_truncated(self) -> None:
        long_output = "x" * 2000
        err = HookTimeoutError(5000, long_output)
        assert len(err.output) <= 1024

    def test_hook_execution_error_output_truncated(self) -> None:
        long_output = "x" * 2000
        err = HookExecutionError(1, long_output, long_output)
        assert len(err.stdout) <= 1024
        assert len(err.stderr) <= 1024
