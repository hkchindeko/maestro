## ADDED Requirements

### Requirement: Prompt template rendering with strict mode
> Source: SPEC §5.4, §12.2

The prompt builder SHALL render the `WORKFLOW.md` prompt body using a strict template engine (Liquid-compatible semantics).

Template input variables:
- `issue` (object) — includes all normalized issue fields from SPEC §4.1.1, including `labels` and `blocked_by`
- `attempt` (integer or null) — `null`/absent on first attempt, integer on retry or continuation run

Unknown variables MUST fail rendering with a `template_render_error`.
Unknown filters MUST fail rendering with a `template_render_error`.

Issue object keys SHALL be converted to strings for template compatibility.
Nested arrays/maps (`labels`, `blocked_by`) SHALL be preserved so templates can iterate over them.

**Tests:**
- Prompt template renders `issue` and `attempt`
- Prompt rendering fails on unknown variables (strict mode)
- Prompt rendering fails on unknown filters (strict mode)
- `issue.labels` can be iterated in template
- `issue.blocked_by` can be iterated in template
- Null fields render as empty string

### Requirement: Fallback prompt for empty workflow body
> Source: SPEC §5.4

If the workflow prompt body is empty, the runtime MAY use a minimal default prompt:
`You are working on an issue.`

**Tests:**
- Empty prompt body produces fallback prompt
- Non-empty prompt body is rendered as-is (no fallback)

### Requirement: Retry/continuation prompt semantics
> Source: SPEC §12.3

The `attempt` value SHALL be passed to the template because the workflow prompt can provide different instructions for:
- First run (`attempt` null or absent)
- Continuation run after a successful prior session
- Retry after error/timeout/stall

**Tests:**
- Rendering with `attempt=None` produces first-run output
- Rendering with `attempt=1` produces continuation output
- Rendering with `attempt=3` produces retry output

### Requirement: Template error classes
> Source: SPEC §5.5

The prompt builder SHALL distinguish between error classes:
- `template_parse_error` — invalid Jinja2 syntax during template compilation
- `template_render_error` — unknown variable/filter, invalid interpolation during rendering

Dispatch gating behavior:
- Template parse errors are configuration/validation errors and SHALL NOT silently fall back to a prompt
- Template render errors fail only the affected run attempt

**Tests:**
- Invalid Jinja2 syntax raises `TemplateParseError`
- Unknown variable raises `TemplateRenderError`
- Unknown filter raises `TemplateRenderError`

### Requirement: Issue context model
> Source: SPEC §4.1.1

The issue context SHALL include all normalized issue fields:
- `id` (string) — stable tracker-internal ID
- `identifier` (string) — human-readable ticket key (e.g., `ABC-123`)
- `title` (string)
- `description` (string or null)
- `priority` (integer or null) — lower numbers are higher priority
- `state` (string) — current tracker state name
- `branch_name` (string or null) — tracker-provided branch metadata
- `url` (string or null)
- `labels` (list of strings) — normalized to lowercase
- `blocked_by` (list of blocker refs) — each ref contains `id`, `identifier`, `state`
- `created_at` (timestamp or null)
- `updated_at` (timestamp or null)

**Tests:**
- Issue context can be created from all fields
- Issue context converts to string-keyed dict for template use
- `blocked_by` refs are preserved as nested dicts for template iteration
