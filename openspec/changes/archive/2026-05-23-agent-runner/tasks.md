## 1. Agent runner protocol

- [x] 1.1 Define `AgentSession` dataclass with `session_id`, `thread_id`, `turn_id`, token counters
- [x] 1.2 Define `AgentEvent` dataclass with `event_type`, `timestamp`, `payload`, token usage
- [x] 1.3 Define `AgentRunner` ABC with `start_session()`, `run_turn()`, `stop_session()`
- [x] 1.4 Define `TurnResult` dataclass with success/failure status and error details
- [x] 1.5 Write unit tests for protocol types

## 2. Codex app-server client

- [x] 2.1 Implement `CodexAgentRunner` class with `asyncio.create_subprocess_exec`
- [x] 2.2 Implement `_launch(command: str, cwd: Path)` with `bash -lc` invocation
- [x] 2.3 Implement `_send_message(msg: dict)` for JSON-RPC request writing
- [x] 2.4 Implement `_read_messages()` async generator for newline-delimited JSON parsing
- [x] 2.5 Implement session startup: thread creation, prompt injection, tool advertisement
- [x] 2.6 Implement turn execution: send prompt, stream responses until turn completion
- [x] 2.7 Implement session cleanup on stop
- [x] 2.8 Write unit tests for launch, message framing, and session lifecycle

## 3. Event streaming and token accounting

- [x] 3.1 Implement event callback dispatch for orchestrator communication
- [x] 3.2 Implement token extraction from agent event payloads (absolute totals, delta tracking)
- [x] 3.3 Implement rate-limit payload extraction and tracking
- [x] 3.4 Implement session_id composition from thread_id and turn_id
- [x] 3.5 Write unit tests for event parsing and token accounting

## 4. Approval and user input policy

- [x] 4.1 Implement auto-approve for command execution approvals (high-trust policy)
- [x] 4.2 Implement auto-approve for file-change approvals (high-trust policy)
- [x] 4.3 Implement user-input-required handling as hard failure (high-trust policy)
- [x] 4.4 Implement unsupported tool call rejection without stalling
- [x] 4.5 Write unit tests for approval and input handling

## 5. Timeout and error handling

- [x] 5.1 Implement read timeout enforcement (`codex.read_timeout_ms`)
- [x] 5.2 Implement turn timeout enforcement (`codex.turn_timeout_ms`)
- [x] 5.3 Implement error mapping to normalized categories per SPEC §10.6
- [x] 5.4 Define `AgentSessionError` base exception class
- [x] 5.5 Define `AgentTimeoutError`, `AgentLaunchError`, `AgentProtocolError` subclasses
- [x] 5.6 Write unit tests for timeout and error handling

## 6. Integration tests

- [x] 6.1 Test full session lifecycle: start → turn → stop with mock app-server
- [x] 6.2 Test event streaming with mock app-server responses
- [x] 6.3 Test timeout handling with slow mock app-server
- [x] 6.4 Test approval auto-approval flow
- [x] 6.5 Test user-input-required failure flow
- [x] 6.6 Test token accounting with mock token events
