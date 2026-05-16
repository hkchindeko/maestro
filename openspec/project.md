# Maestro — OpenSpec Project

## Project Overview

**Maestro** is a Python implementation of the [OpenAI Symphony specification](../SPEC.md) — a long-running automation service that orchestrates coding agents to execute issue tracker work autonomously.

- **Repository:** `openai/symphony` (Python implementation lives alongside the Elixir reference)
- **Spec of truth:** [`SPEC.md`](../SPEC.md) at repository root
- **PRD:** [`PRD.md`](../PRD.md)
- **Language:** Python 3.12+
- **Package manager:** uv
- **CLI framework:** Typer + Rich

---

## Conventions

### Code Style

- **Formatter:** `ruff format` (Black-compatible)
- **Linter:** `ruff check` with strict rules
- **Type checking:** `mypy --strict` on all modules
- **Line length:** 100 characters
- **Imports:** grouped as stdlib → third-party → local, sorted alphabetically
- **Docstrings:** Google style for all public functions and classes

### Architecture Rules

1. **Layered design** — CLI → Observability → Coordination → Execution → Integration → Config
2. **Protocol-first** — define ABCs before implementations (e.g., `Tracker`, `AgentRunner`, `SandboxManager`)
3. **Pydantic for config** — all configuration uses Pydantic v2 models with validators
4. **Async where I/O-bound** — tracker calls, HTTP server, agent streaming use `asyncio`
5. **Sync where CPU-bound** — config parsing, prompt rendering, path safety are synchronous
6. **No global mutable state** — orchestrator state is encapsulated, passed explicitly

### Testing

- **Framework:** pytest with `asyncio` plugin
- **Coverage:** 100% threshold on core modules (`maestro.core.*`, `maestro.workspace.*`, `maestro.tracker.base`)
- **Fixtures:** in `tests/fixtures/`, snapshot-based where applicable
- **Mocking:** prefer protocol-based fakes over `unittest.mock` where practical

### Naming

- **Modules:** `snake_case` (e.g., `workspace_manager.py`)
- **Classes:** `PascalCase` (e.g., `WorkflowConfig`, `LinearTracker`)
- **Functions:** `snake_case` (e.g., `fetch_candidate_issues`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `DEFAULT_POLL_INTERVAL_MS`)
- **Private:** prefix with `_` (e.g., `_resolve_env_var`)

---

## OpenSpec Workflow

Every feature is developed through a **change** with formal artifacts. The lifecycle is:
