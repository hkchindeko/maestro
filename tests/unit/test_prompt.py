"""Tests for prompt builder and models (tasks 1.4, 2.5, 3.1-3.5, 4.1-4.4, 5.3-5.4)."""

from __future__ import annotations

from datetime import datetime

import pytest

from maestro.prompt.builder import (
    FALLBACK_PROMPT,
    PromptBuilder,
    TemplateParseError,
    TemplateRenderError,
)
from maestro.prompt.models import BlockerRef, IssueContext


class TestBlockerRef:
    """Tests for BlockerRef dataclass (task 1.1)."""

    def test_default_values(self) -> None:
        ref = BlockerRef()
        assert ref.id is None
        assert ref.identifier is None
        assert ref.state is None

    def test_with_values(self) -> None:
        ref = BlockerRef(id="abc123", identifier="ABC-100", state="Todo")
        assert ref.id == "abc123"
        assert ref.identifier == "ABC-100"
        assert ref.state == "Todo"


class TestIssueContext:
    """Tests for IssueContext dataclass (tasks 1.2-1.4)."""

    def test_minimal_context(self) -> None:
        ctx = IssueContext(id="abc123", identifier="ABC-123", title="Test issue")
        assert ctx.id == "abc123"
        assert ctx.identifier == "ABC-123"
        assert ctx.title == "Test issue"
        assert ctx.description is None
        assert ctx.priority is None
        assert ctx.state == ""
        assert ctx.labels == []
        assert ctx.blocked_by == []

    def test_full_context(self) -> None:
        now = datetime(2026, 5, 23, 10, 0, 0)
        blockers = [
            BlockerRef(id="blk1", identifier="ABC-100", state="In Progress"),
            BlockerRef(id="blk2", identifier="ABC-101", state="Todo"),
        ]
        ctx = IssueContext(
            id="abc123",
            identifier="ABC-123",
            title="Test issue",
            description="A detailed description",
            priority=2,
            state="In Progress",
            branch_name="feature/abc-123",
            url="https://linear.app/test/issue/ABC-123",
            labels=["bug", "urgent"],
            blocked_by=blockers,
            created_at=now,
            updated_at=now,
        )
        assert ctx.description == "A detailed description"
        assert ctx.priority == 2
        assert ctx.state == "In Progress"
        assert len(ctx.labels) == 2
        assert len(ctx.blocked_by) == 2

    def test_to_dict_string_keys(self) -> None:
        ctx = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        d = ctx.to_dict()
        assert all(isinstance(k, str) for k in d.keys())
        assert d["id"] == "abc123"
        assert d["identifier"] == "ABC-123"
        assert d["title"] == "Test"

    def test_to_dict_preserves_labels(self) -> None:
        ctx = IssueContext(
            id="abc123",
            identifier="ABC-123",
            title="Test",
            labels=["bug", "urgent"],
        )
        d = ctx.to_dict()
        assert d["labels"] == ["bug", "urgent"]

    def test_to_dict_preserves_blocked_by(self) -> None:
        blockers = [
            BlockerRef(id="blk1", identifier="ABC-100", state="Todo"),
        ]
        ctx = IssueContext(
            id="abc123",
            identifier="ABC-123",
            title="Test",
            blocked_by=blockers,
        )
        d = ctx.to_dict()
        assert len(d["blocked_by"]) == 1
        assert d["blocked_by"][0]["id"] == "blk1"
        assert d["blocked_by"][0]["identifier"] == "ABC-100"
        assert d["blocked_by"][0]["state"] == "Todo"

    def test_to_dict_null_fields_preserved(self) -> None:
        ctx = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        d = ctx.to_dict()
        assert d["description"] is None
        assert d["priority"] is None
        assert d["branch_name"] is None
        assert d["url"] is None
        assert d["created_at"] is None
        assert d["updated_at"] is None


class TestPromptBuilderRender:
    """Tests for successful rendering (task 2.5)."""

    def test_render_basic_template(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Fix the bug")
        result = builder.render("Issue: {{ issue.identifier }} - {{ issue.title }}", issue)
        assert result == "Issue: ABC-123 - Fix the bug"

    def test_render_with_all_fields(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(
            id="abc123",
            identifier="ABC-123",
            title="Fix the bug",
            description="Something is broken",
            priority=1,
            state="In Progress",
            labels=["bug"],
        )
        template = (
            "Issue: {{ issue.identifier }}\n"
            "Title: {{ issue.title }}\n"
            "State: {{ issue.state }}\n"
            "Priority: {{ issue.priority }}\n"
            "Labels: {{ issue.labels }}"
        )
        result = builder.render(template, issue)
        assert "ABC-123" in result
        assert "Fix the bug" in result
        assert "In Progress" in result
        assert "1" in result
        assert "['bug']" in result


class TestFallbackPrompt:
    """Tests for fallback prompt (task 2.4)."""

    def test_empty_template_returns_fallback(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        result = builder.render("", issue)
        assert result == FALLBACK_PROMPT

    def test_whitespace_only_template_returns_fallback(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        result = builder.render("   \n\n  ", issue)
        assert result == FALLBACK_PROMPT

    def test_non_empty_template_rendered(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        result = builder.render("Working on {{ issue.identifier }}", issue)
        assert result != FALLBACK_PROMPT
        assert "ABC-123" in result


class TestStrictModeEnforcement:
    """Tests for strict mode (tasks 3.1-3.5)."""

    def test_unknown_variable_raises_error(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        with pytest.raises(TemplateRenderError):
            builder.render("Issue: {{ issue.unknown_field }}", issue)

    def test_unknown_filter_raises_error(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        with pytest.raises(TemplateRenderError):
            builder.render("{{ issue.identifier | unknown_filter }}", issue)

    def test_labels_iteration(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(
            id="abc123",
            identifier="ABC-123",
            title="Test",
            labels=["bug", "urgent", "frontend"],
        )
        template = "Labels: {% for label in issue.labels %}{{ label }}{% if not loop.last %}, {% endif %}{% endfor %}"
        result = builder.render(template, issue)
        assert result == "Labels: bug, urgent, frontend"

    def test_blocked_by_iteration(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(
            id="abc123",
            identifier="ABC-123",
            title="Test",
            blocked_by=[
                BlockerRef(id="blk1", identifier="ABC-100", state="Todo"),
                BlockerRef(id="blk2", identifier="ABC-101", state="In Progress"),
            ],
        )
        template = (
            "Blocked by: {% for b in issue.blocked_by %}{{ b.identifier }}{% if not loop.last %}, {% endif %}{% endfor %}"
        )
        result = builder.render(template, issue)
        assert result == "Blocked by: ABC-100, ABC-101"

    def test_null_fields_render_as_empty(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(
            id="abc123",
            identifier="ABC-123",
            title="Test",
            description=None,
        )
        # Jinja2 renders None as empty string
        result = builder.render("Desc: '{{ issue.description }}'", issue)
        assert result == "Desc: ''"


class TestRetryContinuationSemantics:
    """Tests for retry/continuation semantics (tasks 4.1-4.4)."""

    def test_first_run_attempt_none(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        template = "{% if attempt %}Retry #{{ attempt }}{% else %}First run{% endif %}"
        result = builder.render(template, issue, attempt=None)
        assert result == "First run"

    def test_continuation_attempt_one(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        template = "{% if attempt %}Retry #{{ attempt }}{% else %}First run{% endif %}"
        result = builder.render(template, issue, attempt=1)
        assert result == "Retry #1"

    def test_retry_attempt_three(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        template = "{% if attempt %}Retry #{{ attempt }}{% else %}First run{% endif %}"
        result = builder.render(template, issue, attempt=3)
        assert result == "Retry #3"

    def test_conditional_template_both_branches(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        template = (
            "{% if attempt %}"
            "This is retry attempt #{{ attempt }}. Resume from current state."
            "{% else %}"
            "This is the first run. Start from scratch."
            "{% endif %}"
        )
        first = builder.render(template, issue, attempt=None)
        assert "first run" in first.lower()
        assert "scratch" in first.lower()

        retry = builder.render(template, issue, attempt=2)
        assert "retry attempt #2" in retry.lower()
        assert "resume" in retry.lower()


class TestErrorHandling:
    """Tests for error classes (tasks 5.1-5.4)."""

    def test_template_parse_error_class_exists(self) -> None:
        assert TemplateParseError is not None
        assert issubclass(TemplateParseError, Exception)

    def test_template_render_error_class_exists(self) -> None:
        assert TemplateRenderError is not None
        assert issubclass(TemplateRenderError, Exception)

    def test_invalid_syntax_raises_parse_error(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        with pytest.raises(TemplateParseError):
            builder.render("{{ issue.identifier ", issue)  # Missing closing }}

    def test_render_error_has_clear_message(self) -> None:
        builder = PromptBuilder()
        issue = IssueContext(id="abc123", identifier="ABC-123", title="Test")
        with pytest.raises(TemplateRenderError) as exc_info:
            builder.render("{{ issue.nonexistent }}", issue)
        assert "nonexistent" in str(exc_info.value).lower() or "undefined" in str(exc_info.value).lower()
