## ADDED Requirements

### Requirement: LocalSandbox default implementation
> Source: SPEC §5.3.5, §10.1

The system SHALL implement `LocalSandbox`, a `SandboxManager` for `sandbox.kind == "local"`. It SHALL be the default sandbox when no `sandbox.kind` is configured.

The local sandbox SHALL use the host filesystem directly — the workspace path IS the sandbox.

#### Scenario: LocalSandbox is used by default
- **WHEN** `sandbox.kind` is `"local"` (or not set)
- **THEN** `LocalSandbox` SHALL be instantiated as the `SandboxManager`

### Requirement: LocalSandbox.provision() returns workspace path
> Source: SPEC §10.1

`LocalSandbox.provision(workspace_path)` SHALL:
1. Verify the workspace path exists as a directory
2. Return a `SandboxResult` with `sandbox_id = str(workspace_path)` and `effective_path = workspace_path`

#### Scenario: Provision returns workspace path as sandbox
- **WHEN** `provision()` is called with a valid workspace path
- **THEN** `SandboxResult.sandbox_id` SHALL equal the string representation of the workspace path
- **AND** `SandboxResult.effective_path` SHALL equal the workspace path

#### Scenario: Provision fails for missing workspace
- **WHEN** `provision()` is called with a non-existent workspace path
- **THEN** a `SandboxError` SHALL be raised

### Requirement: LocalSandbox.teardown() is a no-op
> Source: SPEC §3.1, §9.2

`LocalSandbox.teardown(sandbox_id)` SHALL be a no-op. Workspace cleanup is owned by `WorkspaceManager` (SPEC §9.2). The local sandbox has no separate resources to release.

#### Scenario: Teardown does nothing
- **WHEN** `teardown()` is called with any sandbox_id
- **THEN** it SHALL complete successfully without modifying any filesystem state

### Requirement: LocalSandbox.is_ready() always returns True
> Source: SPEC §5.3.5

`LocalSandbox.is_ready()` SHALL always return `True`. Since local execution has no external dependencies, the local sandbox is always available.

#### Scenario: Readiness check always succeeds
- **WHEN** `is_ready()` is called
- **THEN** it SHALL return `True`

### Requirement: LocalSandbox sandbox_id is stable
> Source: SPEC §9.2

For the local sandbox, `sandbox_id` SHALL be derived from the workspace path. The same workspace path SHALL produce the same `sandbox_id` across multiple `provision()` calls, enabling consistent observability and logging.

#### Scenario: Sandbox ID is deterministic for same workspace
- **WHEN** `provision()` is called twice with the same workspace path
- **THEN** both calls SHALL return the same `sandbox_id`