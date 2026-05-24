## 1. Runtime Factory

- [x] 1.1 Add `src/maestro/runtime.py` with a `RuntimeComponents` dataclass containing tracker, workspace manager, prompt builder, agent runner, orchestrator, config, and workflow definition
- [x] 1.2 Implement `apply_cli_overrides(config, tracker_kind, agent_kind, sandbox_kind, port)` before validation
- [x] 1.3 Implement `build_tracker(config)` supporting `tracker.kind == "linear"` and failing clearly for unsupported kinds
- [x] 1.4 Implement `build_agent_runner(config)` supporting `agent.kind == "codex"` with `agent.command` or `codex.command`
- [x] 1.5 Implement `build_workspace_manager(config)` using resolved/default workspace root and hooks config
- [x] 1.6 Implement `build_orchestrator(definition, config)` wiring `LinearTracker`, `WorkspaceManager`, `PromptBuilder`, and `CodexAgentRunner`
- [x] 1.7 Write unit tests for factory construction and unsupported kind errors

## 2. Service Lifecycle

- [x] 2.1 Implement `run_runtime(definition, config, port)` that starts the orchestrator and optional HTTP server as asyncio tasks
- [x] 2.2 Supervise sibling tasks so unexpected failure in either orchestrator or HTTP server stops the other and surfaces an error
- [x] 2.3 Implement graceful shutdown helper that stops orchestrator, cancels server task, and drains task exceptions
- [x] 2.4 Install SIGTERM/SIGINT handlers where the event loop supports them
- [x] 2.5 Write async unit tests for normal shutdown, orchestrator failure, and HTTP server failure

## 3. HTTP Integration

- [x] 3.1 Change HTTP app creation to accept an optional refresh callback in addition to `OrchestratorState`
- [x] 3.2 Wire `/api/v1/refresh` to schedule the callback and preserve existing `202 Accepted` response shape
- [x] 3.3 Use the real `orchestrator.state` for dashboard/API when HTTP server is enabled
- [x] 3.4 Preserve loopback bind and CLI `--port` override behavior
- [x] 3.5 Write tests proving `/refresh` invokes the callback and repeated refreshes are coalesced/best-effort

## 4. CLI Integration

- [x] 4.1 Update `maestro run` to use runtime composition after config resolution and validation
- [x] 4.2 Preserve `--dry-run` behavior as validation-only with no runtime construction
- [x] 4.3 Apply CLI overrides before validation and startup
- [x] 4.4 Return nonzero exit with clear messages for invalid config or unsupported runtime kinds
- [x] 4.5 Add CLI integration tests for dry run, no-port service startup path, port-enabled startup path, CLI override precedence, and unsupported kinds

## 5. End-to-End Smoke Coverage

- [x] 5.1 Add a smoke test using fake tracker/agent dependencies to verify one service tick can dispatch an issue through the composed runtime
- [x] 5.2 Add a smoke test that starts runtime with HTTP enabled and verifies `/api/v1/state` reads real orchestrator state
- [x] 5.3 Verify graceful shutdown leaves no pending asyncio tasks in tests

## 6. Verification

- [x] 6.1 Run `uv run pytest tests/ -v -W error`
- [x] 6.2 Run `uv run ruff check src/ tests/`
- [x] 6.3 Run `uv run mypy src/maestro`
