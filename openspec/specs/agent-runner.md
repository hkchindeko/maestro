## ADDED Requirements

### Requirement: Agent runner protocol
> Source: SPEC §10.7

The `AgentRunner` SHALL wrap workspace + prompt + app-server client with these behaviors:
1. Create/reuse workspace for issue
2. Build prompt from workflow template
3. Start app-server session
4. Forward app-server events to orchestrator
5. On any error, fail the worker attempt (the orchestrator will retry)

The `AgentRunner` interface SHALL be defined as an abstract base class so that multiple agent kinds (Codex, Claude Code, Copilot CLI) can be implemented.

**Tests:**
- `AgentRunner` ABC defines `start_session`, `run_turn`, `stop_session` methods
- Concrete implementations can be substituted via the protocol

### Requirement: Codex app-server launch
> Source: SPEC §10.1

For `agent.kind == "codex"`, the agent runner SHALL:
- Launch the command via `bash -lc <agent.command>` in the workspace directory
- Use stdio transport for JSON-RPC communication
- Set max line size to 10 MB for safe buffering

**Tests:**
- Launch command uses workspace cwd and invokes `bash -lc <codex.command>`
- Stdio transport framing is handled correctly

### Requirement: Session startup
> Source: SPEC §10.2

The agent runner SHALL:
- Start the agent subprocess in the per-issue workspace
- Initialize the agent session using the targeted protocol
- Create or resume a coding-agent thread
- Supply the absolute per-issue workspace path as the thread/turn working directory
- Start the first turn with the rendered issue prompt
- Include issue-identifying metadata in session/turn titles
- Advertise implemented client-side tools using the targeted protocol

Session identifiers SHALL be composed as:
- `session_id = "<thread_id>-<turn_id>"`
- Reuse the same `thread_id` for all continuation turns inside one worker run

**Tests:**
- Session startup follows the targeted Codex app-server protocol
- Thread and turn identities are extracted and used to emit `session_started`
- Client identity/capability payloads are valid when required

### Requirement: Streaming turn processing
> Source: SPEC §10.3

The agent runner SHALL process app-server updates until the active turn terminates.

Completion conditions:
- Targeted-protocol turn completion signal → success
- Targeted-protocol turn failure signal → failure
- Targeted-protocol turn cancellation signal → failure
- Turn timeout → failure
- Subprocess exit → failure

Continuation processing:
- If the worker decides to continue after a successful turn, it SHALL start another turn on the same live thread
- The app-server subprocess SHALL remain alive across continuation turns

**Tests:**
- Turn timeout is enforced
- Transport framing required by the targeted protocol is handled correctly
- For stdio-based transports, diagnostic stderr handling is kept separate from the protocol stream

### Requirement: Emitted runtime events
> Source: SPEC §10.4

The app-server client SHALL emit structured events to the orchestrator callback. Each event SHALL include:
- `event` (enum/string)
- `timestamp` (UTC timestamp)
- `codex_app_server_pid` (if available)
- OPTIONAL `usage` map (token counts)

Important emitted events include:
- `session_started`, `startup_failed`
- `turn_completed`, `turn_failed`, `turn_cancelled`, `turn_ended_with_error`
- `turn_input_required`, `approval_auto_approved`
- `unsupported_tool_call`, `notification`, `other_message`, `malformed`

**Tests:**
- Usage and rate-limit telemetry exposed by the targeted protocol is extracted
- Approval, user-input-required, usage, and rate-limit signals are interpreted

### Requirement: Approval and user input policy
> Source: SPEC §10.5

Each implementation MUST document its chosen approval, sandbox, and operator-confirmation posture.

For high-trust environments:
- Auto-approve command execution approvals for the session
- Auto-approve file-change approvals for the session
- Treat user-input-required turns as hard failure

Unsupported dynamic tool calls:
- If the agent requests a dynamic tool call that is not supported, return a tool failure response and continue the session
- This prevents the session from stalling on unsupported tool execution paths

**Tests:**
- Command/file-change approvals are handled according to the implementation's documented policy
- Unsupported dynamic tool calls are rejected without stalling the session
- User input requests are handled according to the implementation's documented policy and do not stall indefinitely

### Requirement: Timeouts and error mapping
> Source: SPEC §10.6

The agent runner SHALL enforce these timeouts:
- `codex.read_timeout_ms`: request/response timeout during startup and sync requests
- `codex.turn_timeout_ms`: total turn stream timeout
- `codex.stall_timeout_ms`: enforced by orchestrator based on event inactivity

Error mapping (RECOMMENDED normalized categories):
- `codex_not_found`, `invalid_workspace_cwd`, `response_timeout`
- `turn_timeout`, `port_exit`, `response_error`
- `turn_failed`, `turn_cancelled`, `turn_input_required`

**Tests:**
- Request/response read timeout is enforced
- Turn timeout is enforced

### Requirement: Agent runner contract
> Source: SPEC §10.7

The agent runner SHALL:
1. Create/reuse workspace for issue
2. Build prompt from workflow template
3. Start app-server session
4. Forward app-server events to orchestrator
5. On any error, fail the worker attempt (the orchestrator will retry)

Workspaces SHALL be intentionally preserved after successful runs.

**Tests:**
- Workspaces are preserved after successful runs
- Agent runner forwards events to orchestrator callback
