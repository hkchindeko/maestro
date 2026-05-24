## Context

The observability layer provides structured logging, runtime snapshots, and token accounting. SPEC §13 defines the exact requirements for logging conventions, snapshot shape, and token accounting rules.

Key SPEC sections:
- §13.1: Logging conventions (context fields, message formatting)
- §13.2: Logging outputs and sinks (multiple sinks, non-crashing)
- §13.3: Runtime snapshot (running, retrying, codex_totals, rate_limits)
- §13.5: Session metrics and token accounting (delta tracking, aggregate totals, live runtime)
- §13.6: Humanized agent event summaries (optional, observability-only)

## Decisions

### Decision 1: Structured logging via Python logging adapter

**Why:** Python's `logging` module supports `LoggerAdapter` for adding context fields to every log record. This maps directly to SPEC §13.1's requirement for issue_id, issue_identifier, session_id context fields.

**Alternatives considered:**
- `structlog` — more feature-rich but adds dependency; stdlib logging is sufficient
- Manual context in every log call — error-prone, verbose

### Decision 2: Snapshot as a dataclass, not JSON dict

**Why:** SPEC §13.3 defines a specific response shape. A dataclass provides type safety and IDE support. The `SnapshotBuilder` assembles the snapshot from orchestrator state and converts to dict for JSON serialization.

**Alternatives considered:**
- Direct dict construction — no type safety, harder to test
- Pydantic model — overkill for read-only snapshot data

### Decision 3: Token accounting in orchestrator state, not separate module

**Why:** SPEC §13.5 states "Accumulate aggregate totals in orchestrator state." The `CodexTotals` in `OrchestratorState` (from core-orchestrator change) already handles this. The observability module provides utilities for delta computation and live runtime calculation, but the state lives in the orchestrator.

**Alternatives considered:**
- Separate token accounting service — unnecessary indirection, tightly coupled to orchestrator

### Decision 4: Humanized summaries as pure functions

**Why:** SPEC §13.6 states humanized summaries are "observability-only output" and "do not make orchestrator logic depend on humanized strings." Pure functions that take an event type and payload and return a string are easily testable and have no side effects.

## Non-Decisions

- **Log sink configuration** — spec doesn't prescribe sinks; uses stdlib logging defaults
- **Remote log shipping** — out of scope; operators can configure logging handlers externally
- **Metrics export (Prometheus, etc.)** — out of scope for v1

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Snapshot assembly slows under many running sessions | Low | Snapshot is O(n) in running count; n is bounded by max_concurrent_agents |
| Token double-counting in snapshot | Medium | Delta tracking from absolute totals, tested independently |
| Log output volume under high concurrency | Low | Structured logging is efficient; operators can configure log levels |
