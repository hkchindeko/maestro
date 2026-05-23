## Context

The agent runner wraps workspace + prompt + app-server client to execute coding agent sessions. SPEC §10 defines the protocol for launching agents, managing sessions, streaming turns, and handling events. The Codex app-server protocol is the primary implementation target.

Key SPEC sections:
- §10.1: Launch contract (command, cwd, transport)
- §10.2: Session startup (sandbox, thread, prompt, tools)
- §10.3: Streaming turn processing (completion conditions, continuation)
- §10.4: Emitted runtime events (event types, token counts)
- §10.5: Approval, tool calls, user input policy
- §10.6: Timeouts and error mapping
- §10.7: Agent runner contract (workspace + prompt + app-server)

## Decisions

### Decision 1: Async subprocess for app-server communication

**Why:** The Codex app-server communicates over stdio with JSON-RPC messages. Using `asyncio.create_subprocess_exec` allows non-blocking read/write of the protocol stream while the orchestrator handles other tasks (reconciliation, other agents).

**Alternatives considered:**
- Sync subprocess with threads — more complex synchronization
- HTTP-based app-server — spec says stdio for local execution

### Decision 2: JSON-RPC message framing over stdio

**Why:** The Codex app-server protocol uses JSON-RPC over stdio with newline-delimited JSON. Each message is a JSON object followed by a newline. The reader loops reading lines, parsing JSON, and dispatching to event handlers.

**Alternatives considered:**
- Custom binary framing — not supported by Codex app-server
- HTTP transport — spec says stdio for local

### Decision 3: Event callback pattern for orchestrator communication

**Why:** SPEC §10.4 defines events emitted upstream to the orchestrator. A callback pattern (`on_event(event)`) decouples the agent runner from the orchestrator, making both testable independently.

**Alternatives considered:**
- Shared state with locks — harder to test, more coupling
- Async queue — adds complexity, callback is sufficient for single consumer

### Decision 4: High-trust approval policy as default

**Why:** SPEC §10.5 states each implementation MUST document its approval policy. For a high-trust environment (the default posture), auto-approve command execution and file-change approvals, and fail on user-input-required. This matches the spec's example high-trust behavior.

**Alternatives considered:**
- Operator confirmation for all approvals — requires UI, out of scope for v1
- Configurable per-session policy — adds complexity, can be added later

### Decision 5: Token accounting from event payloads

**Why:** SPEC §13.5 defines token accounting rules: prefer absolute thread totals, track deltas, ignore delta-style payloads. The agent runner extracts token counts from agent events and accumulates them in the running entry.

**Alternatives considered:**
- Separate token accounting module — tightly coupled to agent events, better in agent runner
- No token accounting — required by spec for observability

## Non-Decisions

- **Multiple agent kinds in v1** — Codex is the primary target; Claude/Copilot stubs can be added later
- **Sandbox provisioning in agent runner** — handled by SandboxManager, agent runner receives the sandbox session
- **Dynamic tool call implementation** — only `linear_graphql` is standardized; others return failure per spec

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Codex app-server protocol changes | High | Isolate protocol handling, test against installed version |
| Stdio deadlock on large output | Medium | Max line size 10MB per spec, async read with buffer |
| Token count double-counting | Medium | Delta tracking from absolute totals per SPEC §13.5 |
| Stall detection false positives | Medium | Configurable stall timeout, default 5m per spec |
