## Problem

SPEC §13 defines the logging, status, and observability requirements:

1. **Logging conventions** — structured logs with issue_id, issue_identifier, session_id context fields (§13.1)
2. **Logging outputs and sinks** — multiple sinks, non-crashing on sink failure (§13.2)
3. **Runtime snapshot** — running sessions, retry queue, token totals, rate limits (§13.3)
4. **Session metrics and token accounting** — delta tracking from absolute totals, aggregate totals, live runtime (§13.5)
5. **Humanized agent event summaries** — optional, observability-only (§13.6)

The `core-orchestrator` change implements the orchestrator with token tracking in `CodexTotals`, but the observability layer (structured logging, snapshot API, token accounting utilities) is not yet a dedicated module. This change extracts and formalizes the observability concerns.

## What Changes

- Implement structured logging helper with issue/session context fields
- Implement `RuntimeSnapshot` dataclass matching SPEC §13.3 response shape
- Implement `SnapshotBuilder` to assemble snapshot from orchestrator state
- Implement token accounting utilities (delta tracking, aggregate computation)
- Implement rate-limit tracking and presentation
- Implement humanized agent event summaries (optional)
- Write unit tests for snapshot assembly, token accounting, and logging

## Capabilities

### New Capabilities

- `structured-logging`: Emit logs with issue_id, issue_identifier, session_id context
- `runtime-snapshot`: Assemble runtime state snapshot for dashboards/monitoring
- `token-accounting`: Delta tracking from absolute totals, aggregate computation
- `rate-limit-tracking`: Track and present latest rate-limit payload

### Modified Capabilities

None — this is a new capability.

## Impact

- **New modules:**
  - `src/maestro/observability/logging.py` — Structured logging helpers
  - `src/maestro/observability/snapshot.py` — `RuntimeSnapshot`, `SnapshotBuilder`
  - `src/maestro/observability/tokens.py` — Token accounting utilities
- **Depends on:** `core-orchestrator` (for `OrchestratorState`, `RunningEntry`, `RetryEntry`)
- **No breaking changes**
