## Problem

SPEC §5.4 and §12 define the prompt template contract for rendering per-issue prompts from `WORKFLOW.md`:

1. **Strict template rendering** — unknown variables and unknown filters MUST fail rendering (§5.4)
2. **Template inputs** — `issue` object (all normalized fields) and `attempt` integer (§12.1)
3. **Retry/continuation semantics** — `attempt` passed to template for first-run vs retry instructions (§12.3)
4. **Failure semantics** — prompt rendering failures fail the run attempt immediately (§12.4)

The `workflow-config` change provides the `WORKFLOW.md` loader and config models, but does not implement prompt rendering. This is the next foundational layer needed before the orchestrator can dispatch work.

## What Changes

- Implement `PromptBuilder` using Jinja2 in strict undefined mode
- Define `IssueContext` dataclass mapping all normalized issue fields (§4.1.1) to template variables
- Implement `render_prompt(template, issue, attempt)` with strict variable and filter checking
- Implement fallback prompt behavior for empty workflow prompt body (§5.4)
- Add typed error classes: `TemplateParseError`, `TemplateRenderError`
- Write unit tests for rendering, strict mode failures, and retry semantics

## Capabilities

### New Capabilities

- `prompt-render`: Render `WORKFLOW.md` prompt body with `issue` and `attempt` context
- `prompt-strict-mode`: Fail rendering on unknown variables or filters
- `prompt-fallback`: Use minimal default prompt when workflow prompt body is empty

### Modified Capabilities

None — this is a new capability.

## Impact

- **New modules:**
  - `src/maestro/prompt/builder.py` — Jinja2 prompt renderer
  - `src/maestro/prompt/models.py` — `IssueContext` dataclass
- **Dependencies added:** `jinja2` (already in `pyproject.toml` from workflow-config)
- **Depends on:** `workflow-config` change (for `WorkflowDefinition.prompt_template`)
- **No breaking changes**
