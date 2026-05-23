"""Linear GraphQL tracker adapter.

Implements SPEC §11.1 (REQUIRED operations), §11.2 (Linear query semantics),
§11.3 (Normalization rules), and §11.4 (Error handling contract).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from maestro.core.config import TrackerConfig
from maestro.tracker.base import BlockerRef, Issue, IssueSnapshot, Tracker

logger = logging.getLogger(__name__)

# GraphQL queries
CANDIDATE_ISSUES_QUERY = """
query CandidateIssues($projectSlug: String!, $states: [String!], $after: String) {
  issues(
    filter: {
      project: { slugId: { eq: $projectSlug } }
      state: { name: { in: $states } }
    }
    first: 50
    after: $after
  ) {
    nodes {
      id
      identifier
      title
      description
      priority
      state { name }
      branchName
      url
      labels { name }
      inverseRelations(filter: { type: { name: { eq: "blocks" } } }) {
        relatedIssue { id identifier state { name } }
      }
      createdAt
      updatedAt
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

ISSUES_BY_STATES_QUERY = """
query IssuesByStates($states: [String!], $after: String) {
  issues(
    filter: { state: { name: { in: $states } } }
    first: 50
    after: $after
  ) {
    nodes {
      id
      identifier
      title
      description
      priority
      state { name }
      branchName
      url
      labels { name }
      inverseRelations(filter: { type: { name: { eq: "blocks" } } }) {
        relatedIssue { id identifier state { name } }
      }
      createdAt
      updatedAt
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

ISSUE_STATES_BY_IDS_QUERY = """
query IssueStatesByIds($ids: [ID!]) {
  issues(filter: { id: { in: $ids } }) {
    nodes {
      id
      identifier
      state { name }
    }
  }
}
"""

# Error classes per SPEC §11.4


class LinearApiRequestError(Exception):
    """Transport failures (network errors, timeouts)."""

    pass


class LinearApiStatusError(Exception):
    """Non-200 HTTP status codes."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Linear API returned status {status_code}: {body[:200]}")


class LinearGraphQLError(Exception):
    """GraphQL errors in response body."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        messages = [e.get("message", "unknown") for e in errors]
        super().__init__(f"GraphQL errors: {'; '.join(messages)}")


class LinearUnknownPayloadError(Exception):
    """Malformed or unexpected response payloads."""

    pass


class LinearMissingEndCursorError(Exception):
    """Pagination integrity error (missing endCursor when hasNextPage is true)."""

    pass


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp string, returning None on failure."""
    if not value:
        return None
    try:
        # Handle both with and without timezone
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _normalize_priority(value: Any) -> int | None:
    """Convert priority to integer only; non-integers become null."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if value == int(value):
            return int(value)
        return None
    return None


def _normalize_issue(raw: dict[str, Any]) -> Issue:
    """Normalize a raw Linear issue response to the stable Issue model.

    Per SPEC §11.3:
    - labels → lowercase strings
    - blocked_by → derived from inverse relations of type "blocks"
    - priority → integer only (non-integers become null)
    - created_at/updated_at → parse ISO-8601 timestamps
    """
    # Normalize labels to lowercase
    labels = []
    for label in raw.get("labels", []):
        name = label.get("name", "")
        if name:
            labels.append(name.lower())

    # Extract blocked_by from inverse relations of type "blocks"
    blocked_by: list[BlockerRef] = []
    for rel in raw.get("inverseRelations", []):
        related = rel.get("relatedIssue")
        if related:
            blocked_by.append(
                BlockerRef(
                    id=related.get("id"),
                    identifier=related.get("identifier"),
                    state=related.get("state", {}).get("name") if related.get("state") else None,
                )
            )

    state_name = ""
    if raw.get("state"):
        state_name = raw["state"].get("name", "")

    return Issue(
        id=raw["id"],
        identifier=raw["identifier"],
        title=raw["title"],
        description=raw.get("description"),
        priority=_normalize_priority(raw.get("priority")),
        state=state_name,
        branch_name=raw.get("branchName"),
        url=raw.get("url"),
        labels=labels,
        blocked_by=blocked_by,
        created_at=_parse_timestamp(raw.get("createdAt")),
        updated_at=_parse_timestamp(raw.get("updatedAt")),
    )


class LinearTracker(Tracker):
    """Linear GraphQL tracker adapter.

    Implements all three required operations from SPEC §11.1:
    - fetch_candidate_issues()
    - fetch_issues_by_states()
    - fetch_issue_states_by_ids()
    """

    def __init__(self, config: TrackerConfig) -> None:
        """Initialize the Linear tracker.

        Args:
            config: TrackerConfig with kind="linear", endpoint, api_key, project_slug.
        """
        self._endpoint = config.endpoint or "https://api.linear.app/graphql"
        self._api_key = config.api_key
        self._project_slug = config.project_slug
        self._active_states = config.active_states
        self._timeout = 30.0  # 30s per SPEC §11.2

    async def _execute_query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query against the Linear API.

        Args:
            query: GraphQL query string.
            variables: Query variables.

        Returns:
            Parsed JSON response data.

        Raises:
            LinearApiRequestError: On transport failures.
            LinearApiStatusError: On non-200 HTTP status.
            LinearGraphQLError: On GraphQL errors in response.
            LinearUnknownPayloadError: On malformed response.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._endpoint, headers=headers, json=body)
        except httpx.RequestError as e:
            raise LinearApiRequestError(f"Linear API request failed: {e}") from e

        if response.status_code != 200:
            raise LinearApiStatusError(response.status_code, response.text)

        try:
            data = response.json()
        except ValueError as e:
            raise LinearUnknownPayloadError(f"Invalid JSON response: {e}") from e

        if not isinstance(data, dict):
            raise LinearUnknownPayloadError(f"Expected JSON object, got {type(data).__name__}")

        # Check for GraphQL errors
        if "errors" in data:
            raise LinearGraphQLError(data["errors"])

        if "data" not in data:
            raise LinearUnknownPayloadError("Response missing 'data' key")

        return data["data"]

    async def fetch_candidate_issues(self) -> list[Issue]:
        """Fetch issues in configured active states for the configured project.

        Uses cursor-based pagination with page size 50 per SPEC §11.2.

        Returns:
            List of normalized issues eligible for dispatch.
        """
        all_issues: list[Issue] = []
        after: str | None = None

        while True:
            variables: dict[str, Any] = {
                "projectSlug": self._project_slug,
                "states": self._active_states,
            }
            if after is not None:
                variables["after"] = after

            data = await self._execute_query(CANDIDATE_ISSUES_QUERY, variables)

            issues_data = data.get("issues")
            if not issues_data or not isinstance(issues_data, dict):
                raise LinearUnknownPayloadError("Unexpected issues response structure")

            nodes = issues_data.get("nodes", [])
            for node in nodes:
                all_issues.append(_normalize_issue(node))

            page_info = issues_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            end_cursor = page_info.get("endCursor")
            if end_cursor is None:
                raise LinearMissingEndCursorError(
                    "hasNextPage is true but endCursor is missing"
                )
            after = end_cursor

        return all_issues

    async def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        """Fetch issues matching the given state names.

        Used for startup terminal cleanup.

        Args:
            state_names: List of state names to filter by.

        Returns:
            List of normalized issues in the specified states.
        """
        if not state_names:
            return []

        all_issues: list[Issue] = []
        after: str | None = None

        while True:
            variables: dict[str, Any] = {"states": state_names}
            if after is not None:
                variables["after"] = after

            data = await self._execute_query(ISSUES_BY_STATES_QUERY, variables)

            issues_data = data.get("issues")
            if not issues_data or not isinstance(issues_data, dict):
                raise LinearUnknownPayloadError("Unexpected issues response structure")

            nodes = issues_data.get("nodes", [])
            for node in nodes:
                all_issues.append(_normalize_issue(node))

            page_info = issues_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            end_cursor = page_info.get("endCursor")
            if end_cursor is None:
                raise LinearMissingEndCursorError(
                    "hasNextPage is true but endCursor is missing"
                )
            after = end_cursor

        return all_issues

    async def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[IssueSnapshot]:
        """Fetch current states for specific issue IDs.

        Used for active-run reconciliation. Uses [ID!] variable type per SPEC §11.2.

        Args:
            issue_ids: List of issue IDs to fetch states for.

        Returns:
            List of minimal issue snapshots with current state.
        """
        if not issue_ids:
            return []

        variables: dict[str, Any] = {"ids": issue_ids}
        data = await self._execute_query(ISSUE_STATES_BY_IDS_QUERY, variables)

        issues_data = data.get("issues")
        if not issues_data or not isinstance(issues_data, dict):
            raise LinearUnknownPayloadError("Unexpected issues response structure")

        nodes = issues_data.get("nodes", [])
        snapshots: list[IssueSnapshot] = []
        for node in nodes:
            state_name = ""
            if node.get("state"):
                state_name = node["state"].get("name", "")
            snapshots.append(
                IssueSnapshot(
                    id=node["id"],
                    identifier=node["identifier"],
                    state=state_name,
                )
            )

        return snapshots
