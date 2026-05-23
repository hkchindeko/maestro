"""Prompt builder using Jinja2 with strict undefined mode.

Implements SPEC §5.4 (Prompt Template Contract) and §12 (Prompt Construction).
"""

from __future__ import annotations

import logging
from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateError, TemplateSyntaxError

from maestro.prompt.models import IssueContext

logger = logging.getLogger(__name__)

FALLBACK_PROMPT = "You are working on an issue."


class TemplateParseError(Exception):
    """Raised when the template has invalid Jinja2 syntax.

    Per SPEC §5.5, this is a configuration/validation error that
    blocks new dispatches until fixed.
    """

    pass


class TemplateRenderError(Exception):
    """Raised when rendering fails due to unknown variable/filter.

    Per SPEC §5.5, this fails only the affected run attempt.
    """

    pass


class PromptBuilder:
    """Renders WORKFLOW.md prompt bodies with issue-specific context.

    Uses Jinja2 with StrictUndefined to enforce SPEC §5.4's requirement
    that unknown variables and unknown filters MUST fail rendering.
    """

    def __init__(self) -> None:
        """Initialize the Jinja2 environment with strict undefined mode."""
        self._env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
        )

    def parse(self, template: str) -> Any:
        """Parse and compile a template string.

        Args:
            template: The Jinja2 template string (WORKFLOW.md prompt body).

        Returns:
            Compiled Jinja2 template object.

        Raises:
            TemplateParseError: If the template has invalid Jinja2 syntax.
        """
        try:
            return self._env.from_string(template)
        except TemplateSyntaxError as e:
            raise TemplateParseError(f"Invalid template syntax: {e}") from e

    def render(
        self,
        template: str,
        issue: IssueContext,
        attempt: int | None = None,
    ) -> str:
        """Render a template with issue context.

        Args:
            template: The Jinja2 template string (WORKFLOW.md prompt body).
            issue: Normalized issue context with all fields from SPEC §4.1.1.
            attempt: Retry/continuation attempt number. None for first run.

        Returns:
            Rendered prompt string.

        Raises:
            TemplateParseError: If the template has invalid Jinja2 syntax.
            TemplateRenderError: If rendering fails due to unknown variable/filter.
        """
        if not template or not template.strip():
            return FALLBACK_PROMPT

        compiled = self.parse(template)

        context = issue.to_dict()
        context["attempt"] = attempt

        try:
            return compiled.render(**context)
        except TemplateError as e:
            raise TemplateRenderError(f"Template render error: {e}") from e
