"""Pydantic configuration models for Maestro workflow config.

Implements SPEC §5.3 (Front Matter Schema) and §6.1 (Configuration Resolution Pipeline).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# Pattern for $VAR_NAME references
_ENV_VAR_PATTERN = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")


def resolve_env_var(value: str) -> str | None:
    """Resolve a $VAR_NAME reference to its environment variable value.

    Returns None if the value is not a $VAR reference, or if the resolved
    value is an empty string (per SPEC §5.3.1).
    """
    match = _ENV_VAR_PATTERN.match(value)
    if not match:
        return None
    env_value = os.environ.get(match.group(1), "")
    if not env_value:
        return None
    return env_value


def expand_path(value: str, workflow_dir: Path | None = None) -> str:
    """Expand a path value: ~ home expansion, $VAR resolution, relative path resolution.

    Per SPEC §5.3.3 and §6.1:
    - ~ is expanded
    - $VAR is resolved for env-backed path values
    - Relative paths resolve relative to workflow_dir (directory containing WORKFLOW.md)
    """
    # Expand ~
    expanded = os.path.expanduser(value)

    # Resolve $VAR if present
    resolved = resolve_env_var(expanded)
    if resolved is not None:
        expanded = resolved

    # Resolve relative paths against workflow directory
    path = Path(expanded)
    if not path.is_absolute() and workflow_dir is not None:
        path = workflow_dir / path

    return str(path.resolve())


class TrackerConfig(BaseModel):
    """Tracker configuration per SPEC §5.3.1."""

    kind: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    project_slug: str | None = None
    active_states: list[str] = Field(default_factory=lambda: ["Todo", "In Progress"])
    terminal_states: list[str] = Field(
        default_factory=lambda: ["Closed", "Cancelled", "Canceled", "Duplicate", "Done"]
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_api_key(cls, v: str | None) -> str | None:
        """Resolve $VAR_NAME for api_key. Empty resolved value treated as missing."""
        if v is None:
            return None
        if isinstance(v, str):
            return resolve_env_var(v) or v
        return v

    @model_validator(mode="after")
    def apply_defaults(self) -> TrackerConfig:
        """Apply endpoint default for linear tracker kind."""
        if self.kind == "linear" and self.endpoint is None:
            self.endpoint = "https://api.linear.app/graphql"
        return self


class PollingConfig(BaseModel):
    """Polling configuration per SPEC §5.3.2."""

    interval_ms: int = 30000


class WorkspaceConfig(BaseModel):
    """Workspace configuration per SPEC §5.3.3."""

    root: str | None = None

    @field_validator("root", mode="before")
    @classmethod
    def normalize_root(cls, v: str | None) -> str | None:
        """Expand ~ and resolve $VAR for workspace root."""
        if v is None:
            return None
        if isinstance(v, str):
            expanded = os.path.expanduser(v)
            resolved = resolve_env_var(expanded)
            if resolved is not None:
                expanded = resolved
            return expanded
        return v


class HooksConfig(BaseModel):
    """Hooks configuration per SPEC §5.3.4."""

    after_create: str | None = None
    before_run: str | None = None
    after_run: str | None = None
    before_remove: str | None = None
    timeout_ms: int = 60000


class SandboxConfig(BaseModel):
    """Sandbox configuration per SPEC §5.3.5."""

    kind: str = "local"
    image: str | None = None
    resources: dict[str, str] | None = None
    env: dict[str, str] | None = None


class AgentConfig(BaseModel):
    """Agent configuration per SPEC §5.3.6."""

    kind: str = "codex"
    command: str | None = None
    approval_policy: str | None = None
    max_concurrent_agents: int = 10
    max_turns: int = 20
    max_retry_backoff_ms: int = 300000
    max_concurrent_agents_by_state: dict[str, int] = Field(default_factory=dict)

    @field_validator("max_concurrent_agents_by_state")
    @classmethod
    def normalize_state_keys(cls, v: dict[str, int]) -> dict[str, int]:
        """Normalize state keys to lowercase, ignore invalid entries."""
        result: dict[str, int] = {}
        for key, value in v.items():
            if isinstance(value, int) and value > 0:
                result[key.lower()] = value
        return result


class CodexConfig(BaseModel):
    """Codex configuration (deprecated, use AgentConfig) per SPEC §5.3.7."""

    command: str | None = None
    approval_policy: str | None = None
    thread_sandbox: str | None = None
    turn_sandbox_policy: dict[str, Any] | None = None
    turn_timeout_ms: int = 3600000
    read_timeout_ms: int = 5000
    stall_timeout_ms: int = 300000


class WorkflowConfig(BaseModel):
    """Root workflow configuration combining all sub-configs.

    Unknown top-level keys are ignored for forward compatibility (SPEC §5.3).
    """

    tracker: TrackerConfig = Field(default_factory=TrackerConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    codex: CodexConfig = Field(default_factory=CodexConfig)

    @model_validator(mode="before")
    @classmethod
    def ignore_unknown_keys(cls, data: Any) -> Any:
        """Pass through all data — Pydantic's extra='ignore' handles unknown keys."""
        return data

    class Config:
        extra = "ignore"
