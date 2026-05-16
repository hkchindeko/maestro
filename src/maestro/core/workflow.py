"""WORKFLOW.md loader and dynamic config reload.

Implements SPEC §5.1 (File Discovery), §5.2 (File Format), and §6.2 (Dynamic Reload).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from maestro.core.config import WorkflowConfig

logger = logging.getLogger(__name__)


@dataclass
class WorkflowDefinition:
    """Parsed WORKFLOW.md payload.

    Attributes:
        config: YAML front matter root object.
        prompt_template: Markdown body after front matter, trimmed.
        workflow_path: Absolute path to the loaded workflow file.
    """

    config: dict[str, Any]
    prompt_template: str
    workflow_path: Path


class WorkflowLoadError(Exception):
    """Base exception for workflow loading errors."""

    pass


class MissingWorkflowFileError(WorkflowLoadError):
    """Raised when the workflow file cannot be found."""

    pass


class WorkflowParseError(WorkflowLoadError):
    """Raised when the workflow file has invalid YAML front matter."""

    pass


class WorkflowFrontMatterNotMapError(WorkflowLoadError):
    """Raised when YAML front matter decodes to a non-map type."""

    pass


def _split_front_matter(content: str) -> tuple[str | None, str]:
    """Split a Markdown file into YAML front matter and body.

    Returns:
        Tuple of (front_matter_string or None, body_string).
    """
    if not content.startswith("---"):
        return None, content.strip()

    # Find the closing ---
    end_index = content.find("---", 3)
    if end_index == -1:
        # No closing ---, treat entire file as body
        return None, content.strip()

    front_matter = content[3:end_index].strip()
    body = content[end_index + 3 :].strip()
    return front_matter, body


def load_workflow(path: Path | str | None = None) -> WorkflowDefinition:
    """Load and parse a WORKFLOW.md file.

    Args:
        path: Explicit path to the workflow file. If None, defaults to
            ./WORKFLOW.md in the current working directory.

    Returns:
        WorkflowDefinition with parsed config and prompt template.

    Raises:
        MissingWorkflowFileError: If the file cannot be read.
        WorkflowParseError: If the YAML front matter is invalid.
        WorkflowFrontMatterNotMapError: If front matter is not a map/object.
    """
    workflow_path = Path(path) if path else Path.cwd() / "WORKFLOW.md"

    if not workflow_path.is_file():
        raise MissingWorkflowFileError(f"Workflow file not found: {workflow_path}")

    content = workflow_path.read_text(encoding="utf-8")
    front_matter_str, body = _split_front_matter(content)

    if front_matter_str is None:
        # No front matter — entire file is prompt body, empty config
        return WorkflowDefinition(
            config={},
            prompt_template=body,
            workflow_path=workflow_path.resolve(),
        )

    try:
        front_matter = yaml.safe_load(front_matter_str)
    except yaml.YAMLError as e:
        raise WorkflowParseError(f"Invalid YAML front matter: {e}") from e

    if not isinstance(front_matter, dict):
        raise WorkflowFrontMatterNotMapError(
            f"YAML front matter must be a map/object, got {type(front_matter).__name__}"
        )

    return WorkflowDefinition(
        config=front_matter,
        prompt_template=body,
        workflow_path=workflow_path.resolve(),
    )


def resolve_config(definition: WorkflowDefinition) -> WorkflowConfig:
    """Resolve a WorkflowDefinition into a typed WorkflowConfig.

    Applies defaults and resolves $VAR references per SPEC §6.1.

    Args:
        definition: Parsed workflow definition.

    Returns:
        Typed WorkflowConfig with defaults applied.
    """
    # Get the directory containing the workflow file for relative path resolution
    workflow_dir = definition.workflow_path.parent

    config_data = dict(definition.config)

    # Resolve workspace.root relative to workflow directory
    if "workspace" in config_data and isinstance(config_data["workspace"], dict):
        ws = config_data["workspace"]
        if "root" in ws and isinstance(ws["root"], str):
            from maestro.core.config import expand_path

            ws["root"] = expand_path(ws["root"], workflow_dir)

    return WorkflowConfig.model_validate(config_data)
