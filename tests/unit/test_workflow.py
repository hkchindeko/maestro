"""Tests for WORKFLOW.md loader (tasks 3.1-3.6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maestro.core.workflow import (
    MissingWorkflowFileError,
    WorkflowFrontMatterNotMapError,
    WorkflowParseError,
    load_workflow,
    resolve_config,
)


class TestLoadWorkflow:
    """Tests for WORKFLOW.md loading."""

    def test_loads_valid_workflow(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text(
            "---\ntracker:\n  kind: linear\n  project_slug: test-project\n---\n\nYou are working on {{ issue.identifier }}."
        )
        definition = load_workflow(workflow)
        assert definition.config == {"tracker": {"kind": "linear", "project_slug": "test-project"}}
        assert "You are working on {{ issue.identifier }}." in definition.prompt_template
        assert definition.workflow_path == workflow.resolve()

    def test_loads_workflow_without_front_matter(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("Just a prompt with no front matter.")
        definition = load_workflow(workflow)
        assert definition.config == {}
        assert definition.prompt_template == "Just a prompt with no front matter."

    def test_loads_workflow_with_empty_front_matter(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n---\n\nPrompt body only.")
        definition = load_workflow(workflow)
        assert definition.config == {}
        assert definition.prompt_template == "Prompt body only."

    def test_missing_file_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(MissingWorkflowFileError):
            load_workflow(tmp_path / "NONEXISTENT.md")

    def test_invalid_yaml_raises_error(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n- invalid: [unclosed\n---\nbody")
        with pytest.raises(WorkflowParseError):
            load_workflow(workflow)

    def test_non_map_front_matter_raises_error(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n- item1\n- item2\n---\nbody")
        with pytest.raises(WorkflowFrontMatterNotMapError):
            load_workflow(workflow)

    def test_default_path_is_cwd_workflow(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n---\nbody")
        definition = load_workflow()  # No path argument
        assert definition.workflow_path == workflow.resolve()

    def test_prompt_body_is_trimmed(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n---\n\n  trimmed prompt  \n\n")
        definition = load_workflow(workflow)
        assert definition.prompt_template == "trimmed prompt"


class TestResolveConfig:
    """Tests for config resolution from workflow definition."""

    def test_resolves_config_from_definition(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text(
            "---\ntracker:\n  kind: linear\n  project_slug: test\nworkspace:\n  root: ~/workspaces\n---\nbody"
        )
        definition = load_workflow(workflow)
        config = resolve_config(definition)
        assert config.tracker.kind == "linear"
        assert config.tracker.project_slug == "test"
        assert config.workspace.root is not None
        assert "workspaces" in config.workspace.root

    def test_applies_defaults(self, tmp_path: Path) -> None:
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n---\nbody")
        definition = load_workflow(workflow)
        config = resolve_config(definition)
        assert config.polling.interval_ms == 30000
        assert config.agent.max_concurrent_agents == 10
        assert config.sandbox.kind == "local"
