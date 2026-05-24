### Requirement: Runtime component composition
> Source: SPEC §16.1, §18.1

The runtime SHALL construct the concrete service graph from the resolved workflow configuration:

1. `Tracker` implementation
2. `WorkspaceManager`
3. `PromptBuilder`
4. `AgentRunner` implementation
5. `Orchestrator`

The initial supported concrete graph SHALL be:

- `tracker.kind == "linear"` -> `LinearTracker`
- `agent.kind == "codex"` -> `CodexAgentRunner`
- `sandbox.kind == "local"` -> local execution path

Unsupported component kinds SHALL fail startup with operator-visible errors before the poll loop is
started.

**Tests:**
- Runtime factory builds an orchestrator with Linear, workspace manager, prompt builder, and Codex
  runner for supported config
- Unsupported tracker kind fails startup before service tasks are started
- Unsupported agent kind fails startup before service tasks are started
- Unsupported sandbox kind fails startup before service tasks are started

### Requirement: CLI runtime overrides
> Source: SPEC §17.7

The `maestro run` command SHALL apply these CLI overrides to the effective runtime configuration
before validation and component construction:

- `--tracker-kind` overrides `tracker.kind`
- `--agent-kind` overrides `agent.kind`
- `--sandbox-kind` overrides `sandbox.kind`
- `--port` overrides `server.port`

Validation SHALL evaluate the effective configuration after overrides.

**Tests:**
- CLI `--port` overrides `server.port`
- CLI `--tracker-kind` changes the tracker kind used by validation/factory construction
- CLI `--agent-kind` changes the agent kind used by validation/factory construction
- CLI `--sandbox-kind` changes the sandbox kind used by validation/factory construction
- Overrides are ignored for `--dry-run` only in the sense that no service tasks are started; validation
  still uses the effective overridden config

### Requirement: Service startup
> Source: SPEC §6.3, §16.1, §17.7

When `maestro run` is invoked without `--dry-run`, the CLI SHALL:

1. Load and resolve `WORKFLOW.md`
2. Apply CLI overrides
3. Run startup validation
4. Construct runtime components
5. Perform orchestrator startup
6. Start the poll loop
7. Keep the process alive until shutdown is requested or a fatal runtime task fails

If startup validation or component construction fails, the CLI SHALL exit nonzero and print a clear
operator-visible error.

**Tests:**
- `maestro run --dry-run` validates and exits without constructing runtime components
- `maestro run` constructs runtime components and starts orchestrator
- Invalid startup config exits nonzero before starting orchestrator
- Component construction failure exits nonzero with a clear message

### Requirement: Optional HTTP server co-run
> Source: SPEC §13.7, §18.2

When the effective runtime configuration has an HTTP port from CLI `--port` or `server.port`, the
runtime SHALL start the HTTP server alongside the orchestrator.

The HTTP server SHALL:

- Bind loopback by default
- Use the real `orchestrator.state` for API/dashboard responses
- Be supervised as part of the same runtime lifecycle
- Shut down when the orchestrator shuts down or the host receives a shutdown signal

When no port is configured, no HTTP server SHALL be started.

**Tests:**
- Runtime starts HTTP server when CLI `--port` is provided
- Runtime starts HTTP server when `server.port` is configured
- Runtime does not start HTTP server when no port is configured
- HTTP API reads the same state object owned by the orchestrator
- HTTP server task is cancelled/stopped during runtime shutdown

### Requirement: HTTP refresh integration
> Source: SPEC §13.7.2, §16.2

`POST /api/v1/refresh` SHALL trigger a best-effort immediate poll-and-reconciliation cycle for the
running orchestrator.

Repeated refresh requests MAY be coalesced. The endpoint SHALL preserve the existing response shape:

- `queued`
- `coalesced`
- `requested_at`
- `operations`

**Tests:**
- Calling `/api/v1/refresh` schedules an orchestrator refresh callback
- Repeated refresh calls while a prior refresh is pending return `coalesced: true`
- Refresh endpoint still returns `202 Accepted`

### Requirement: Graceful shutdown
> Source: SPEC §17.7

The runtime host SHALL support graceful shutdown on SIGTERM/SIGINT.

On shutdown, the runtime SHALL:

1. Stop the orchestrator
2. Stop or cancel the optional HTTP server
3. Await task cleanup
4. Exit successfully for normal shutdown

If a managed task exits abnormally, the runtime SHALL stop sibling tasks and surface a nonzero CLI
exit.

**Tests:**
- SIGTERM/SIGINT path calls orchestrator stop
- Normal shutdown exits successfully
- Abnormal orchestrator task failure stops HTTP server and exits nonzero
- Abnormal HTTP server task failure stops orchestrator and exits nonzero