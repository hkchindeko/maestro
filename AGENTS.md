# Maestro — Agent Instructions

Maestro is a **Python implementation of the OpenAI Symphony specification** — a long-running automation service that orchestrates coding agents to execute issue tracker work autonomously.

> **Note:** The `elixir/` folder contains a reference implementation only. This project is implemented in Python.

## Quick Reference

```bash
uv sync                          # Install dependencies
uv run maestro --help            # Run CLI
uv run ruff check src/ tests/    # Lint
uv run ruff format src/ tests/   # Format
uv run mypy src/maestro          # Type check
uv run pytest tests/ -v          # Run tests
```

## Project Structure

| Path | Purpose |
|------|---------|
| `SPEC.md` | **Source of truth** — the Symphony specification |
| `PRD.md` | Product requirements document |
| `openspec/` | Spec-driven development (propose → apply → archive) |
| `src/maestro/` | Python source code |
| `elixir/` | Reference Elixir implementation (do not modify) |

## Architecture

Layered design: **CLI → Observability → Coordination → Execution → Integration → Config**

- **Protocol-first**: Define ABCs before implementations (`Tracker`, `AgentRunner`, `SandboxManager`)
- **Pydantic v2** for all configuration models
- **Async** for I/O-bound (tracker, HTTP, agent streaming); **sync** for CPU-bound (config, paths)
- **No global mutable state** — orchestrator state is encapsulated

See [`openspec/project.md`](openspec/project.md) for full conventions.

## OpenSpec Workflow

Every feature starts as a formal change before code is written:

```bash
openspec propose <name>     # Create change scaffold
openspec list               # Show active changes
openspec status --change <name>  # Show task progress
openspec apply <name>       # Implement tasks
openspec archive <name>     # Archive completed change
```

Each change in `openspec/changes/<name>/` has: `proposal.md`, `design.md`, `tasks.md`, `specs/`.

**Rules:**
- Reference SPEC.md sections explicitly in proposals
- Keep tasks small (1-4 hours each)
- Delta specs only — write what's new/changed, don't duplicate SPEC.md
- Archive promptly when all tasks are complete

## Key Conventions

- **Formatter**: `ruff format` (Black-compatible, 100 char line length)
- **Type checking**: `mypy --strict`
- **Testing**: pytest, 100% coverage on core modules
- **Docstrings**: Google style for public functions/classes
- **Naming**: `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants

## Important Boundaries

- **SPEC.md is authoritative** — implementation must not conflict with the spec
- **Workspace safety is critical** — agent cwd must equal workspace path, paths must stay under workspace root
- **Orchestrator is stateful** — preserve retry, reconciliation, and cleanup semantics
- **Config via Pydantic** — use typed models with validators, not ad-hoc env reads

## Behavioral Guidelines

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Related Documentation

- [SPEC.md](SPEC.md) — Full Symphony specification
- [PRD.md](PRD.md) — Product requirements and implementation phases
- [openspec/project.md](openspec/project.md) — Project conventions and OpenSpec workflow
- [elixir/README.md](elixir/README.md) — Reference Elixir implementation
