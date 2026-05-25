## Context

The SPEC §3.1 defines Sandbox Manager as a core system component responsible for provisioning and tearing down AI sandbox environments. The `workflow-config` change provides `SandboxConfig` (§5.3.5) with `kind` (default `local`), `image`, `resources`, and `env` fields. The `agent-runner` change requires sandbox provisioning during session startup (§10.2). This design covers the protocol, the `local` sandbox implementation, and integration into the existing agent runner and orchestrator flow.

Existing patterns in the codebase:
- `Tracker` ABC (`src/maestro/tracker/base.py`) — protocol-first design with async methods
- `AgentRunner` ABC (`src/maestro/agent/base.py`) — protocol-first, async, dataclass results
- `WorkspaceManager` (`src/maestro/workspace/manager.py`) — sync class with `WorkspaceResult` dataclass

## Goals / Non-Goals

**Goals:**
- Define `SandboxManager` ABC with `provision()`, `teardown()`, `is_ready()` methods
- Implement `LocalSandbox` as the default no-op sandbox for `sandbox.kind == "local"`
- Integrate sandbox provisioning into `AgentRunner.start_session()` flow
- Pass `SandboxManager` through `Orchestrator` to agent runner
- Keep the protocol extensible for future sandbox types (Docker, Daytona, E2B, etc.)

**Non-Goals:**
- Docker sandbox implementation
- Daytona, E2B, Modal, Blaxel, Runloop, Cloudflare, Vercel implementations
- Resource limit enforcement (local sandbox has no container isolation)
- Sandbox health monitoring or auto-recovery
- Multi-agent sandbox sharing

## Decisions

### Decision 1: Async SandboxManager protocol

**Why:** Sandbox provisioning can be I/O-bound — Docker container creation, Daytona session start, E2B API calls. Following the existing `AgentRunner` and `Tracker` patterns keeps the API surface consistent and avoids blocking the event loop.

**Alternatives considered:**
- Sync protocol — simpler but would block the event loop during container creation or API calls
- Hybrid (sync `is_ready` + async `provision`) — inconsistent, harder to reason about

### Decision 2: LocalSandbox as identity/no-op

**Why:** When `sandbox.kind == "local"`, there is no external sandbox — the agent runs directly on the host filesystem in the workspace directory. The sandbox is the workspace itself. `provision()` simply verifies the workspace path exists and returns a `SandboxResult` wrapping it. `teardown()` is a no-op because workspace cleanup is owned by `WorkspaceManager`.

**Alternatives considered:**
- LocalSandbox creates a temp directory — conflicts with workspace reuse semantics in SPEC §9.2
- LocalSandbox does nothing at all — agent runner still needs a sandbox result for cwd/path info

### Decision 3: SandboxResult carries sandbox_id and effective_path

**Why:** The agent runner needs to know where to launch the agent subprocess. For local sandbox, this is the workspace path. For Docker sandbox, this could be a bind mount path, a container ID, or a connection string. `SandboxResult` provides `sandbox_id` (for teardown/observability) and `effective_path` (where to run the agent — for local this equals workspace path).

**Alternatives considered:**
- Return just a path string — insufficient for non-local sandboxes that need an ID for teardown
- Return a dict — less type-safe, no IDE support

### Decision 4: SandboxManager injected via AgentRunner constructor, not start_session()

**Why:** The agent runner is configured once with a sandbox manager, and every session uses the same sandbox kind. Passing it at construction time (like how `Tracker` is passed to `Orchestrator`) is cleaner than threading it through every `start_session()` call. The Orchestrator creates the sandbox manager from config and passes it to the agent runner constructor.

**Alternatives considered:**
- Pass to `start_session()` — more flexible (different sandbox per session) but unnecessary for current requirements
- Agent runner creates its own sandbox — violates DI, harder to test

### Decision 5: SandboxConfig passed to SandboxManager constructor

**Why:** The sandbox manager needs `SandboxConfig` to know what kind of sandbox to provision and with what settings (image, resources, env). The factory/constructor pattern is: `Orchestrator` creates `SandboxManager` from config, passes it to `AgentRunner`. For `sandbox.kind == "local"`, `LocalSandbox` ignores most config fields.

**Alternatives considered:**
- SandboxManager reads config from a global — violates no-global-mutable-state convention
- Each `provision()` call takes config — repetitive, config doesn't change per-issue

### Decision 6: is_ready() as a pre-flight check

**Why:** Docker and other sandbox backends may require pre-installed tools (Docker daemon running, CLI available). `is_ready()` provides a synchronous pre-flight check that the orchestrator can call during startup validation. For `LocalSandbox`, this always returns `True`.

**Alternatives considered:**
- Check readiness in `provision()` — fails too late, after dispatch
- No readiness check — Docker failures manifest as opaque agent launch errors

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Local sandbox provides no isolation | Medium | Document trust posture; local is for high-trust environments only. Future Docker sandbox addresses this. |
| SandboxManager not yet integrated into startup validation | Low | `is_ready()` method exists on protocol for future validation use. Not called during dispatch preflight yet — can be added in a follow-up. |
| `effective_path` semantic overload for non-local sandboxes | Low | Protocol field is explicitly documented. Each implementation defines what `effective_path` means. |

## Open Questions

None — the design is straightforward for `local` sandbox. Docker and other sandbox implementations will raise new questions about container lifecycle, image pulling, and resource limits when they are built.