"""Integration tests for CLI commands (task 6.3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from maestro.cli.main import app

runner = CliRunner()


class TestConfigValidateCommand:
    """Integration tests for `maestro config validate`."""

    def test_valid_workflow(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text(
            "---\ntracker:\n  kind: linear\n  api_key: test-key\n  project_slug: test\nagent:\n  command: codex app-server\n---\nbody"
        )
        result = runner.invoke(app, ["config", "validate", str(workflow)])
        assert result.exit_code == 0
        assert "Configuration is valid" in result.output

    def test_missing_workflow_file(self) -> None:
        result = runner.invoke(app, ["config", "validate", "/nonexistent/WORKFLOW.md"])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_invalid_config_missing_tracker_kind(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n---\nbody")
        result = runner.invoke(app, ["config", "validate", str(workflow)])
        assert result.exit_code == 1
        assert "missing_tracker_kind" in result.output

    def test_invalid_config_missing_api_key(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\ntracker:\n  kind: linear\n---\nbody")
        result = runner.invoke(app, ["config", "validate", str(workflow)])
        assert result.exit_code == 1
        assert "missing_tracker_api_key" in result.output


class TestConfigShowCommand:
    """Integration tests for `maestro config show`."""

    def test_shows_resolved_config(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text(
            "---\ntracker:\n  kind: linear\n  api_key: test-key\n  project_slug: test\nagent:\n  command: codex app-server\n---\nbody"
        )
        result = runner.invoke(app, ["config", "show", str(workflow)])
        assert result.exit_code == 0
        assert "Tracker Config" in result.output
        assert "linear" in result.output
        assert "Polling Config" in result.output
        assert "Agent Config" in result.output

    def test_shows_defaults_when_not_specified(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n---\nbody")
        result = runner.invoke(app, ["config", "show", str(workflow)])
        assert result.exit_code == 0
        assert "30000" in result.output  # default polling interval
        assert "codex" in result.output  # default agent kind


class TestRootRunCommand:
    """Integration tests for `maestro run`."""

    def test_dry_run_valid_config(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text(
            "---\ntracker:\n  kind: linear\n  api_key: test-key\n  project_slug: test\nagent:\n  command: codex app-server\n---\nbody"
        )
        result = runner.invoke(app, ["run", "--dry-run", str(workflow)])
        assert result.exit_code == 0
        assert "Configuration valid" in result.output
        assert "Dry run complete" in result.output

    def test_dry_run_invalid_config(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n---\nbody")
        result = runner.invoke(app, ["run", "--dry-run", str(workflow)])
        assert result.exit_code == 1
        assert "Configuration validation failed" in result.output

    def test_missing_workflow_file(self) -> None:
        result = runner.invoke(app, ["run", "--dry-run", "/nonexistent/WORKFLOW.md"])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_run_starts_runtime(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text(
            "---\ntracker:\n  kind: linear\n  api_key: test-key\n  project_slug: test\nagent:\n  command: codex app-server\n---\nbody"
        )

        with patch("maestro.cli.main.run_runtime", new_callable=AsyncMock) as run_runtime:
            result = runner.invoke(app, ["run", str(workflow)])

        assert result.exit_code == 0
        run_runtime.assert_awaited_once()

    def test_run_applies_cli_overrides_before_validation(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text(
            "---\ntracker:\n  kind: github\n  api_key: test-key\n  project_slug: test\nagent:\n  command: codex app-server\nserver:\n  port: 9999\n---\nbody"
        )

        with patch("maestro.cli.main.run_runtime", new_callable=AsyncMock) as run_runtime:
            result = runner.invoke(
                app,
                [
                    "run",
                    "--tracker-kind",
                    "linear",
                    "--agent-kind",
                    "codex",
                    "--sandbox-kind",
                    "local",
                    "--port",
                    "8080",
                    str(workflow),
                ],
            )

        assert result.exit_code == 0
        _, kwargs = run_runtime.await_args
        config = kwargs["config"]
        assert config.tracker.kind == "linear"
        assert config.agent.kind == "codex"
        assert config.sandbox.kind == "local"
        assert kwargs["port"] == 8080

    def test_run_reports_unsupported_runtime_kind(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text(
            "---\ntracker:\n  kind: linear\n  api_key: test-key\n  project_slug: test\nagent:\n  command: codex app-server\n---\nbody"
        )

        result = runner.invoke(app, ["run", "--sandbox-kind", "docker", str(workflow)])

        assert result.exit_code == 1
        assert "unsupported_sandbox_kind" in result.output
