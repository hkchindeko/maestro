"""Tracker protocol and domain models.

Defines the abstract `Tracker` interface and normalized issue models per SPEC §4.1.1 and §11.1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BlockerRef:
    """A reference to an issue that blocks the current issue.

    Attributes:
        id: Stable tracker-internal ID of the blocking issue.
        identifier: Human-readable ticket key (e.g., ABC-100).
        state: Current tracker state name of the blocking issue.
    """

    id: str | None = None
    identifier: str | None = None
    state: str | None = None


@dataclass
class Issue:
    """Normalized issue record used by orchestration, prompt rendering, and observability.

    Fields per SPEC §4.1.1.
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


@dataclass
class IssueSnapshot:
    """Minimal issue state for reconciliation and startup cleanup.

    Contains only the fields needed for state-based decisions.
    """

    id: str
    identifier: str
    state: str


class Tracker(ABC):
    """Abstract base class for issue tracker adapters.

    Per SPEC §11.1, all implementations MUST support these three operations.
    """

    @abstractmethod
    async def fetch_candidate_issues(self) -> list[Issue]:
        """Fetch issues in configured active states for a configured project.

        Returns:
            List of normalized issues eligible for dispatch.
        """
        ...

    @abstractmethod
    async def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        """Fetch issues matching the given state names.

        Used for startup terminal cleanup.

        Args:
            state_names: List of state names to filter by.

        Returns:
            List of normalized issues in the specified states.
        """
        ...

    @abstractmethod
    async def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[IssueSnapshot]:
        """Fetch current states for specific issue IDs.

        Used for active-run reconciliation.

        Args:
            issue_ids: List of issue IDs to fetch states for.

        Returns:
            List of minimal issue snapshots with current state.
        """
        ...
