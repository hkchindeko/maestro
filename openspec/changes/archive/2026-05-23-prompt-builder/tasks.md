## 1. Issue context model

- [x] 1.1 Create `BlockerRef` dataclass with `id`, `identifier`, `state` fields per SPEC §4.1.1
- [x] 1.2 Create `IssueContext` dataclass with all normalized issue fields: `id`, `identifier`, `title`, `description`, `priority`, `state`, `branch_name`, `url`, `labels`, `blocked_by`, `created_at`, `updated_at`
- [x] 1.3 Implement `to_dict()` method converting context to string-keyed dict for Jinja2
- [x] 1.4 Write unit tests for context creation and dict conversion

## 2. Prompt builder with Jinja2 strict mode

- [x] 2.1 Implement `PromptBuilder` class with Jinja2 `Environment` using `StrictUndefined`
- [x] 2.2 Implement `parse(template: str)` method returning compiled template, raising `TemplateParseError` on failure
- [x] 2.3 Implement `render(template, issue: IssueContext, attempt: int | None = None)` method, raising `TemplateRenderError` on unknown variable/filter
- [x] 2.4 Implement fallback prompt (`You are working on an issue.`) for empty template body
- [x] 2.5 Write unit tests for successful rendering with issue context

## 3. Strict mode enforcement

- [x] 3.1 Test that unknown variable raises `TemplateRenderError`
- [x] 3.2 Test that unknown filter raises `TemplateRenderError`
- [x] 3.3 Test that `issue.labels` iteration works in template
- [x] 3.4 Test that `issue.blocked_by` iteration works in template
- [x] 3.5 Test that null fields render as empty string

## 4. Retry/continuation semantics

- [x] 4.1 Test rendering with `attempt=None` (first run)
- [x] 4.2 Test rendering with `attempt=1` (continuation)
- [x] 4.3 Test rendering with `attempt=3` (retry after error)
- [x] 4.4 Write template that uses `{% if attempt %}` conditional and verify both branches

## 5. Error handling

- [x] 5.1 Define `TemplateParseError` exception class
- [x] 5.2 Define `TemplateRenderError` exception class
- [x] 5.3 Test parse error for invalid Jinja2 syntax
- [x] 5.4 Test render error propagation with clear message about missing variable/filter
