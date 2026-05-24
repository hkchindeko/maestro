## 1. Structured logging

- [x] 1.1 Implement `create_issue_logger(issue_id, issue_identifier)` returning LoggerAdapter with context fields per SPEC §13.1
- [x] 1.2 Implement `create_session_logger(session_id)` returning LoggerAdapter with session_id context
- [x] 1.3 Implement log message formatting with `key=value` phrasing and action outcomes per SPEC §13.1
- [x] 1.4 Implement log sink failure handling (non-crashing) per SPEC §13.2
- [x] 1.5 Write unit tests for structured logging with context fields

## 2. Runtime snapshot

- [x] 2.1 Define `RunningSessionRow` dataclass matching SPEC §13.3 running row shape
- [x] 2.2 Define `RetryQueueRow` dataclass matching SPEC §13.3 retrying row shape
- [x] 2.3 Define `RuntimeSnapshot` dataclass with running, retrying, codex_totals, rate_limits
- [x] 2.4 Implement `SnapshotBuilder` to assemble snapshot from `OrchestratorState`
- [x] 2.5 Implement `to_dict()` method for JSON serialization
- [x] 2.6 Write unit tests for snapshot assembly

## 3. Token accounting utilities

- [x] 3.1 Implement `compute_token_delta(current_total, last_reported_total)` for delta tracking per SPEC §13.5
- [x] 3.2 Implement `extract_tokens_from_event(payload)` for lenient field extraction
- [x] 3.3 Implement `compute_live_runtime(started_at_entries, cumulative_seconds)` per SPEC §13.5
- [x] 3.4 Write unit tests for token delta tracking and live runtime

## 4. Rate-limit tracking

- [x] 4.1 Implement `update_rate_limits(current, new)` to track latest rate-limit payload
- [x] 4.2 Implement rate-limit presentation for snapshot output
- [x] 4.3 Write unit tests for rate-limit tracking

## 5. Humanized event summaries

- [x] 5.1 Implement `humanize_event(event_type, payload)` returning human-readable string per SPEC §13.6
- [x] 5.2 Cover key event classes: session_started, turn_completed, turn_failed, approval_auto_approved, notification
- [x] 5.3 Write unit tests for humanized summaries

## 6. Integration tests

- [x] 6.1 Test full snapshot assembly from mock orchestrator state
- [x] 6.2 Test snapshot with running sessions and retry queue
- [x] 6.3 Test token accounting integration with orchestrator state
- [x] 6.4 Test snapshot timeout/unavailable error modes per SPEC §13.3
