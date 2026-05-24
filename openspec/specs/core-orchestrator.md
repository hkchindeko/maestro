## ADDED Requirements

### Requirement: Orchestrator state machine
> Source: SPEC §7

The orchestrator SHALL maintain these internal issue states:
- `Unclaimed` — issue is not running and has no retry scheduled
- `Claimed` — orchestrator has reserved the issue to prevent duplicate dispatch
- `Running` — worker task exists and issue is tracked in `running` map
- `RetryQueued` — worker is not running, but a retry timer exists in `retry_attempts`
- `Released` — claim removed because issue is terminal, non-active, missing, or retry path completed

Transition triggers:
- `Poll Tick` → reconcile, validate, fetch, dispatch
- `Worker Exit (normal)` → remove running entry, schedule continuation retry
- `Worker Exit (abnormal)` → remove running entry, schedule exponential-backoff retry
- `Retry Timer Fired` → re-fetch candidates, attempt re-dispatch or release claim
- `Reconciliation State Refresh` → stop runs whose issue states are terminal or no longer active
- `Stall Timeout` → kill worker and schedule retry

**Tests:**
- State transitions follow the defined state machine
- Concurrent dispatch attempts result in only one worker launched

### Requirement: Poll-and-dispatch tick loop
> Source: SPEC §8.1, §16.2

The orchestrator SHALL execute a poll tick on a configurable interval (`polling.interval_ms`):
1. Reconcile running issues
2. Run dispatch preflight validation
3. Fetch candidate issues from tracker
4. Sort by dispatch priority
5. Dispatch eligible issues while slots remain

If per-tick validation fails, dispatch SHALL be skipped but reconciliation SHALL still run.

**Tests:**
- Tick executes in correct sequence
- Validation failure skips dispatch but runs reconciliation
- Tracker fetch failure skips dispatch for that tick

### Requirement: Candidate selection and sorting
> Source: SPEC §8.2

An issue is dispatch-eligible only if all are true:
- It has `id`, `identifier`, `title`, and `state`
- Its state is in `active_states` and not in `terminal_states`
- It is not already in `running`
- It is not already in `claimed`
- Global concurrency slots are available
- Per-state concurrency slots are available
- Blocker rule for `Todo` state passes: if issue state is `Todo`, do not dispatch when any blocker is non-terminal

Sorting order (stable intent):
1. `priority` ascending (1..4 preferred; null/unknown sorts last)
2. `created_at` oldest first
3. `identifier` lexicographic tie-breaker

**Tests:**
- Dispatch sort order is priority then oldest creation time
- `Todo` issue with non-terminal blockers is not eligible
- `Todo` issue with terminal blockers is eligible

### Requirement: Concurrency control
> Source: SPEC §8.3

The orchestrator SHALL enforce:
- Global limit: `max_concurrent_agents - running_count` available slots
- Per-state limit: `max_concurrent_agents_by_state[state]` when configured, falling back to global limit
- State keys are normalized (`lowercase`) for lookup

**Tests:**
- Global limit prevents dispatch when all slots full
- Per-state limit applies independently

### Requirement: Retry with exponential backoff
> Source: SPEC §8.4, §16.6

The orchestrator SHALL schedule retries with:
- Continuation retries (normal exit): fixed 1000ms delay
- Failure-driven retries: `min(10000 * 2^(attempt-1), max_retry_backoff_ms)`
- Retry entry creation cancels any existing timer for the same issue

On retry timer fire, the orchestrator SHALL:
1. Fetch active candidate issues
2. Find the specific issue by ID
3. If not found or no longer active, release claim
4. If eligible and slots available, dispatch
5. If eligible but no slots, requeue with error

**Tests:**
- Backoff formula produces correct delays for attempts 1-10
- Backoff cap is respected
- Retry timer fire dispatches eligible issue
- Retry timer fire releases claim for terminal issue
- Normal worker exit schedules a short continuation retry (attempt 1)
- Abnormal worker exit increments retries with 10s-based exponential backoff
- Retry backoff cap uses configured `agent.max_retry_backoff_ms`
- Retry queue entries include attempt, due time, identifier, and error
- Slot exhaustion requeues retries with explicit error reason

### Requirement: Active run reconciliation
> Source: SPEC §8.5, §16.3

The orchestrator SHALL reconcile running issues every tick:
- Stall detection: terminate worker if elapsed since last event exceeds `stall_timeout_ms`
- Tracker state refresh: fetch current states for all running issue IDs
- Terminal state: terminate worker and clean workspace
- Non-active state: terminate worker without workspace cleanup
- Refresh failure: keep workers running, retry next tick

**Tests:**
- Stalled session is terminated and retried
- Terminal tracker state stops worker and cleans workspace
- Non-active tracker state stops worker without cleanup
- Tracker refresh failure keeps workers running
- Reconciliation with no running issues is a no-op
- Active-state issue refresh updates running entry state

### Requirement: Startup terminal workspace cleanup
> Source: SPEC §8.6

On startup, the orchestrator SHALL:
1. Query tracker for issues in terminal states
2. Remove corresponding workspace directories
3. Log warning and continue if terminal fetch fails

**Tests:**
- Terminal workspaces are cleaned on startup
- Terminal fetch failure logs warning and continues

### Requirement: Dispatch preflight validation
> Source: SPEC §6.3

Before dispatching work, the orchestrator SHALL validate:
- Workflow file can be loaded and parsed
- `tracker.kind` is present and supported
- `tracker.api_key` is present after `$` resolution
- `tracker.project_slug` is present when REQUIRED by the selected tracker kind
- `agent.command` (or `codex.command`) is present and non-empty

Validation failures SHALL block new dispatches but keep reconciliation active.

**Tests:**
- Validation failure blocks dispatch
- Reconciliation continues even when validation fails

### Requirement: Idempotency and recovery
> Source: SPEC §7.4

The orchestrator SHALL serialize state mutations through one authority to avoid duplicate dispatch.
- `claimed` and `running` checks are REQUIRED before launching any worker
- Reconciliation runs before dispatch on every tick
- Restart recovery is tracker-driven and filesystem-driven (without a durable orchestrator DB)

**Tests:**
- State mutations are atomic (no partial updates visible)
- `claimed` check prevents duplicate dispatch
