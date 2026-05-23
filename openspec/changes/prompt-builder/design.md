## Context

The prompt builder renders the `WORKFLOW.md` prompt body with issue-specific context. SPEC §5.4 requires strict template semantics: unknown variables and unknown filters MUST fail rendering. SPEC §12 defines the inputs (`issue` object, `attempt` integer) and failure semantics.

Key SPEC sections:
- §4.1.1: Issue entity fields (id, identifier, title, description, priority, state, branch_name, url, labels, blocked_by, created_at, updated_at)
- §5.4: Prompt template contract (strict mode, template inputs, fallback behavior)
- §12.1: Inputs to prompt rendering
- §12.2: Rendering rules (strict variable/filter checking, string keys, preserve nested arrays/maps)
- §12.3: Retry/continuation semantics (attempt null on first run, integer on retry)
- §12.4: Failure semantics (fail run attempt immediately on render error)

## Decisions

### Decision 1: Jinja2 with StrictUndefined

**Why:** SPEC §5.4 requires that unknown variables and unknown filters MUST fail rendering. Jinja2's `StrictUndefined` class raises `UndefinedError` on any access to an undefined variable, which maps directly to this requirement. Jinja2 also supports `undefined` filter behavior and is Liquid-compatible for the template features used in this spec.

**Alternatives considered:**
- `liquidpy` — closer to Liquid spec but less maintained, smaller ecosystem
- `string.Template` — no filter support, too limited for iteration over labels/blockers
- Custom template engine — unnecessary complexity, Jinja2 is well-tested

### Decision 2: IssueContext as dataclass, not dict

**Why:** SPEC §12.2 requires converting issue object keys to strings for template compatibility and preserving nested arrays/maps (labels, blockers). A dataclass with `__dict__` conversion provides type safety, IDE support, and clear field definitions matching SPEC §4.1.1. The dict conversion at render time ensures string keys for Jinja2 compatibility.

**Alternatives considered:**
- Plain dict — no type safety, easy to miss fields
- Pydantic model — overkill for a read-only context object, dataclass is sufficient
- TypedDict — good for type hints but doesn't help with runtime conversion

### Decision 3: Separate parse and render phases

**Why:** SPEC §5.5 distinguishes `template_parse_error` (during prompt rendering setup) from `template_render_error` (unknown variable/filter, invalid interpolation). Separating parse (compile template) from render (inject context) allows different error handling: parse errors are configuration errors that block dispatch, render errors fail only the affected run attempt.

**Alternatives considered:**
- Single render call — can't distinguish parse vs render errors cleanly
- Cache parsed templates — adds complexity, not needed for v1 (templates are small)

### Decision 4: Fallback prompt as constant, not config

**Why:** SPEC §5.4 states: "If the workflow prompt body is empty, the runtime MAY use a minimal default prompt (`You are working on an issue.`)." This is a simple constant, not a configurable value. Making it configurable would add unnecessary complexity for a fallback that should rarely be used.

**Alternatives considered:**
- Configurable fallback prompt — overkill, spec says "MAY use a minimal default"
- No fallback, fail on empty — conflicts with spec's "MAY use" language

### Decision 5: Blocker refs as nested dicts in template context

**Why:** SPEC §4.1.1 defines `blocked_by` as a list of blocker refs, each containing `id`, `identifier`, and `state`. Templates need to iterate over these (e.g., `{% for blocker in issue.blocked_by %}`). Representing them as a list of dicts preserves the nested structure for template iteration.

## Non-Decisions

- **Template caching** — not needed for v1; templates are small and re-parsed per run
- **Custom Jinja2 filters** — spec doesn't require any; strict mode means unknown filters fail
- **Async rendering** — template rendering is CPU-bound and fast; sync is sufficient

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Jinja2 StrictUndefined too strict for optional fields | Medium | All issue fields are present in context; null values are rendered as empty string |
| Template syntax errors in WORKFLOW.md | Low | Parse errors are caught and reported as configuration errors |
| Large issue descriptions slow rendering | Low | Jinja2 rendering is fast; descriptions are typically < 10KB |
