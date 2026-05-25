## Why

The SPEC §3.1 defines a **Sandbox Manager** as a first-class system component. It provisions and tears down AI sandbox environments (local, Docker, Daytona, E2B, Modal, etc.) for agent execution and enforces isolation and resource limits. The `workflow-config` change defines `SandboxConfig` (§5.3.5) with `kind`, `image`, `resources`, and `env` fields, and the `agent-runner` change requires sandbox provisioning during session startup (§10.2). Without a SandboxManager protocol and a local implementation, the agent runner cannot launch agents in any sandbox environment — even the simplest local case.

## What Changes

- Define `SandboxManager` abstract base class (protocol) with `provision()`, `teardown()`, `is_ready()` methods
- Implement `LocalSandbox` — no-op sandbox that uses the local filesystem directly (default `sandbox.kind`)
- Define typed result and error classes for sandbox operations
- Integrate `SandboxManager` into the `AgentRunner.start_session()` flow: provision sandbox before launching agent, teardown after session ends
- Extend `Orchestrator.__init__` to accept and pass `SandboxManager` to the agent runner
- Write unit tests for LocalSandbox lifecycle and protocol contract

## Capabilities

### New Capabilities

- `sandbox-protocol`: Abstract `SandboxManager` interface with provision/teardown lifecycle and sandbox metadata
- `local-sandbox`: No-op `LocalSandbox` implementation that uses local filesystem (default sandbox kind)

### Modified Capabilities

None — this is a new capability. No existing spec-level requirements change.

## Impact

- **New modules:**
  - `src/maestro/sandbox/base.py` — `SandboxManager` ABC, `SandboxInfo`, `SandboxResult`
  - `src/maestro/sandbox/local.py` — `LocalSandbox` implementation
- **Modified modules:**
  - `src/maestro/agent/base.py` — `AgentRunner.start_session()` accepts optional `SandboxManager`
  - `src/maestro/core/orchestrator.py` — constructor accepts and passes `SandboxManager`
  - `src/maestro/sandbox/__init__.py` — re-exports protocol and LocalSandbox
- **Depends on:** `workflow-config` (for `SandboxConfig`), `agent-runner` (for session startup flow)
- **No breaking changes**