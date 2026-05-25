## MODIFIED Requirements

### Requirement: Orchestrator stop cancels workers
> Source: SPEC §7, §16.1

When the orchestrator shuts down, `stop()` SHALL cancel all active worker tasks in addition to the poll loop.

Worker cancellation SHALL:
1. Iterate all running entries and cancel each `worker_task`
2. Wait for worker tasks to complete with a timeout (default 5 seconds)
3. Log any workers that don't shut down within the timeout

Worker shutdown SHALL be best-effort — workers that time out SHALL NOT block orchestrator shutdown.

#### Scenario: Stop cancels all workers
- **WHEN** `Orchestrator.stop()` is called with 3 active workers
- **THEN** all 3 worker tasks SHALL be cancelled
- **AND** the method SHALL wait for all tasks to complete (or timeout)

#### Scenario: Worker timeout does not block shutdown
- **WHEN** a worker task does not complete within the 5-second timeout
- **THEN** the timeout SHALL be logged as a warning
- **AND** orchestrator shutdown SHALL proceed

### Requirement: Supported tracker validation matches implementation
> Source: SPEC §6.3

Dispatch preflight validation SHALL only accept tracker kinds that have actual implementations. For the current implementation, `SUPPORTED_TRACKER_KINDS` SHALL be `{"linear"}`.

Removing unvalidated entries (`jira`, `github`) SHALL NOT break existing configurations since building those trackers raises `RuntimeCompositionError`.

#### Scenario: Linear passes validation
- **WHEN** `tracker.kind` is `"linear"`
- **THEN** dispatch validation SHALL pass (provided other checks pass)

#### Scenario: Unimplemented tracker fails validation
- **WHEN** `tracker.kind` is `"jira"` or `"github"`
- **THEN** dispatch validation SHALL fail with `unsupported_tracker_kind`