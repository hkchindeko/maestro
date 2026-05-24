## Problem

SPEC §16.1 and §17.7 define service startup and host lifecycle, but the current
`maestro run` command only validates configuration. It does not construct the runtime graph or
start the orchestrator. When `--port` is provided, it starts the HTTP server with a placeholder
`OrchestratorState` instead of the real orchestrator state.

The foundational pieces already exist:

- `workflow-config` — load and resolve `WORKFLOW.md`
- `tracker-linear` — Linear tracker adapter
- `workspace-manager` — per-issue workspaces, hooks, path safety
- `prompt-builder` — strict Jinja2 prompt rendering
- `agent-runner` — Codex app-server client
- `core-orchestrator` — poll loop, dispatch, reconciliation, retry
- `http-dashboard` — FastAPI app, REST endpoints, HTML dashboard

What is missing is the composition layer that turns a validated workflow into a running Maestro
process.

## What Changes

- Add runtime composition/factory code that builds the supported tracker, workspace manager,
  prompt builder, agent runner, and orchestrator from resolved configuration
- Apply CLI overrides (`--tracker-kind`, `--agent-kind`, `--sandbox-kind`, `--port`) before
  validation and component construction
- Wire `maestro run` to start the orchestrator event loop
- When enabled, start the HTTP server alongside the orchestrator using the orchestrator's real state
- Wire HTTP refresh requests to an immediate best-effort orchestrator tick/reconcile trigger
- Add graceful SIGTERM/SIGINT handling that stops orchestrator and HTTP server tasks cleanly
- Return clear nonzero startup errors for unsupported component kinds or invalid config
- Write unit and integration tests for composition, CLI startup paths, HTTP co-run behavior, refresh,
  and shutdown

## Capabilities

### New Capabilities

- `runtime-composition`: Build the concrete runtime graph from `WorkflowConfig`
- `cli-run-service`: `maestro run` starts the actual orchestration service
- `http-orchestrator-cowiring`: Optional HTTP server observes and controls the real orchestrator
  state
- `host-lifecycle`: Signal-aware startup, cancellation, and graceful shutdown

### Modified Capabilities

- `http-dashboard`: `/refresh` becomes connected to the running orchestrator instead of storing an
  unconsumed event
- `workflow-config`: CLI overrides are applied before dispatch validation for runtime startup

## Non-Goals

- Implementing new tracker kinds beyond Linear
- Implementing non-local sandbox backends
- Implementing new agent kinds beyond Codex
- Durable retry/session persistence across process restarts
- Authentication, TLS, or remote binding for the HTTP dashboard
- Reworking orchestrator dispatch algorithms already covered by `core-orchestrator`

## Impact

- **New modules:**
  - `src/maestro/runtime.py` — runtime factory and service lifecycle helpers
- **Modified modules:**
  - `src/maestro/cli/main.py` — start runtime instead of stopping after validation
  - `src/maestro/web/app.py` — expose server lifecycle that can run beside orchestrator
  - `src/maestro/web/routes.py` — route refresh requests to runtime/orchestrator trigger
  - `src/maestro/core/orchestrator.py` — expose a safe immediate tick/refresh trigger if needed
- **Depends on:** `workflow-config`, `tracker-linear`, `workspace-manager`, `prompt-builder`,
  `agent-runner`, `core-orchestrator`, `http-dashboard`
- **No breaking changes** to existing config or public model types
