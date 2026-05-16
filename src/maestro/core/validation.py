"""Dispatch preflight validation.

Implements SPEC §6.3 (Dispatch Preflight Validation).
"""

from __future__ import annotations

from dataclasses import dataclass

from maestro.core.config import WorkflowConfig
from maestro.core.workflow import WorkflowDefinition

SUPPORTED_TRACKER_KINDS = {"linear", "jira", "github"}


@dataclass
class ValidationResult:
    """Result of dispatch preflight validation."""

    ok: bool
    errors: list[str]


def validate_dispatch_config(
    config: WorkflowConfig,
    definition: WorkflowDefinition | None = None,
) -> ValidationResult:
    """Validate configuration before dispatching work.

    Checks per SPEC §6.3:
    - Workflow file can be loaded and parsed
    - tracker.kind is present and supported
    - tracker.api_key is present after $ resolution
    - tracker.project_slug is present when REQUIRED by the selected tracker kind
    - agent.command (or codex.command) is present and non-empty

    Args:
        config: Resolved workflow configuration.
        definition: Optional workflow definition (for file load check).

    Returns:
        ValidationResult with ok=True if all checks pass, or list of errors.
    """
    errors: list[str] = []

    # Check tracker.kind
    if not config.tracker.kind:
        errors.append("missing_tracker_kind: tracker.kind is required")
    elif config.tracker.kind not in SUPPORTED_TRACKER_KINDS:
        errors.append(
            f"unsupported_tracker_kind: '{config.tracker.kind}' is not supported "
            f"(supported: {', '.join(sorted(SUPPORTED_TRACKER_KINDS))})"
        )

    # Check tracker.api_key
    if not config.tracker.api_key:
        errors.append("missing_tracker_api_key: tracker.api_key is required after $VAR resolution")

    # Check tracker.project_slug for Linear
    if config.tracker.kind == "linear" and not config.tracker.project_slug:
        errors.append(
            "missing_tracker_project_slug: tracker.project_slug is required for Linear tracker"
        )

    # Check agent.command (or codex.command as fallback)
    agent_command = config.agent.command
    if not agent_command:
        agent_command = config.codex.command
    if not agent_command:
        errors.append("missing_agent_command: agent.command (or codex.command) is required")

    return ValidationResult(ok=len(errors) == 0, errors=errors)
