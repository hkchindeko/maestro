## 1. Orchestrator state model

- [x] 1.1 Define `RunningEntry` dataclass with issue metadata, session info, token counters, timestamps per SPEC §4.1.6
- [x] 1.2 Define `RetryEntry` dataclass with issue_id, identifier, attempt, due_at_ms, timer_handle, error per SPEC §4.1.7
- [x] 1.3 Define `OrchestratorState` with `running`, `claimed`, `retry_attempts`, `completed`, `codex_totals`, `codex_rate_limits` per SPEC §4.1.8
- [x] 1.4 Implement state mutation methods with asyncio.Lock protection per SPEC §7.4
- [x] 1.5 Write unit tests for state transitions and lock serialization

## 2. Poll-and-dispatch tick

- [x] 2.1 Implement `on_tick()` following SPEC §16.2 algorithm (reconcile → validate → fetch → sort → dispatch)
- [x] 2.2 Implement candidate issue sorting (priority asc, created_at asc, identifier tie-break) per SPEC §8.2
- [x] 2.3 Implement dispatch eligibility checks (active state, not running, not claimed, slots available)
- [x] 2.4 Implement Todo blocker gating (no dispatch when non-terminal blockers exist) per SPEC §8.2
- [x] 2.5 Implement slot exhaustion break (stop dispatching when no slots remain)
- [x] 2.6 Write unit tests for dispatch sorting and eligibility

## 3. Concurrency control

- [x] 3.1 Implement global slot calculation: `max(max_concurrent_agents - running_count, 0)` per SPEC §8.3
- [x] 3.2 Implement per-state limit lookup with normalized state keys
- [x] 3.3 Write unit tests for slot exhaustion and per-state overrides

## 4. Retry & backoff

- [x] 4.1 Implement continuation retry scheduling (fixed 1000ms delay after normal exit) per SPEC §8.4
- [x] 4.2 Implement failure-driven exponential backoff: `min(10000 * 2^(attempt-1), max_retry_backoff_ms)`
- [x] 4.3 Implement retry timer firing with candidate re-fetch and dispatch-or-requeue logic
- [x] 4.4 Implement retry entry creation that cancels existing timer for same issue
- [x] 4.5 Write unit tests for backoff formula and retry handling

## 5. Reconciliation

- [x] 5.1 Implement stall detection: elapsed since last_codex_timestamp or started_at vs stall_timeout_ms per SPEC §8.5
- [x] 5.2 Implement tracker state refresh for all running issue IDs
- [x] 5.3 Implement terminal state handling (terminate worker + cleanup workspace)
- [x] 5.4 Implement non-active state handling (terminate worker without cleanup)
- [x] 5.5 Implement refresh failure handling (keep workers running, retry next tick)
- [x] 5.6 Write unit tests for reconciliation scenarios

## 6. Startup & lifecycle

- [x] 6.1 Implement startup terminal workspace cleanup per SPEC §8.6
- [x] 6.2 Implement dispatch preflight validation integration per SPEC §6.3
- [x] 6.3 Implement graceful shutdown on SIGTERM/SIGINT
- [x] 6.4 Implement poll loop with configurable interval and dynamic reload support
- [x] 6.5 Write unit tests for startup and shutdown

## 7. Integration tests

- [x] 7.1 Test full tick with mock tracker + mock agent (dispatch → run → complete)
- [x] 7.2 Test reconciliation stopping runs on terminal tracker state
- [x] 7.3 Test retry scheduling after worker failure
- [x] 7.4 Test concurrency limit enforcement (no dispatch when slots full)
- [x] 7.5 Test Todo blocker gating (no dispatch with non-terminal blockers)
- [x] 7.6 Test stall detection terminating stalled sessions
