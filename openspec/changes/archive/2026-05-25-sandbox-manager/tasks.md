## 1. Sandbox Protocol (ABC and Models)

- [x] 1.1 Create `src/maestro/sandbox/base.py` with `SandboxManager` ABC having `provision()`, `teardown()`, `is_ready()` abstract methods
- [x] 1.2 Define `SandboxResult` dataclass with `sandbox_id`, `effective_path` fields
- [x] 1.3 Define `SandboxError` exception class for sandbox operation failures
- [x] 1.4 Update `src/maestro/sandbox/__init__.py` to export protocol classes

## 2. LocalSandbox Implementation

- [x] 2.1 Create `src/maestro/sandbox/local.py` with `LocalSandbox` class implementing `SandboxManager`
- [x] 2.2 Implement `provision()` — verify workspace path exists, return `SandboxResult` with `sandbox_id = str(workspace_path)`, `effective_path = workspace_path`
- [x] 2.3 Implement `teardown()` — no-op (workspace cleanup owned by WorkspaceManager)
- [x] 2.4 Implement `is_ready()` — always returns `True`
- [x] 2.5 Update `src/maestro/sandbox/__init__.py` to export `LocalSandbox`

## 3. Agent Runner Integration

- [x] 3.1 Update `AgentRunner` ABC in `src/maestro/agent/base.py` to accept optional `SandboxManager` in constructor
- [x] 3.2 Update `AgentSession` dataclass to include `sandbox_id` field
- [x] 3.3 Update `AgentRunner.start_session()` docstring to document sandbox provisioning flow
- [x] 3.4 Update `CodexAgentRunner` in `src/maestro/agent/codex.py` to accept and use `SandboxManager`

## 4. Orchestrator Integration

- [x] 4.1 Update `Orchestrator.__init__()` to accept and store `SandboxManager`
- [x] 4.2 Create sandbox manager factory based on `SandboxConfig.kind` (return `LocalSandbox` for `"local"`, raise `NotImplementedError` for others)
- [x] 4.3 Pass `SandboxManager` to `AgentRunner` during orchestrator initialization in `runtime.py`

## 5. Unit Tests

- [x] 5.1 Create `tests/unit/test_sandbox.py` with test class structure
- [x] 5.2 Write tests for `SandboxManager` protocol — verify ABC cannot be instantiated, subclasses must implement all methods
- [x] 5.3 Write tests for `LocalSandbox.provision()` — valid workspace, missing workspace, deterministic sandbox_id
- [x] 5.4 Write tests for `LocalSandbox.teardown()` — no-op behavior, idempotency
- [x] 5.5 Write tests for `LocalSandbox.is_ready()` — always returns True
- [x] 5.6 Write tests for `SandboxResult` dataclass fields and types
- [x] 5.7 Run full test suite: `uv run pytest tests/ -v` and verify 100% pass