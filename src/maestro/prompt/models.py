"""Prompt construction models.

Defines the issue context dataclasses for template rendering per SPEC §4.1.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BlockerRef:
    """A reference to an issue that blocks the current issue.

    Attributes:
        id: Stable tracker-internal ID of the blocking issue.
        identifier: Human-readable ticket key (e.g., ABC-123).
        state: Current tracker state name of the blocking issue.
    """

    id: str | None = None
    identifier: str | None = None
    state: str | None = None


@dataclass
class IssueContext:
    """Normalized issue context for prompt template rendering.

    Maps all fields from SPEC §4.1.1 to template-accessible attributes.
    """

    id: str
    identifier: str
    title: str
    description: str | None = None
    priority: int | None = None
    state: str = ""
    branch_name: str | None = None
    url: str | None = None
    labels: list[str] = field(default_factory=list)
    blocked_by: list[BlockerRef] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to a string-keyed dict for Jinja2 template compatibility.

        Preserves nested arrays/maps (labels, blocked_by) so templates
        can iterate over them. Null values are preserved as-is.
        """
        return {
            "id": self.id,
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "state": self.state,
            "branch_name": self.branch_name,
            "url": self.url,
            "labels": self.labels,
            "blocked_by": [
                {"id": b.id, "identifier": b.identifier, "state": b.state}
                for b in self.blocked_by
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
