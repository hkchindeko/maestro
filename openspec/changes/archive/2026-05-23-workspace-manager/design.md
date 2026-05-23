## Context

The workspace manager handles per-issue workspace directories, lifecycle hooks, and path safety. SPEC §9 defines the exact requirements for workspace layout, creation, hooks, and safety invariants.

Key SPEC sections:
- §9.1: Workspace layout (workspace root, per-issue paths, reuse across runs)
- §9.2: Workspace creation and reuse (sanitize identifier, create directory, run after_create hook)
- §9.4: Workspace hooks (after_create, before_run, after_run, before_remove with timeout)
- §9.5: Safety invariants (cwd == workspace_path, workspace_path under workspace_root, sanitized keys)

## Decisions

### Decision 1: WorkspaceManager as a sync class

**Why:** Workspace operations (directory creation, path checks, hook execution) are primarily filesystem and subprocess operations. While subprocess execution can be async, the filesystem operations are fast and sync is simpler. The orchestrator can call these from an async context using `asyncio.to_thread` if needed.

**Alternatives considered:**
- Async WorkspaceManager — adds complexity for minimal benefit (filesystem ops are fast)
- Mix of sync/async — inconsistent API, harder to reason about

### Decision 2: `subprocess.run` with timeout for hooks

**Why:** SPEC §9.4 requires hook execution with timeout enforcement. `subprocess.run` with `timeout` parameter provides clean timeout handling with `TimeoutExpired` exception. Hooks run with `cwd` set to the workspace directory per spec.

**Alternatives considered:**
- `asyncio.create_subprocess_exec` — more complex, not needed for sync hooks
- `os.system` — no timeout support, no output capture

### Decision 3: Path safety as pure functions

**Why:** SPEC §9.5 defines three safety invariants that must be checked before agent launch. Implementing these as pure functions (`sanitize_key()`, `is_path_under_root()`) makes them easily testable and reusable.

**Alternatives considered:**
- Path safety as methods on WorkspaceManager — harder to test independently
- Path validation at config load time — too early, workspace path is computed per-issue

### Decision 4: Hook failure semantics per SPEC §9.4

**Why:** SPEC §9.4 defines different failure behaviors for each hook:
- `after_create` failure → fatal to workspace creation
- `before_run` failure → fatal to current run attempt
- `after_run` failure → logged and ignored
- `before_remove` failure → logged and ignored

The `WorkspaceManager` methods will raise exceptions for fatal hooks and log+return for non-fatal hooks.

**Alternatives considered:**
- All hooks raise exceptions — conflicts with spec's "logged and ignored" for after_run/before_remove
- All hooks return status codes — less Pythonic, harder to handle fatal cases

### Decision 5: Workspace reuse without destructive reset

**Why:** SPEC §9.2 states workspaces are reused across runs for the same issue. SPEC §9.3 states reused workspaces should NOT be destructively reset on population failure. The `create_for_issue` method checks if the directory exists and returns it without modification if it does.

## Non-Decisions

- **Workspace population/sync** — SPEC §9.3 says this is implementation-defined; handled via hooks, not built-in
- **Workspace compression/archival** — not required by spec; workspaces are preserved as-is
- **Concurrent workspace access** — single orchestrator, no concurrent access to same workspace

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hook script hangs without timeout | High | Timeout enforcement per SPEC §9.4, default 60s |
| Workspace path escape via symlink | Medium | Path containment check after resolution, not just string prefix |
| Disk space exhaustion from preserved workspaces | Low | Workspaces are per-issue, not per-run; operator can clean manually |
| Non-directory path at workspace location | Low | Handled safely: replace or fail per implementation policy |
