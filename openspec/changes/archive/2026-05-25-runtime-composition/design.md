## Context

The service has enough modules to run, but no single place owns composition:

```text
CLI -> load workflow -> resolve config -> apply CLI overrides -> validate
   -> build tracker/workspace/prompt/agent/orchestrator
   -> optionally build HTTP server with orchestrator.state
   -> run until SIGTERM/SIGINT
```

Key SPEC sections:

- §6.1: Configuration resolution pipeline
- §6.3: Startup and per-tick dispatch validation
- §13.7: Optional HTTP server extension
- §16.1: Service startup
- §17.7: CLI and host lifecycle
- §18.1: Required conformance checklist
- §18.2: Recommended HTTP extension behavior

## Decisions

### Decision 1: Add a small `maestro.runtime` composition module

**Why:** CLI should stay thin. Runtime construction is application logic that will also be useful
for integration tests and future host surfaces. A dedicated module keeps object creation,
kind-dispatch, and task lifecycle out of Typer command handlers.

**Alternatives considered:**
- Put all construction in `src/maestro/cli/main.py` — fast, but makes CLI hard to test and mixes
  host concerns with runtime concerns
- Put construction on `Orchestrator` — wrong ownership; orchestrator should coordinate after
  dependencies are supplied, not decide which concrete implementations exist

### Decision 2: Support only implemented component kinds in this change

**Why:** The currently implemented concrete runtime is Linear + Codex + local execution. The CLI
has `--tracker-kind`, `--agent-kind`, and `--sandbox-kind`, but unsupported values should fail
clearly rather than pretend to work.

Supported initially:

| Component | Supported kind | Concrete type |
|-----------|----------------|---------------|
| tracker | `linear` | `LinearTracker` |
| agent | `codex` | `CodexAgentRunner` |
| sandbox | `local` | no-op/local execution path |

**Alternatives considered:**
- Leave validation permissive for future kinds — confusing because startup succeeds until a factory
  crashes later
- Implement GitHub/Internal trackers or Docker/Claude/Copilot here — too broad; those deserve their
  own OpenSpec changes

### Decision 3: Apply CLI overrides before validation and factory construction

**Why:** SPEC §17.7 defines CLI flags as runtime overrides. Validation must evaluate the effective
configuration that will actually run.

**Alternatives considered:**
- Validate workflow first, then apply overrides — rejects valid CLI override use cases
- Mutate raw YAML before resolution — harder to reason about and bypasses typed config behavior

### Decision 4: Run orchestrator and HTTP server as sibling asyncio tasks

**Why:** The orchestrator and HTTP server are long-running async services. Running them as sibling
tasks lets either one fail visibly and lets shutdown cancel both in a controlled way.

**Alternatives considered:**
- HTTP server owns orchestrator lifecycle — couples optional dashboard to required runtime
- Orchestrator owns HTTP server lifecycle — makes an optional extension part of core coordination
- Threading — unnecessary; both surfaces are async

### Decision 5: HTTP `/refresh` calls a runtime-supplied refresh callback

**Why:** The dashboard should not reach into private orchestrator internals by global state. The app
can store a callable on `app.state` that schedules an immediate tick/reconcile request. Tests can
replace it with a fake.

**Alternatives considered:**
- Store an `asyncio.Event` only — current behavior leaves no orchestrator consumer
- Directly call private `_on_tick()` from route handlers — tightly couples HTTP routes to
  orchestrator implementation details

### Decision 6: Signal handling is installed in the runtime host layer

**Why:** SIGTERM/SIGINT are process concerns, not orchestrator business logic. The runtime host can
translate signals into `stop()` calls and task cancellation while keeping orchestration code focused.

**Alternatives considered:**
- Handle signals inside `Orchestrator.start()` — harder to reuse orchestrator in tests
- Depend on Typer/Click signal behavior — not enough for multi-task async shutdown

## Non-Decisions

- No durable state store for retries or sessions; restart recovery remains tracker/filesystem driven
- No hot-rebind for HTTP port changes during dynamic reload
- No Docker or remote sandbox lifecycle
- No tracker write APIs
- No TUI or team/board mode

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Startup path becomes hard to test | Medium | Keep construction in pure factory functions; test with temp configs and fakes |
| HTTP server task hides orchestrator failures | High | Use sibling task supervision: if one task fails unexpectedly, stop the other and surface nonzero exit |
| Refresh trigger races with poll loop | Medium | Coalesce refresh requests and schedule a best-effort tick through orchestrator-safe method |
| Unsupported CLI overrides confuse users | Medium | Fail early with explicit `unsupported_*_kind` messages |
| Signal handling differs by platform | Low | Use asyncio signal handlers where available; fall back to KeyboardInterrupt/cancellation handling |
