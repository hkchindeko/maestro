# Maestro — Product Requirements Document

**Status:** Draft v1  
**Date:** May 16, 2026  
**Spec Reference:** [`SPEC.md`](../SPEC.md)  
**Inspiration:** [Contrebass](https://github.com/junhoyeo/contrabass) (Go implementation)

---

## 1. Vision

**Maestro** is a Python implementation of the [OpenAI Symphony specification](../SPEC.md) — a long-running automation service that continuously reads work from an issue tracker, creates isolated per-issue workspaces, and runs coding agent sessions to execute those issues autonomously.

Maestro targets Python developers and teams who want a modern, extensible, CLI-first orchestration tool with:

- **Zero-config local mode** — run against a filesystem-backed board without any external service
- **Production-ready tracker integration** — Linear, GitHub Issues, and extensible adapter pattern
- **Multi-agent support** — Codex, Claude Code, GitHub Copilot CLI, and custom agents
- **Rich operator experience** — TUI, web dashboard, structured logging, and JSON REST API
- **Spec-driven development** — every feature traced back to a SPEC.md requirement via OpenSpec

---

## 2. Goals

| # | Goal | SPEC Reference |
|---|------|----------------|
| G1 | Implement all **Core Conformance** requirements from SPEC §18.1 | §18.1 |
| G2 | Provide a **Typer-based CLI** with subcommands for run, team, board, and config | §17.7 |
| G3 | Support **single-agent** and **team execution** modes | Contrebass pattern |
| G4 | Include a **filesystem-backed internal board** for testing and standalone use | Contrebass `internal` tracker |
| G5 | Ship with **OpenSpec** change management — every domain has proposal → design → tasks → archive | OpenSpec workflow |
| G6 | Achieve **100% test coverage** on core modules | §17, Elixir `mix.exs` |
| G7 | Provide **TUI + web dashboard** for operator visibility | §13.7 |

---

## 3. Non-Goals

- Multi-tenant control plane or SaaS offering
- Prescribing a specific sandbox hardening posture (implementation-defined per SPEC §15)
- Built-in business logic for ticket mutations (handled by agent tools per SPEC §11.5)
- Distributed job scheduler or general-purpose workflow engine

---

## 4. Architecture Overview

### 4.1 Layered Design

```
┌─────────────────────────────────────────────────┐
│                   CLI Layer                      │
│         Typer: run, team, board, config          │
├─────────────────────────────────────────────────┤
│              Observability Layer                 │
│    Structured logging · TUI · HTTP API · Tokens  │
├─────────────────────────────────────────────────┤
│              Coordination Layer                  │
│         Orchestrator · Scheduler · Retry         │
├─────────────────────────────────────────────────┤
│              Execution Layer                     │
│   Workspace · Sandbox · Agent Runner · Prompt    │
├─────────────────────────────────────────────────┤
│              Integration Layer                   │
│      Tracker Adapters (Linear, GitHub, Local)    │
├─────────────────────────────────────────────────┤
│              Configuration Layer                 │
│       Pydantic models · $VAR · ~ expansion       │
└─────────────────────────────────────────────────┘
```

### 4.2 Technology Stack

| Concern | Technology | Rationale |
|---------|-----------|-----------|
| CLI | **Typer** + **Rich** | Auto-help, async support, beautiful TUI |
| Config | **Pydantic v2** | Typed models, validators, clear errors |
| Templates | **Jinja2** (strict mode) | Liquid-compatible, fail on unknowns |
| HTTP | **FastAPI** / Starlette | Async, auto OpenAPI, easy SPA hosting |
| HTTP Client | **httpx** | Async, modern, type-safe |
| File Watch | **watchdog** | Cross-platform `WORKFLOW.md` reload |
| Testing | **pytest** + **coverage** | Industry standard, 100% threshold |
| Linting | **ruff** + **mypy** | Fast lint + type checking |
| Packaging | **uv** + **pyproject.toml** | Fast resolution, modern standard |

---

## 5. CLI Surface

### 5.1 Root Command

```
maestro [WORKFLOW.md] [OPTIONS]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--port <port>` | int | disabled | Enable HTTP dashboard on port |
| `--tracker-kind <kind>` | str | from workflow | Override tracker type |
| `--agent-kind <kind>` | str | from workflow | Override agent type |
| `--sandbox-kind <kind>` | str | `local` | Override sandbox type |
| `--verbose` | flag | false | Enable debug logging |
| `--dry-run` | flag | false | Validate + one poll cycle, no dispatch |
| `--no-tui` | flag | false | Run headless (structured logs only) |
| `--log-file <path>` | str | stderr | Write logs to file |
| `--log-level <level>` | str | `info` | Log level (debug, info, warning, error) |

### 5.2 Subcommands

#### `maestro team`

Multi-worker coordination for internal board issues (Contrebass pattern).

| Command | Description |
|---------|-------------|
| `team run [OPTIONS]` | Start team execution loop |
| `team status` | Show current team status |
| `team list` | List active teams and workers |

#### `maestro board`

Manage the local filesystem-backed issue board.

| Command | Description |
|---------|-------------|
| `board list` | List all board issues by state |
| `board dispatch` | Dispatch eligible issues to teams |
| `board drain` | Dispatch until board is empty |
| `board create` | Create a new board issue |

#### `maestro config`

Inspect and validate workflow configuration.

| Command | Description |
|---------|-------------|
| `config validate [WORKFLOW.md]` | Validate workflow file, report errors |
| `config show [WORKFLOW.md]` | Show resolved config with defaults applied |

---

## 6. Domain Modules

### 6.1 Config & Workflow (`maestro.core.config`, `maestro.core.workflow`)

**Responsibilities:**
- Parse `WORKFLOW.md` YAML front matter + Markdown body
- Resolve `$VAR_NAME` indirection and `~` home expansion
- Apply built-in defaults for optional fields
- Validate required fields (`tracker.kind`, `tracker.api_key`, etc.)
- Support dynamic reload via `watchdog` file watcher

**Pydantic Models:**
```
WorkflowConfig
├── TrackerConfig (kind, endpoint, api_key, project_slug, active_states, terminal_states)
├── PollingConfig (interval_ms)
├── WorkspaceConfig (root)
├── HooksConfig (after_create, before_run, after_run, before_remove, timeout_ms)
├── SandboxConfig (kind, image, resources, env)
├── AgentConfig (kind, command, approval_policy, max_concurrent_agents, max_turns, max_retry_backoff_ms, max_concurrent_agents_by_state)
└── CodexConfig [DEPRECATED] (command, approval_policy, thread_sandbox, turn_sandbox_policy, timeouts)
```

### 6.2 Tracker Adapters (`maestro.tracker.*`)

**Protocol (`Tracker` ABC):**
- `fetch_candidate_issues()` → `list[Issue]`
- `fetch_issues_by_states(states)` → `list[Issue]`
- `fetch_issue_states_by_ids(ids)` → `list[IssueSnapshot]`

**Implementations:**

| Adapter | Protocol | Auth | Notes |
|---------|----------|------|-------|
| `LinearTracker` | GraphQL | `LINEAR_API_KEY` env or `$VAR` | Pagination, project slug filter, blocker extraction |
| `GitHubTracker` | REST API | `GITHUB_TOKEN` env | Issue filtering, state normalization |
| `InternalTracker` | Filesystem | None | `.maestro/board/` directory, CRUD operations, no external service |

**Issue Normalization (all adapters):**
- `labels` → lowercase strings
- `blocked_by` → derived from inverse `blocks` relations
- `priority` → integer only (non-integers → null)
- `state` → lowercase comparison

### 6.3 Workspace Manager (`maestro.workspace.*`)

**Responsibilities:**
- Sanitize issue identifiers → workspace keys (`[A-Za-z0-9._-]`)
- Create/reuse per-issue workspace directories
- Execute lifecycle hooks with timeout enforcement
- Clean up workspaces for terminal issues

**Hooks:**

| Hook | When | Failure Behavior |
|------|------|-----------------|
| `after_create` | New workspace created | Abort workspace creation |
| `before_run` | Before each agent attempt | Abort current attempt |
| `after_run` | After each attempt | Logged, ignored |
| `before_remove` | Before workspace deletion | Logged, ignored |

**Safety Invariants:**
1. Agent `cwd` must equal workspace path
2. Workspace path must be under workspace root
3. Workspace keys are sanitized

### 6.4 Sandbox Manager (`maestro.sandbox.*`)

**Protocol (`SandboxManager` ABC):**
- `provision(issue_id, workspace_path)` → `SandboxSession`
- `teardown(session)` → `None`

**Implementations:**
- `LocalSandbox` (default) — direct host execution
- `DockerSandbox` — container-based isolation with resource limits

### 6.5 Agent Runner (`maestro.agent.*`)

**Protocol (`AgentRunner` ABC):**
- `start_session(workspace, sandbox, prompt)` → `Session`
- `run_turn(session, prompt)` → `TurnResult`
- `stop_session(session)` → `None`

**Implementations:**
- `CodexAgentRunner` — stdio-based app-server protocol (SPEC §10)
- `ClaudeAgentRunner` — Claude Code protocol (stub, extensible)
- `CopilotAgentRunner` — GitHub Copilot CLI protocol (stub, extensible)

**Client-Side Tool Extension:**
- `linear_graphql` — inject raw GraphQL access into agent session using configured Linear auth

### 6.6 Orchestrator (`maestro.core.orchestrator`)

**Responsibilities:**
- Own the poll tick loop
- Maintain single-authority in-memory state
- Dispatch eligible issues with bounded concurrency
- Reconcile running issues (stall detection + state refresh)
- Schedule retries with exponential backoff

**State Machine (§7.1):**
```
Unclaimed → Claimed → Running → Released
                      ↘ RetryQueued ↗
```

**Concurrency Control:**
- Global limit: `max_concurrent_agents` (default: 10)
- Per-state limit: `max_concurrent_agents_by_state[state]`
- `Todo` blocker gating: no dispatch when non-terminal blockers exist

**Retry Logic:**
- Continuation (normal exit): fixed 1s delay
- Failure-driven: `min(10000 * 2^(attempt-1), max_retry_backoff_ms)`
- Default cap: 300,000ms (5 minutes)

### 6.7 Prompt Builder (`maestro.prompt.*`)

**Responsibilities:**
- Render `WORKFLOW.md` prompt body with Jinja2 (strict mode)
- Inject `issue` object (all normalized fields) and `attempt` integer
- Fail on unknown variables or filters
- Support first-run vs. retry/continuation prompt variants

### 6.8 Observability (`maestro.observability.*`)

**Structured Logging:**
- Context fields: `issue_id`, `issue_identifier`, `session_id`
- `key=value` phrasing, action outcomes, concise failure reasons
- Multiple sinks, non-crashing on sink failure

**Token Accounting:**
- Delta tracking from agent events (avoid double-counting)
- Aggregate totals: input, output, total tokens
- Live runtime calculation at snapshot time

**Runtime Snapshot (§13.3):**
```json
{
  "generated_at": "2026-05-16T10:00:00Z",
  "counts": { "running": 2, "retrying": 1 },
  "running": [...],
  "retrying": [...],
  "codex_totals": {
    "input_tokens": 5000,
    "output_tokens": 2400,
    "total_tokens": 7400,
    "seconds_running": 1834.2
  },
  "rate_limits": null
}
```

### 6.9 HTTP Server (`maestro.web.*`)

**Extension** — not required for conformance, enabled via `--port` or `server.port` config.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Human-readable dashboard |
| `GET` | `/api/v1/state` | Full runtime state snapshot |
| `GET` | `/api/v1/{issue_identifier}` | Issue-specific debug details |
| `POST` | `/api/v1/refresh` | Trigger immediate poll + reconcile |

**Bind:** loopback (`127.0.0.1`) by default, configurable.

---

## 7. Execution Modes

### 7.1 Single-Agent Mode (Default)

The standard Symphony workflow: poll tracker → dispatch issues → run agents → reconcile.

```
maestro ./WORKFLOW.md
```

### 7.2 Team Mode

Multi-worker coordination for internal board issues. Each team has its own worker pool and dispatches board issues independently.

```
maestro team run --team alpha
```

**Constraints:**
- Requires `tracker.type: internal` (or `local`)
- Teams are defined in `WORKFLOW.md` front matter
- Board issues are assigned to teams by label or explicit mapping

### 7.3 Board Mode

Standalone management of the local filesystem board without running agents.

```
maestro board list
maestro board drain
```

---

## 8. OpenSpec Development Workflow

Maestro uses [OpenSpec](https://github.com/openspec-labs/openspec) for spec-driven development. Each domain is a **change** with artifacts:

```
openspec/changes/<change-name>/
├── .openspec.yaml          # Change metadata
├── proposal.md             # What & why
├── design.md               # How (decisions, trade-offs)
├── tasks.md                # Implementation steps with checkboxes
└── specs/                  # Delta specs (synced to openspec/specs/ on archive)
```

### 8.1 Change Lifecycle

1. **Propose** — `openspec propose <name>` creates scaffold with proposal/design/tasks
2. **Apply** — `openspec apply <name>` implements tasks, updates progress
3. **Archive** — `openspec archive <name>` moves to `archive/`, syncs specs

### 8.2 Initial Changes

| Change | Domain | Priority |
|--------|--------|----------|
| `core-orchestrator` | Poll loop, state machine, dispatch, reconcile | P0 |
| `workflow-config` | Pydantic config, WORKFLOW.md loader, $VAR resolution | P0 |
| `tracker-linear` | Linear GraphQL adapter, pagination, normalization | P0 |
| `workspace-manager` | Directory management, hooks, path safety | P0 |
| `agent-runner` | Codex app-server client, stdio protocol, events | P0 |
| `prompt-builder` | Jinja2 template rendering, strict mode | P1 |
| `sandbox-manager` | Local + Docker sandbox provisioning | P1 |
| `observability` | Structured logging, token accounting, snapshot | P1 |
| `http-dashboard` | FastAPI server, REST API, HTML dashboard | P2 |
| `internal-board` | Filesystem tracker, board CLI commands | P2 |
| `team-mode` | Multi-worker coordination, team dispatch | P2 |
| `tracker-github` | GitHub Issues REST adapter | P3 |

---

## 9. Project Structure

```
maestro/
├── pyproject.toml                 # uv/pip, dependencies, entry points
├── README.md
├── PRD.md                         # This document
├── WORKFLOW.md                    # Default workflow template
├── openspec/                      # OpenSpec spec-driven development
│   ├── project.md
│   ├── specs/
│   └── changes/
├── src/maestro/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli/                       # Typer CLI commands
│   │   ├── main.py
│   │   ├── team.py
│   │   ├── board.py
│   │   └── config.py
│   ├── core/                      # Domain logic
│   │   ├── config.py
│   │   ├── workflow.py
│   │   ├── orchestrator.py
│   │   ├── state.py
│   │   ├── scheduler.py
│   │   └── reconciliation.py
│   ├── tracker/                   # Issue tracker adapters
│   │   ├── base.py
│   │   ├── linear.py
│   │   ├── github.py
│   │   └── internal.py
│   ├── workspace/                 # Workspace management
│   │   ├── manager.py
│   │   ├── hooks.py
│   │   └── safety.py
│   ├── sandbox/                   # AI sandbox provisioning
│   │   ├── base.py
│   │   ├── local.py
│   │   └── docker.py
│   ├── agent/                     # Coding agent runners
│   │   ├── base.py
│   │   ├── codex.py
│   │   ├── claude.py
│   │   └── copilot.py
│   ├── prompt/                    # Prompt construction
│   │   ├── builder.py
│   │   └── models.py
│   ├── observability/             # Logging + status
│   │   ├── logging.py
│   │   ├── snapshot.py
│   │   └── tokens.py
│   ├── web/                       # HTTP server extension
│   │   ├── server.py
│   │   ├── api.py
│   │   └── dashboard.py
│   ├── team/                      # Team execution mode
│   │   ├── coordinator.py
│   │   └── dispatcher.py
│   └── utils/
│       ├── env.py
│       ├── paths.py
│       └── retry.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── docs/
```

---

## 10. Implementation Phases

### Phase 1: Bootstrap (Week 1)
- [ ] `pyproject.toml` with all dependencies
- [ ] OpenSpec project setup + first change scaffolds
- [ ] `src/maestro/__init__.py`, `__main__.py`
- [ ] Basic CLI skeleton with Typer

### Phase 2: Config & Workflow (Week 1-2)
- [ ] Pydantic config models with defaults and validation
- [ ] `WORKFLOW.md` loader (YAML front matter + body)
- [ ] `$VAR` resolution and `~` expansion
- [ ] Jinja2 prompt renderer (strict mode)
- [ ] Dynamic file watch + reload

### Phase 3: Tracker Adapters (Week 2-3)
- [ ] `Tracker` ABC protocol
- [ ] `LinearTracker` with GraphQL, pagination, normalization
- [ ] `InternalTracker` (filesystem board)
- [ ] `GitHubTracker` (REST API)

### Phase 4: Workspace & Sandbox (Week 3)
- [ ] `WorkspaceManager` with sanitization and hooks
- [ ] `PathSafety` invariants
- [ ] `SandboxManager` protocol + `LocalSandbox`
- [ ] `DockerSandbox` (optional)

### Phase 5: Agent Runner (Week 3-4)
- [ ] `AgentRunner` ABC protocol
- [ ] `CodexAgentRunner` (stdio app-server protocol)
- [ ] `linear_graphql` client-side tool
- [ ] Claude/Copilot stubs

### Phase 6: Orchestrator (Week 4-5)
- [ ] `OrchestratorState` in-memory model
- [ ] Poll-and-dispatch tick loop
- [ ] Concurrency control (global + per-state)
- [ ] Retry/backoff scheduling
- [ ] Reconciliation (stall detection + state refresh)

### Phase 7: CLI & TUI (Week 5-6)
- [ ] Root command with all flags
- [ ] `team` subcommands
- [ ] `board` subcommands
- [ ] `config` subcommands
- [ ] Rich TUI with live tables

### Phase 8: Observability & HTTP (Week 6)
- [ ] Structured logging
- [ ] Token accounting
- [ ] FastAPI server + REST API
- [ ] Web dashboard

### Phase 9: Testing & CI (Week 6-7)
- [ ] Unit tests (100% coverage on core)
- [ ] Integration tests
- [ ] E2E smoke tests
- [ ] CI pipeline (pytest, ruff, mypy)

---

## 11. Conformance Checklist

### 11.1 Core Conformance (REQUIRED — SPEC §18.1)

- [x] Workflow path selection (explicit + cwd default)
- [x] `WORKFLOW.md` loader with YAML front matter + prompt body
- [x] Typed config layer with defaults and `$` resolution
- [x] Dynamic `WORKFLOW.md` watch/reload/re-apply
- [x] Polling orchestrator with single-authority mutable state
- [x] Issue tracker client (candidate fetch + state refresh + terminal fetch)
- [x] Workspace manager with sanitized per-issue workspaces
- [x] Sandbox manager for provisioning
- [x] Workspace lifecycle hooks with timeout config
- [x] Coding-agent subprocess client (multiple agent kinds)
- [x] Agent launch command config
- [x] Strict prompt rendering with `issue` and `attempt`
- [x] Exponential retry queue with continuation retries
- [x] Configurable retry backoff cap
- [x] Reconciliation stopping runs on terminal/non-active states
- [x] Workspace cleanup for terminal issues
- [x] Structured logs with `issue_id`, `issue_identifier`, `session_id`
- [x] Operator-visible observability

### 11.2 Recommended Extensions (OPTIONAL — SPEC §18.2)

- [ ] HTTP server with CLI `--port` override, loopback bind, baseline endpoints
- [ ] `linear_graphql` client-side tool extension
- [ ] Multiple tracker kinds (Linear, GitHub, Internal)
- [ ] Multiple sandbox kinds (Local, Docker)
- [ ] Multiple agent kinds (Codex, Claude, Copilot)
- [ ] Persist retry queue across restarts (TODO in spec)
- [ ] Configurable observability settings (TODO in spec)
- [ ] First-class tracker write APIs (TODO in spec)

---

## 12. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Codex app-server protocol drift | High | Isolate protocol handling, test against installed `codex` version |
| Linear GraphQL API changes | Medium | Pin query fields, test with real API in CI |
| Hook script injection | High | Timeout enforcement, trusted config boundary, log truncation |
| Token double-counting | Medium | Delta tracking from absolute totals, unit tests |
| Workspace path escape | Critical | Path containment checks before every agent launch, unit tests |
| Orchestrator state corruption | High | Single-authority mutations, defensive reload validation |

---

## 13. Success Criteria

1. **Spec Conformance**: All §18.1 items pass deterministic tests
2. **CLI Usability**: `maestro --help` is self-documenting, `--dry-run` validates config safely
3. **Local-First**: `maestro board drain` works with zero external dependencies
4. **Production Ready**: Real Linear integration test passes with valid credentials
5. **Developer Experience**: `uv run pytest` passes, `uv run ruff check` clean, `uv run mypy` clean
6. **OpenSpec Traceability**: Every feature maps to a change with proposal → design → tasks → archive
