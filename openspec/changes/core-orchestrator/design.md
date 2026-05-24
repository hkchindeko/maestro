## Context

The orchestrator is the central coordination layer of Maestro. It owns the poll tick loop, in-memory runtime state, dispatch decisions, retry scheduling, and reconciliation. It depends on the tracker adapter for issue data, the workspace manager for directory lifecycle, the agent runner for coding agent execution, and the prompt builder for template rendering.

Key SPEC sections:
- §7: Orchestration State Machine (states, lifecycle, transitions, idempotency)
- §8: Polling, Scheduling, and Reconciliation (poll loop, candidate selection, concurrency, retry, reconciliation, startup cleanup)
- §16: Reference Algorithms (startup, tick, reconcile, dispatch, worker attempt, exit/retry)

## Decisions

### Decision 1: In-memory state with tracker-driven recovery

**Why:** SPEC §2.1 and §14.3 explicitly state that exact in-memory scheduler state is not restored across restarts. Recovery is tracker-driven and filesystem-driven. This simplifies the design — no durable state store needed for v1.

**Alternatives considered:** SQLite-backed state for retry queue persistence. Deferred to a future change (see PRD §11.2 TODO).

### Decision 2: Async poll loop with asyncio

**Why:** Tracker API calls, agent streaming, and HTTP server are all I/O-bound. Using `asyncio` allows concurrent operations without thread overhead. The tick loop is an async task that sleeps between polls.

**Alternatives considered:** Threading-based poll loop. Rejected — more complex synchronization, no benefit for I/O-bound work.

### Decision 3: Single orchestrator instance per process

**Why:** SPEC §3.1 states "Maintain a single authoritative orchestrator state." One instance per process avoids distributed coordination complexity. Horizontal scaling (multiple orchestrators) is out of scope.

### Decision 4: Retry scheduling via asyncio.sleep

**Why:** Simple, no external dependencies. Each retry entry gets its own `asyncio.create_task` with a sleep until `due_at_ms`. On process restart, retry timers are lost (per Decision 1).

**Alternatives considered:** APScheduler, Celery. Rejected — overkill for in-memory scheduling, adds deployment complexity.

### Decision 5: State mutations through a single async lock

**Why:** SPEC §7.4 requires serialized state mutations to avoid duplicate dispatch. An `asyncio.Lock` around all state mutations ensures single-authority without deadlocks.

### Decision 6: Worker tasks as asyncio.Task

**Why:** Each dispatched issue gets an `asyncio.Task` that runs the full worker attempt lifecycle (workspace → prompt → agent → hooks). The orchestrator tracks these tasks in the `running` map and can cancel them on reconciliation.

**Alternatives considered:** Subprocess-per-worker — overkill, agent runner already manages subprocess
Thread-per-worker — more complex synchronization, asyncio is sufficient

## Non-Decisions

- **Distributed orchestration** — single process only, no multi-node coordination
- **Durable retry queue** — retry timers are lost on restart (SPEC §14.3)
- **Custom scheduling algorithm** — follows SPEC §16 reference algorithms exactly

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Async lock contention under high concurrency | Medium | Lock is held briefly; state mutations are dict/set operations |
| Tracker API slowness blocking poll loop | Medium | Tracker calls have configurable timeout (§11.2: 30s for Linear) |
| Memory growth from `completed` set | Low | Set is bookkeeping only; can be bounded or pruned in future |
| Stall detection false positives | Medium | Configurable stall timeout; default 5m per SPEC §5.3.7 |
