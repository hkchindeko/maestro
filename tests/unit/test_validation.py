"""Tests for dispatch preflight validation (tasks 4.1-4.3)."""

from __future__ import annotations

import pytest

from maestro.core.config import WorkflowConfig
from maestro.core.validation import validate_dispatch_config


class TestValidateDispatchConfig:
    """Tests for dispatch preflight validation."""

    def test_valid_config_passes(self) -> None:
        config = WorkflowConfig.model_validate(
            {
                "tracker": {"kind": "linear", "api_key": "test-key", "project_slug": "test"},
                "agent": {"command": "codex app-server"},
            }
        )
        result = validate_dispatch_config(config)
        assert result.ok
        assert result.errors == []

    def test_missing_tracker_kind_fails(self) -> None:
        config = WorkflowConfig.model_validate(
            {"tracker": {"api_key": "test-key"}, "agent": {"command": "codex"}}
        )
        result = validate_dispatch_config(config)
        assert not result.ok
        assert any("missing_tracker_kind" in e for e in result.errors)

    def test_unsupported_tracker_kind_fails(self) -> None:
        config = WorkflowConfig.model_validate(
            {
                "tracker": {"kind": "unsupported", "api_key": "test-key"},
                "agent": {"command": "codex"},
            }
        )
        result = validate_dispatch_config(config)
        assert not result.ok
        assert any("unsupported_tracker_kind" in e for e in result.errors)

    def test_missing_api_key_fails(self) -> None:
        config = WorkflowConfig.model_validate(
            {"tracker": {"kind": "linear"}, "agent": {"command": "codex"}}
        )
        result = validate_dispatch_config(config)
        assert not result.ok
        assert any("missing_tracker_api_key" in e for e in result.errors)

    def test_missing_project_slug_for_linear_fails(self) -> None:
        config = WorkflowConfig.model_validate(
            {
                "tracker": {"kind": "linear", "api_key": "test-key"},
                "agent": {"command": "codex"},
            }
        )
        result = validate_dispatch_config(config)
        assert not result.ok
        assert any("missing_tracker_project_slug" in e for e in result.errors)

    def test_missing_agent_command_fails(self) -> None:
        config = WorkflowConfig.model_validate(
            {"tracker": {"kind": "linear", "api_key": "test-key", "project_slug": "test"}}
        )
        result = validate_dispatch_config(config)
        assert not result.ok
        assert any("missing_agent_command" in e for e in result.errors)

    def test_multiple_errors_reported(self) -> None:
        config = WorkflowConfig()  # All defaults, nothing set
        result = validate_dispatch_config(config)
        assert not result.ok
        assert len(result.errors) >= 2  # At least kind and api_key missing
