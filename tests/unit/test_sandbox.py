"""Tests for sandbox manager protocol and LocalSandbox implementation.

Covers tasks 1.1-1.4, 2.1-2.5, and 5.2-5.6.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from maestro.sandbox.base import SandboxError, SandboxManager, SandboxResult
from maestro.sandbox.local import LocalSandbox


class TestSandboxResult:
    """Tests for SandboxResult dataclass (task 5.6)."""

    def test_creation_with_fields(self) -> None:
        result = SandboxResult(
            sandbox_id="/tmp/workspaces/ABC-123",
            effective_path=Path("/tmp/workspaces/ABC-123"),
        )
        assert result.sandbox_id == "/tmp/workspaces/ABC-123"
        assert result.effective_path == Path("/tmp/workspaces/ABC-123")

    def test_effective_path_is_absolute(self, tmp_path: Path) -> None:
        ws = tmp_path / "ABC-123"
        ws.mkdir()
        result = SandboxResult(sandbox_id=str(ws), effective_path=ws)
        assert result.effective_path.is_absolute()

    def test_sandbox_id_is_string(self, tmp_path: Path) -> None:
        ws = tmp_path / "ABC-123"
        ws.mkdir()
        result = SandboxResult(sandbox_id=str(ws), effective_path=ws)
        assert isinstance(result.sandbox_id, str)
        assert len(result.sandbox_id) > 0


class TestSandboxManagerProtocol:
    """Tests for SandboxManager ABC (task 5.2)."""

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            SandboxManager()  # type: ignore[abstract]

    def test_subclass_must_implement_provision(self) -> None:
        class Incomplete(SandboxManager):
            async def teardown(self, sandbox_id: str) -> None:
                pass

            def is_ready(self) -> bool:
                return True

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_subclass_must_implement_teardown(self) -> None:
        class Incomplete(SandboxManager):
            async def provision(self, workspace_path: Path) -> SandboxResult:
                return SandboxResult(sandbox_id="test", effective_path=workspace_path)

            def is_ready(self) -> bool:
                return True

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_subclass_must_implement_is_ready(self) -> None:
        class Incomplete(SandboxManager):
            async def provision(self, workspace_path: Path) -> SandboxResult:
                return SandboxResult(sandbox_id="test", effective_path=workspace_path)

            async def teardown(self, sandbox_id: str) -> None:
                pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_full_subclass_instantiates(self) -> None:
        class Complete(SandboxManager):
            async def provision(self, workspace_path: Path) -> SandboxResult:
                return SandboxResult(sandbox_id=str(workspace_path), effective_path=workspace_path)

            async def teardown(self, sandbox_id: str) -> None:
                pass

            def is_ready(self) -> bool:
                return True

        instance = Complete()
        assert instance is not None
        assert instance.is_ready() is True


class TestLocalSandbox:
    """Tests for LocalSandbox implementation (tasks 5.3-5.5)."""

    @pytest.fixture
    def sandbox(self) -> LocalSandbox:
        return LocalSandbox()

    @pytest.mark.asyncio
    async def test_provision_valid_workspace(self, sandbox: LocalSandbox, tmp_path: Path) -> None:
        ws = tmp_path / "test-issue"
        ws.mkdir()
        result = await sandbox.provision(ws)
        assert result.sandbox_id == str(ws)
        assert result.effective_path == ws

    @pytest.mark.asyncio
    async def test_provision_missing_workspace(self, sandbox: LocalSandbox, tmp_path: Path) -> None:
        ws = tmp_path / "nonexistent"
        with pytest.raises(SandboxError, match="does not exist"):
            await sandbox.provision(ws)

    @pytest.mark.asyncio
    async def test_provision_path_is_file_not_directory(
        self, sandbox: LocalSandbox, tmp_path: Path
    ) -> None:
        f = tmp_path / "a-file"
        f.write_text("not a dir")
        with pytest.raises(SandboxError, match="not a directory"):
            await sandbox.provision(f)

    @pytest.mark.asyncio
    async def test_provision_deterministic_sandbox_id(
        self, sandbox: LocalSandbox, tmp_path: Path
    ) -> None:
        ws = tmp_path / "ABC-123"
        ws.mkdir()
        result1 = await sandbox.provision(ws)
        result2 = await sandbox.provision(ws)
        assert result1.sandbox_id == result2.sandbox_id

    @pytest.mark.asyncio
    async def test_teardown_is_noop(self, sandbox: LocalSandbox, tmp_path: Path) -> None:
        # Teardown should not raise and should not touch the filesystem
        ws = tmp_path / "ABC-123"
        ws.mkdir()
        await sandbox.teardown(str(ws))
        assert ws.exists()  # workspace still exists

    @pytest.mark.asyncio
    async def test_teardown_with_nonexistent_sandbox_id(self, sandbox: LocalSandbox) -> None:
        # Teardown should be idempotent and never raise
        await sandbox.teardown("nonexistent-sandbox-id")

    @pytest.mark.asyncio
    async def test_teardown_with_empty_sandbox_id(self, sandbox: LocalSandbox) -> None:
        await sandbox.teardown("")

    def test_is_ready_always_true(self, sandbox: LocalSandbox) -> None:
        assert sandbox.is_ready() is True

    def test_is_ready_is_sync(self, sandbox: LocalSandbox) -> None:
        # Verify is_ready is not a coroutine
        result = sandbox.is_ready()
        assert not hasattr(result, "__await__")
        assert result is True


class TestSandboxError:
    """Tests for SandboxError exception class (task 5.2)."""

    def test_is_exception(self) -> None:
        assert issubclass(SandboxError, Exception)

    def test_can_be_raised(self) -> None:
        with pytest.raises(SandboxError, match="test message"):
            raise SandboxError("test message")

    def test_can_be_caught_as_exception(self) -> None:
        try:
            raise SandboxError("foo")
        except Exception as e:
            assert isinstance(e, SandboxError)
            assert str(e) == "foo"