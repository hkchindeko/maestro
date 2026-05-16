"""Tests for Pydantic config models (tasks 1.1-1.9)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from maestro.core.config import (
    AgentConfig,
    HooksConfig,
    PollingConfig,
    SandboxConfig,
    TrackerConfig,
    WorkflowConfig,
    WorkspaceConfig,
    expand_path,
    resolve_env_var,
)


class TestResolveEnvVar:
    """Tests for $VAR_NAME resolution (task 2.1)."""

    def test_resolves_existing_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_KEY", "secret-value")
        assert resolve_env_var("$TEST_KEY") == "secret-value"

    def test_returns_none_for_missing_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NONEXISTENT_VAR_12345", raising=False)
        assert resolve_env_var("$NONEXISTENT_VAR_12345") is None

    def test_returns_none_for_empty_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMPTY_VAR", "")
        assert resolve_env_var("$EMPTY_VAR") is None

    def test_returns_none_for_non_var_string(self) -> None:
        assert resolve_env_var("plain-value") is None
        assert resolve_env_var("$invalid") is None  # starts with $ but invalid pattern

    def test_returns_none_for_partial_var_reference(self) -> None:
        assert resolve_env_var("prefix-$VAR") is None


class TestExpandPath:
    """Tests for path normalization (tasks 2.2-2.3, 2.5)."""

    def test_expands_home_tilde(self) -> None:
        result = expand_path("~/workspaces")
        assert result.startswith(os.path.expanduser("~"))
        assert "workspaces" in result

    def test_resolves_env_var_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WORKSPACE_DIR", "/tmp/test-ws")
        result = expand_path("$WORKSPACE_DIR")
        assert result == "/tmp/test-ws"

    def test_resolves_relative_path(self, tmp_path: Path) -> None:
        result = expand_path("relative/path", tmp_path)
        assert result == str((tmp_path / "relative" / "path").resolve())

    def test_preserves_absolute_path(self) -> None:
        result = expand_path("/absolute/path")
        assert result == "/absolute/path"


class TestTrackerConfig:
    """Tests for TrackerConfig (task 1.1)."""

    def test_defaults(self) -> None:
        config = TrackerConfig()
        assert config.kind is None
        assert config.endpoint is None
        assert config.api_key is None
        assert config.project_slug is None
        assert config.active_states == ["Todo", "In Progress"]
        assert config.terminal_states == ["Closed", "Cancelled", "Canceled", "Duplicate", "Done"]

    def test_linear_endpoint_default(self) -> None:
        config = TrackerConfig(kind="linear")
        assert config.endpoint == "https://api.linear.app/graphql"

    def test_non_linear_no_endpoint_default(self) -> None:
        config = TrackerConfig(kind="github")
        assert config.endpoint is None

    def test_resolves_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LINEAR_API_KEY", "test-token-123")
        config = TrackerConfig(kind="linear", api_key="$LINEAR_API_KEY")
        assert config.api_key == "test-token-123"

    def test_empty_api_key_treated_as_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMPTY_KEY", "")
        config = TrackerConfig(api_key="$EMPTY_KEY")
        assert config.api_key == "$EMPTY_KEY"  # unresolved, treated as missing

    def test_literal_api_key(self) -> None:
        config = TrackerConfig(api_key="literal-token")
        assert config.api_key == "literal-token"


class TestPollingConfig:
    """Tests for PollingConfig (task 1.2)."""

    def test_default_interval(self) -> None:
        config = PollingConfig()
        assert config.interval_ms == 30000

    def test_custom_interval(self) -> None:
        config = PollingConfig(interval_ms=5000)
        assert config.interval_ms == 5000


class TestWorkspaceConfig:
    """Tests for WorkspaceConfig (task 1.3)."""

    def test_default_root_is_none(self) -> None:
        config = WorkspaceConfig()
        assert config.root is None

    def test_expands_tilde(self) -> None:
        config = WorkspaceConfig(root="~/workspaces")
        assert config.root.startswith(os.path.expanduser("~"))


class TestHooksConfig:
    """Tests for HooksConfig (task 1.4)."""

    def test_defaults(self) -> None:
        config = HooksConfig()
        assert config.after_create is None
        assert config.before_run is None
        assert config.after_run is None
        assert config.before_remove is None
        assert config.timeout_ms == 60000


class TestSandboxConfig:
    """Tests for SandboxConfig (task 1.5)."""

    def test_defaults(self) -> None:
        config = SandboxConfig()
        assert config.kind == "local"
        assert config.image is None
        assert config.resources is None
        assert config.env is None


class TestAgentConfig:
    """Tests for AgentConfig (task 1.6)."""

    def test_defaults(self) -> None:
        config = AgentConfig()
        assert config.kind == "codex"
        assert config.command is None
        assert config.approval_policy is None
        assert config.max_concurrent_agents == 10
        assert config.max_turns == 20
        assert config.max_retry_backoff_ms == 300000
        assert config.max_concurrent_agents_by_state == {}

    def test_normalizes_state_keys_to_lowercase(self) -> None:
        config = AgentConfig(max_concurrent_agents_by_state={"In Progress": 5})
        assert "in progress" in config.max_concurrent_agents_by_state

    def test_ignores_invalid_entries(self) -> None:
        config = AgentConfig(max_concurrent_agents_by_state={"Done": -1, "Todo": 0, "Active": 3})
        assert config.max_concurrent_agents_by_state == {"active": 3}


class TestWorkflowConfig:
    """Tests for WorkflowConfig root model (tasks 1.7-1.9)."""

    def test_defaults(self) -> None:
        config = WorkflowConfig()
        assert isinstance(config.tracker, TrackerConfig)
        assert isinstance(config.polling, PollingConfig)
        assert isinstance(config.workspace, WorkspaceConfig)
        assert isinstance(config.hooks, HooksConfig)
        assert isinstance(config.sandbox, SandboxConfig)
        assert isinstance(config.agent, AgentConfig)

    def test_ignores_unknown_keys(self) -> None:
        config = WorkflowConfig.model_validate({"unknown_key": "value", "server": {"port": 8080}})
        # Should not raise, unknown keys ignored
        assert config is not None

    def test_from_dict_with_nested_config(self) -> None:
        data = {
            "tracker": {"kind": "linear", "project_slug": "test-project"},
            "polling": {"interval_ms": 5000},
            "agent": {"max_concurrent_agents": 5},
        }
        config = WorkflowConfig.model_validate(data)
        assert config.tracker.kind == "linear"
        assert config.tracker.project_slug == "test-project"
        assert config.polling.interval_ms == 5000
        assert config.agent.max_concurrent_agents == 5
