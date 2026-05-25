## 1. Workspace Default Root in Config Model

- [ ] 1.1 Update `WorkspaceConfig.root` in `src/maestro/core/config.py` to default to `<tempdir>/symphony_workspaces` via `default_factory`
- [ ] 1.2 Simplify `build_workspace_manager()` in `src/maestro/runtime.py` to use `config.workspace.root` directly (no more None check and fallback)
- [ ] 1.3 Update tests in `tests/unit/test_config.py` (`TestWorkspaceConfig`) to verify the default value
- [ ] 1.4 Update tests in `tests/unit/test_runtime.py` to reflect simplified workspace builder

## 2. Tracker Validation Alignment

- [ ] 2.1 Change `SUPPORTED_TRACKER_KINDS` in `src/maestro/core/validation.py` from `{"linear", "jira", "github"}` to `{"linear"}`
- [ ] 2.2 Update tests in `tests/unit/test_validation.py` to verify jira/github fail validation
- [ ] 2.3 Remove `config.sandbox.kind` duplicate check from `build_components()` in `src/maestro/runtime.py` (already handled by `build_sandbox_manager()`)

## 3. HTTP Refresh Wiring Status

- [ ] 3.1 Update POST `/api/v1/refresh` handler in `src/maestro/web/routes.py` to check if `refresh_callback` is None and return `queued: false` with reason
- [ ] 3.2 Update tests in `tests/unit/test_web.py` (`TestRefreshEndpoint`) to verify None callback response

## 4. Workspace Path in API

- [ ] 4.1 Add `workspace_manager` parameter to `create_app()` in `src/maestro/web/app.py`
- [ ] 4.2 Store `workspace_manager` reference on `app.state`
- [ ] 4.3 Update `_build_issue_detail()` in `src/maestro/web/routes.py` to compute workspace path from `WorkspaceManager`
- [ ] 4.4 Update `_run_server()` in `src/maestro/runtime.py` to pass workspace manager to `create_app()` via `start_server_fn`
- [ ] 4.5 Update `start_server` signature in `src/maestro/web/app.py` to accept and pass `workspace_manager`
- [ ] 4.6 Update tests in `tests/unit/test_web.py` to verify workspace path in issue detail response

## 5. Clean Signal Shutdown

- [ ] 5.1 Update `Orchestrator.stop()` in `src/maestro/core/orchestrator.py` to cancel all worker tasks with timeout
- [ ] 5.2 Add worker shutdown timeout constant (5000ms)
- [ ] 5.3 Update `_run_worker()` in orchestrator to handle `CancelledError` and log worker cancellation
- [ ] 5.4 Update tests in `tests/unit/test_runtime.py` to verify workers are cancelled on shutdown

## 6. Final Verification

- [ ] 6.1 Run full test suite: `uv run pytest tests/ -v` and verify 100% pass
- [ ] 6.2 Run ruff linting on all modified files