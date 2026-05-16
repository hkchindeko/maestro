"""Integration tests for CLI commands (task 6.3)."""

from __future__ import annotations

from pathlib import Path

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
