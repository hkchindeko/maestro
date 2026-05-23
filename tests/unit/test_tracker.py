"""Tests for tracker protocol and Linear adapter.

Covers tasks 1.5, 2.7, 3.6, 4.6, and 5.1-5.4.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from maestro.tracker.base import BlockerRef, Issue, IssueSnapshot, Tracker
from maestro.tracker.linear import (
    LinearApiRequestError,
    LinearApiStatusError,
    LinearGraphQLError,
    LinearMissingEndCursorError,
    LinearTracker,
    LinearUnknownPayloadError,
    _normalize_issue,
    _normalize_priority,
    _parse_timestamp,
)


class TestIssueModel:
    """Tests for Issue dataclass (task 1.1)."""

    def test_minimal_issue(self) -> None:
        issue = Issue(id="abc123", identifier="ABC-123", title="Test")
        assert issue.id == "abc123"
        assert issue.identifier == "ABC-123"
        assert issue.title == "Test"
        assert issue.description is None
        assert issue.priority is None
        assert issue.state == ""
        assert issue.labels == []
        assert issue.blocked_by == []

    def test_full_issue(self) -> None:
        now = datetime(2026, 5, 23, 10, 0, 0)
        issue = Issue(
            id="abc123",
            identifier="ABC-123",
            title="Fix the bug",
            description="Something is broken",
            priority=2,
            state="In Progress",
            branch_name="feature/fix",
            url="https://linear.app/test/issue/ABC-123",
            labels=["bug", "urgent"],
            blocked_by=[BlockerRef(id="blk1", identifier="ABC-100", state="Todo")],
            created_at=now,
            updated_at=now,
        )
        assert issue.description == "Something is broken"
        assert issue.priority == 2
        assert len(issue.labels) == 2
        assert len(issue.blocked_by) == 1


class TestIssueSnapshot:
    """Tests for IssueSnapshot dataclass (task 1.2)."""

    def test_snapshot(self) -> None:
        snap = IssueSnapshot(id="abc123", identifier="ABC-123", state="In Progress")
        assert snap.id == "abc123"
        assert snap.identifier == "ABC-123"
        assert snap.state == "In Progress"


class TestTrackerABC:
    """Tests for Tracker ABC (task 1.4)."""

    def test_tracker_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            Tracker()  # type: ignore[abstract]

    def test_tracker_requires_three_methods(self) -> None:
        """Verify the ABC requires all three methods."""
        assert hasattr(Tracker, "fetch_candidate_issues")
        assert hasattr(Tracker, "fetch_issues_by_states")
        assert hasattr(Tracker, "fetch_issue_states_by_ids")


class TestNormalizePriority:
    """Tests for priority normalization (task 3.4)."""

    def test_integer_priority(self) -> None:
        assert _normalize_priority(2) == 2

    def test_none_priority(self) -> None:
        assert _normalize_priority(None) is None

    def test_float_priority_whole_number(self) -> None:
        assert _normalize_priority(2.0) == 2

    def test_float_priority_fractional(self) -> None:
        assert _normalize_priority(2.5) is None

    def test_boolean_priority(self) -> None:
        assert _normalize_priority(True) is None
        assert _normalize_priority(False) is None

    def test_string_priority(self) -> None:
        assert _normalize_priority("high") is None


class TestParseTimestamp:
    """Tests for timestamp parsing (task 3.5)."""

    def test_iso8601_with_timezone(self) -> None:
        result = _parse_timestamp("2026-05-23T10:00:00+00:00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 5

    def test_iso8601_with_z(self) -> None:
        result = _parse_timestamp("2026-05-23T10:00:00Z")
        assert result is not None
        assert result.year == 2026

    def test_none_timestamp(self) -> None:
        assert _parse_timestamp(None) is None

    def test_empty_timestamp(self) -> None:
        assert _parse_timestamp("") is None

    def test_invalid_timestamp(self) -> None:
        assert _parse_timestamp("not-a-date") is None


class TestNormalizeIssue:
    """Tests for issue normalization (tasks 3.1-3.3, 3.6)."""

    def test_basic_normalization(self) -> None:
        raw = {
            "id": "abc123",
            "identifier": "ABC-123",
            "title": "Fix the bug",
            "description": "Something broken",
            "priority": 2,
            "state": {"name": "In Progress"},
            "branchName": "feature/fix",
            "url": "https://linear.app/test/issue/ABC-123",
            "labels": [{"name": "Bug"}, {"name": "Urgent"}],
            "inverseRelations": [],
            "createdAt": "2026-05-23T10:00:00Z",
            "updatedAt": "2026-05-23T11:00:00Z",
        }
        issue = _normalize_issue(raw)
        assert issue.id == "abc123"
        assert issue.identifier == "ABC-123"
        assert issue.title == "Fix the bug"
        assert issue.description == "Something broken"
        assert issue.priority == 2
        assert issue.state == "In Progress"
        assert issue.branch_name == "feature/fix"
        assert issue.url == "https://linear.app/test/issue/ABC-123"

    def test_labels_normalized_to_lowercase(self) -> None:
        raw = {
            "id": "abc123",
            "identifier": "ABC-123",
            "title": "Test",
            "labels": [{"name": "Bug"}, {"name": "URGENT"}],
            "inverseRelations": [],
        }
        issue = _normalize_issue(raw)
        assert issue.labels == ["bug", "urgent"]

    def test_blocked_by_from_inverse_relations(self) -> None:
        raw = {
            "id": "abc123",
            "identifier": "ABC-123",
            "title": "Test",
            "labels": [],
            "inverseRelations": [
                {
                    "relatedIssue": {
                        "id": "blk1",
                        "identifier": "ABC-100",
                        "state": {"name": "Todo"},
                    }
                },
                {
                    "relatedIssue": {
                        "id": "blk2",
                        "identifier": "ABC-101",
                        "state": {"name": "In Progress"},
                    }
                },
            ],
        }
        issue = _normalize_issue(raw)
        assert len(issue.blocked_by) == 2
        assert issue.blocked_by[0].id == "blk1"
        assert issue.blocked_by[0].identifier == "ABC-100"
        assert issue.blocked_by[0].state == "Todo"
        assert issue.blocked_by[1].identifier == "ABC-101"

    def test_priority_non_integer_becomes_null(self) -> None:
        raw = {
            "id": "abc123",
            "identifier": "ABC-123",
            "title": "Test",
            "priority": 2.5,
            "labels": [],
            "inverseRelations": [],
        }
        issue = _normalize_issue(raw)
        assert issue.priority is None

    def test_timestamps_parsed(self) -> None:
        raw = {
            "id": "abc123",
            "identifier": "ABC-123",
            "title": "Test",
            "labels": [],
            "inverseRelations": [],
            "createdAt": "2026-05-23T10:00:00Z",
            "updatedAt": "2026-05-23T11:00:00Z",
        }
        issue = _normalize_issue(raw)
        assert issue.created_at is not None
        assert issue.created_at.year == 2026
        assert issue.updated_at is not None


class TestLinearErrorClasses:
    """Tests for error classes (tasks 4.1-4.6)."""

    def test_linear_api_request_error(self) -> None:
        err = LinearApiRequestError("connection refused")
        assert "connection refused" in str(err)
        assert isinstance(err, Exception)

    def test_linear_api_status_error(self) -> None:
        err = LinearApiStatusError(500, "Internal Server Error")
        assert err.status_code == 500
        assert "500" in str(err)
        assert isinstance(err, Exception)

    def test_linear_graphql_error(self) -> None:
        errors = [{"message": "Field not found", "locations": [{"line": 1}]}]
        err = LinearGraphQLError(errors)
        assert "Field not found" in str(err)
        assert err.errors == errors
        assert isinstance(err, Exception)

    def test_linear_unknown_payload_error(self) -> None:
        err = LinearUnknownPayloadError("Expected dict, got list")
        assert "Expected dict" in str(err)
        assert isinstance(err, Exception)

    def test_linear_missing_end_cursor_error(self) -> None:
        err = LinearMissingEndCursorError("hasNextPage true but endCursor missing")
        assert "endCursor" in str(err)
        assert isinstance(err, Exception)


class TestLinearTracker:
    """Tests for Linear tracker (tasks 2.1-2.7, 5.1-5.4)."""

    def _make_config(self, **kwargs: object) -> MagicMock:
        config = MagicMock()
        config.endpoint = kwargs.get("endpoint", "https://api.linear.app/graphql")
        config.api_key = kwargs.get("api_key", "test-token")
        config.project_slug = kwargs.get("project_slug", "test-project")
        config.active_states = kwargs.get("active_states", ["Todo", "In Progress"])
        return config

    @pytest.mark.asyncio
    async def test_fetch_candidate_issues_single_page(self) -> None:
        """Test candidate fetch with single page response."""
        config = self._make_config()
        tracker = LinearTracker(config)

        mock_response = {
            "issues": {
                "nodes": [
                    {
                        "id": "abc123",
                        "identifier": "ABC-123",
                        "title": "Fix bug",
                        "description": None,
                        "priority": 2,
                        "state": {"name": "Todo"},
                        "branchName": None,
                        "url": "https://linear.app/test/issue/ABC-123",
                        "labels": [{"name": "Bug"}],
                        "inverseRelations": [],
                        "createdAt": "2026-05-23T10:00:00Z",
                        "updatedAt": "2026-05-23T10:00:00Z",
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }

        with patch.object(tracker, "_execute_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            issues = await tracker.fetch_candidate_issues()

        assert len(issues) == 1
        assert issues[0].identifier == "ABC-123"
        assert issues[0].labels == ["bug"]

        # Verify query was called with project slug filter
        call_args = mock_query.call_args
        assert call_args[0][1]["projectSlug"] == "test-project"
        assert call_args[0][1]["states"] == ["Todo", "In Progress"]

    @pytest.mark.asyncio
    async def test_fetch_candidate_issues_pagination(self) -> None:
        """Test candidate fetch with multiple pages."""
        config = self._make_config()
        tracker = LinearTracker(config)

        page1 = {
            "issues": {
                "nodes": [
                    {
                        "id": "abc123",
                        "identifier": "ABC-123",
                        "title": "Issue 1",
                        "description": None,
                        "priority": 1,
                        "state": {"name": "Todo"},
                        "branchName": None,
                        "url": None,
                        "labels": [],
                        "inverseRelations": [],
                        "createdAt": "2026-05-23T10:00:00Z",
                        "updatedAt": "2026-05-23T10:00:00Z",
                    }
                ],
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
            }
        }
        page2 = {
            "issues": {
                "nodes": [
                    {
                        "id": "abc456",
                        "identifier": "ABC-456",
                        "title": "Issue 2",
                        "description": None,
                        "priority": 2,
                        "state": {"name": "In Progress"},
                        "branchName": None,
                        "url": None,
                        "labels": [],
                        "inverseRelations": [],
                        "createdAt": "2026-05-23T10:00:00Z",
                        "updatedAt": "2026-05-23T10:00:00Z",
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }

        with patch.object(tracker, "_execute_query", new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = [page1, page2]
            issues = await tracker.fetch_candidate_issues()

        assert len(issues) == 2
        assert mock_query.call_count == 2

        # Second call should include after cursor
        second_call = mock_query.call_args_list[1]
        assert second_call[0][1].get("after") == "cursor1"

    @pytest.mark.asyncio
    async def test_fetch_issues_by_states_empty_returns_empty(self) -> None:
        """Test empty fetch_issues_by_states returns empty without API call (task 5.4)."""
        config = self._make_config()
        tracker = LinearTracker(config)

        with patch.object(tracker, "_execute_query", new_callable=AsyncMock) as mock_query:
            result = await tracker.fetch_issues_by_states([])

        assert result == []
        mock_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_issues_by_states(self) -> None:
        """Test terminal state fetch (task 5.3)."""
        config = self._make_config()
        tracker = LinearTracker(config)

        mock_response = {
            "issues": {
                "nodes": [
                    {
                        "id": "abc123",
                        "identifier": "ABC-123",
                        "title": "Done issue",
                        "description": None,
                        "priority": None,
                        "state": {"name": "Done"},
                        "branchName": None,
                        "url": None,
                        "labels": [],
                        "inverseRelations": [],
                        "createdAt": "2026-05-23T10:00:00Z",
                        "updatedAt": "2026-05-23T10:00:00Z",
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }

        with patch.object(tracker, "_execute_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            issues = await tracker.fetch_issues_by_states(["Done", "Closed"])

        assert len(issues) == 1
        assert issues[0].state == "Done"

    @pytest.mark.asyncio
    async def test_fetch_issue_states_by_ids(self) -> None:
        """Test state refresh (task 5.2)."""
        config = self._make_config()
        tracker = LinearTracker(config)

        mock_response = {
            "issues": {
                "nodes": [
                    {"id": "abc123", "identifier": "ABC-123", "state": {"name": "In Progress"}},
                    {"id": "abc456", "identifier": "ABC-456", "state": {"name": "Done"}},
                ]
            }
        }

        with patch.object(tracker, "_execute_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            snapshots = await tracker.fetch_issue_states_by_ids(["abc123", "abc456"])

        assert len(snapshots) == 2
        assert snapshots[0].id == "abc123"
        assert snapshots[0].state == "In Progress"
        assert snapshots[1].state == "Done"

        # Verify [ID!] variable type
        call_args = mock_query.call_args
        assert "ids" in call_args[0][1]
        assert call_args[0][1]["ids"] == ["abc123", "abc456"]

    @pytest.mark.asyncio
    async def test_fetch_issue_states_by_ids_empty(self) -> None:
        """Test empty issue IDs returns empty without API call."""
        config = self._make_config()
        tracker = LinearTracker(config)

        with patch.object(tracker, "_execute_query", new_callable=AsyncMock) as mock_query:
            result = await tracker.fetch_issue_states_by_ids([])

        assert result == []
        mock_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_end_cursor_raises_error(self) -> None:
        """Test pagination integrity error."""
        config = self._make_config()
        tracker = LinearTracker(config)

        mock_response = {
            "issues": {
                "nodes": [],
                "pageInfo": {"hasNextPage": True, "endCursor": None},
            }
        }

        with patch.object(tracker, "_execute_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            with pytest.raises(LinearMissingEndCursorError):
                await tracker.fetch_candidate_issues()

    @pytest.mark.asyncio
    async def test_graphql_errors_raises(self) -> None:
        """Test GraphQL error handling."""
        config = self._make_config()
        tracker = LinearTracker(config)

        with patch.object(tracker, "_execute_query", new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = LinearGraphQLError(
                [{"message": "Unknown field"}]
            )
            with pytest.raises(LinearGraphQLError):
                await tracker.fetch_candidate_issues()

    @pytest.mark.asyncio
    async def test_full_pipeline_candidate_fetch_normalize(self) -> None:
        """Integration test: full candidate fetch → normalize pipeline (task 5.1)."""
        config = self._make_config()
        tracker = LinearTracker(config)

        mock_response = {
            "issues": {
                "nodes": [
                    {
                        "id": "abc123",
                        "identifier": "ABC-123",
                        "title": "Fix the bug",
                        "description": "Something is broken",
                        "priority": 1,
                        "state": {"name": "Todo"},
                        "branchName": "feature/fix",
                        "url": "https://linear.app/test/issue/ABC-123",
                        "labels": [{"name": "Bug"}, {"name": "Urgent"}],
                        "inverseRelations": [
                            {
                                "relatedIssue": {
                                    "id": "blk1",
                                    "identifier": "ABC-100",
                                    "state": {"name": "In Progress"},
                                }
                            }
                        ],
                        "createdAt": "2026-05-23T10:00:00Z",
                        "updatedAt": "2026-05-23T11:00:00Z",
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }

        with patch.object(tracker, "_execute_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            issues = await tracker.fetch_candidate_issues()

        assert len(issues) == 1
        issue = issues[0]
        assert issue.id == "abc123"
        assert issue.identifier == "ABC-123"
        assert issue.title == "Fix the bug"
        assert issue.priority == 1
        assert issue.state == "Todo"
        assert issue.labels == ["bug", "urgent"]
        assert len(issue.blocked_by) == 1
        assert issue.blocked_by[0].identifier == "ABC-100"
        assert issue.created_at is not None
