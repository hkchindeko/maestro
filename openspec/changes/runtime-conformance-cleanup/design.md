## Context

Five SPEC conformance gaps exist between the runtime implementation and the SPEC. These are small fixes that don't change architecture but correct behavior, observability, and safety.

## Goals / Non-Goals

**Goals:**
- Fix workspace default root to apply at config model level per SPEC §6.1
- Align tracker validation with what `build_tracker()` actually supports
- Surface HTTP refresh wiring status in API response
- Expose workspace paths in the HTTP API per-issue detail endpoint
- Cancel worker tasks on orchestrator shutdown for clean signal handling

**Non-Goals:**
- Implementing Jira or GitHub tracker support (just aligning validation)
- Full workspace path resolution for retrying issues (may not have active workspace)
- Exposing workspace path in the `/state` snapshot (just `/api/v1/<id>` for now)
- Adding new API endpoints

## Decisions

### Decision 1: Move workspace default root to config model

**Why:** SPEC §6.1 says "Apply built-in defaults for missing OPTIONAL fields" during config resolution, not at runtime builder time. `WorkspaceConfig.root` should default to `<system-temp>/symphony_workspaces` at the Pydantic model level, matching how other config fields apply defaults. This also simplifies `build_workspace_manager()`.

**Current:** `WorkspaceConfig.root` defaults to `None`, and `build_workspace_manager()` builds the path:
```python
root = Path(config.workspace.root) if config.workspace.root is not None else Path(tempfile.gettempdir()) / "symphony_workspaces"
```

**Target:** `WorkspaceConfig.root` defaults via `default_factory`:
```python
root: str = Field(default_factory=lambda: str(Path(tempfile.gettempdir()) / "symphony_workspaces"))
```

**Alternatives considered:**
- Keep None in config, apply in builder — keeps existing pattern but diverges from spec

### Decision 2: Restrict SUPPORTED_TRACKER_KINDS to {"linear"}

**Why:** `validation.py` declares `{"linear", "jira", "github"}` but only `linear` is implemented. Validation should reflect actual support to avoid misleading users. We remove `jira` and `github` from `SUPPORTED_TRACKER_KINDS` since they're aspirational, not implemented.

**Alternatives considered:**
- Keep jira/github in validation, add nicer error in `build_tracker()` — validation passes but building fails, worse UX
- Add NotImplementedError stubs for jira/github — unnecessary dead code

### Decision 3: Surface refresh callback wiring in API response

**Why:** The POST `/api/v1/refresh` response always returns `queued: true` even when no callback is configured. The API should report whether a refresh was actually triggered or if no callback is wired.

**Current:** Returns `{"queued": true, ...}` regardless.

**Target:** Check `refresh_callback is None` first, return `{"queued": false, "reason": "no_callback_configured", ...}`.

**Alternatives considered:**
- Return 501 Not Implemented when no callback — too aggressive, refresh is optional

### Decision 4: Inject WorkspaceManager into web layer

**Why:** The per-issue detail endpoint needs workspace paths. Currently returns `"workspace": {"path": None}`. The simplest approach is to pass the `WorkspaceManager` reference through `create_app()` and store it on `app.state`.

**Target:** Add `workspace_manager` parameter to `create_app()`, store on `app.state`, use `workspace_manager.path_for_issue(identifier)` in `_build_issue_detail()`.

**Alternatives considered:**
- Store workspace path on RunningEntry during dispatch — adds coupling to state model, path varies per deployment
- Compute from config root + sanitized identifier in routes — duplicates workspace manager logic

### Decision 5: Cancel worker tasks in Orchestrator.stop()

**Why:** When the orchestrator receives a shutdown signal, `stop()` cancels the poll loop but worker tasks (running agent subprocesses) continue. This can leave orphaned agent processes after Maestro exits. `stop()` needs to iterate running entries, cancel their worker tasks, and wait for them.

**Current:** Only cancels `_tick_task`.

**Target:** After cancelling tick, iterate `_state.running`, cancel each `entry.worker_task`, gather with timeout, then proceed.

**Alternatives considered:**
- Kill subprocesses directly from orchestrator — couples orchestrator to agent internals
- Rely on agent runner cleanup in worker task finally blocks — worker task cancellation may not run finally if cancelled

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Worker cancellation can leave agent subprocesses running | Medium | Cancellation triggers `CancelledError` in worker, which should hit cleanup in `_run_worker` finally. Add explicit timeout (5s) for worker shutdown. |
| Workspace default root differs across platforms | Low | Uses `tempfile.gettempdir()` like spec says `<system-temp>`. |
| Removing jira/github from validation surprises users | Low | They were never implemented; this clarifies actual support. |

## Open Questions

None — each fix is straightforward and well-scoped.