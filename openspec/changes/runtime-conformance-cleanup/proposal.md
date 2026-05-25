## Why

The runtime implementation has several small but important gaps against the SPEC that affect correctness, observability, and shutdown behavior:

1. **Workspace default root**: SPEC §5.3.3 defines `<system-temp>/symphony_workspaces` as the default. `WorkspaceConfig.root` defaults to `None`, and the default is only applied in the runtime builder (`build_workspace_manager`), not in the config model itself per SPEC §6.1 ("Apply built-in defaults for missing OPTIONAL fields").

2. **Supported tracker validation mismatch**: `validation.py` declares `{"linear", "jira", "github"}` as supported, but `build_tracker()` in `runtime.py` only implements `linear`. Validation passes for `jira`/`github` but building fails with `RuntimeCompositionError`.

3. **HTTP refresh callback may be None**: The POST `/api/v1/refresh` endpoint calls the refresh callback but doesn't surface when it's `None` (not wired). The response always reports `queued: true` even if no callback is configured.

4. **Workspace path missing from API**: The per-issue detail endpoint (`GET /api/v1/<issue_identifier>`) returns `"workspace": {"path": None}` with a comment acknowledging the WorkspaceManager isn't available. The API cannot report actual workspace paths.

5. **Signal shutdown leaves worker tasks running**: `Orchestrator.stop()` cancels only the tick loop but not active worker tasks. On SIGTERM/SIGINT, worker tasks may continue running after the orchestrator shuts down, potentially leaving agent subprocesses orphaned.

## What Changes

- Apply workspace default root in `WorkspaceConfig` model per SPEC §6.1
- Align `build_tracker()` supported kinds with validation (restrict to `linear` only, or add `NotImplementedError` for declared-but-unbuilt kinds)
- Validate refresh callback is non-None before queuing, return clear status in API response
- Pass `WorkspaceManager` to the web layer so API can compute workspace paths for running issues
- Cancel all worker tasks in `Orchestrator.stop()` before shutdown completes

## Capabilities

### New Capabilities

None — these are conformance fixes to existing capabilities.

### Modified Capabilities

- `workspace-manager`: Workspace default root moves from runtime builder to config model
- `core-orchestrator`: Shutdown now cancels worker tasks; tracker validation aligns with implementation
- `http-dashboard`: Refresh endpoint reports wiring status; per-issue endpoint includes workspace path

## Impact

- **Modified modules:**
  - `src/maestro/core/config.py` — `WorkspaceConfig.root` default
  - `src/maestro/core/orchestrator.py` — `stop()` cancels workers
  - `src/maestro/runtime.py` — `build_tracker()` aligned with validation; `build_workspace_manager()` simplified
  - `src/maestro/core/validation.py` — optional: restrict `SUPPORTED_TRACKER_KINDS` to `{"linear"}`
  - `src/maestro/web/app.py` — accept `WorkspaceManager` reference
  - `src/maestro/web/routes.py` — refresh response, workspace path in issue detail
- **No breaking changes** — all changes are additive or fix incorrect behavior