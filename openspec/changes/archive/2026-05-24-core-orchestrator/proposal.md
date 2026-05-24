## Problem

SPEC §7, §8, and §16 define the orchestrator as the central coordination layer:

1. **Orchestration state machine** — issue states (Unclaimed, Claimed, Running, RetryQueued, Released), run attempt lifecycle, transition triggers, idempotency rules (§7)
2. **Polling, scheduling, reconciliation** — poll loop, candidate selection, concurrency control, retry/backoff, active run reconciliation, startup cleanup (§8)
3. **Reference algorithms** — service startup, poll-and-dispatch tick, reconcile active runs, dispatch one issue, worker attempt, worker exit and retry handling (§16)

All foundational layers are now implemented and archived:
- `workflow-config` — config loading, $VAR resolution, validation
- `prompt-builder` — Jinja2 strict template rendering
- `tracker-linear` — Linear GraphQL adapter with pagination
- `workspace-manager` — workspace creation, hooks, path safety
- `agent-runner` — Codex app-server client with stdio protocol

The orchestrator is the final piece that ties everything together into a working service.

## What Changes

- Implement `OrchestratorState` with `running`, `claimed`, `retry_attempts`, `completed`, `codex_totals`, `codex_rate_limits`
- Implement `Orchestrator` class with poll loop, dispatch, reconciliation, retry scheduling
- Implement candidate selection with sorting (priority, created_at, identifier) and eligibility checks
- Implement concurrency control (global + per-state limits, Todo blocker gating)
- Implement retry/backoff scheduling (continuation 1s fixed, failure-driven exponential with cap)
- Implement active run reconciliation (stall detection, tracker state refresh, terminal/non-active handling)
- Implement startup terminal workspace cleanup
- Implement dispatch preflight validation integration
- Implement graceful shutdown on SIGTERM/SIGINT
- Write unit tests for state machine transitions, dispatch logic, retry scheduling, reconciliation

## Capabilities

### New Capabilities

- `orchestrator-poll`: Poll tracker on configurable cadence, dispatch eligible issues
- `orchestrator-reconcile`: Stop runs on terminal/non-active tracker states, detect stalled sessions
- `orchestrator-retry`: Schedule retries with exponential backoff and continuation delays
- `orchestrator-concurrency`: Enforce global and per-state concurrency limits
- `orchestrator-state`: Maintain single-authority in-memory state with serialized mutations

### Modified Capabilities

None — this is a new capability.

## Impact

- **New modules:**
  - `src/maestro/core/state.py` — `OrchestratorState`, `RunningEntry`, `RetryEntry` models
  - `src/maestro/core/orchestrator.py` — `Orchestrator` class with poll/dispatch/reconcile/retry
  - `src/maestro/core/scheduler.py` — Poll tick scheduling and retry timer management
  - `src/maestro/core/reconciliation.py` — Stall detection and tracker state refresh
- **Depends on:** All archived changes (`workflow-config`, `prompt-builder`, `tracker-linear`, `workspace-manager`, `agent-runner`)
- **No breaking changes**
