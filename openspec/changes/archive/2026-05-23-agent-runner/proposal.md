## Problem

SPEC §10 defines the agent runner protocol for integrating coding agents (Codex, Claude Code, Copilot CLI, etc.):

1. **Launch contract** — subprocess with command, cwd, transport per SPEC §10.1
2. **Session startup** — provision sandbox, start agent, create thread, supply prompt, advertise tools per SPEC §10.2
3. **Streaming turn processing** — process app-server updates until turn terminates, handle continuation per SPEC §10.3
4. **Emitted runtime events** — structured events upstream to orchestrator per SPEC §10.4
5. **Approval, tool calls, user input** — documented policy, no indefinite stalls per SPEC §10.5
6. **Timeouts and error mapping** — read, turn, stall timeouts; normalized error categories per SPEC §10.6
7. **Agent runner contract** — workspace + prompt + app-server client wrapper per SPEC §10.7

The `workflow-config`, `prompt-builder`, `tracker-linear`, and `workspace-manager` changes provide config loading, prompt rendering, tracker integration, and workspace management, but no agent runner implementation exists yet. This is the final foundational layer needed before the orchestrator can dispatch work.

## What Changes

- Define `AgentRunner` abstract base class with `start_session()`, `run_turn()`, `stop_session()`
- Implement `CodexAgentRunner` for Codex app-server stdio protocol
- Implement session startup with thread creation, prompt injection, tool advertisement
- Implement streaming turn processing with event emission to orchestrator callback
- Implement approval handling (auto-approve for high-trust), user-input-required handling (fail)
- Implement timeout enforcement (read, turn, stall)
- Implement token accounting and rate-limit tracking from agent events
- Implement typed error classes for agent session failures
- Write unit tests for session lifecycle, event streaming, timeout handling, and error mapping

## Capabilities

### New Capabilities

- `agent-runner-protocol`: Abstract `AgentRunner` interface with session/turn lifecycle
- `codex-app-server`: Codex app-server stdio protocol client with session management
- `event-streaming`: Structured events emitted to orchestrator callback
- `approval-policy`: Documented approval/user-input policy (high-trust: auto-approve, fail on input)
- `token-accounting`: Token counter extraction from agent events

### Modified Capabilities

None — this is a new capability.

## Impact

- **New modules:**
  - `src/maestro/agent/base.py` — `AgentRunner` ABC and session models
  - `src/maestro/agent/codex.py` — Codex app-server stdio client
  - `src/maestro/agent/events.py` — Event types and token accounting
- **Depends on:** `workflow-config` (for `AgentConfig`), `workspace-manager` (for workspace path), `prompt-builder` (for rendered prompt)
- **No breaking changes**
