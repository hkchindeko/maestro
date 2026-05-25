# sandbox-protocol Specification

## Purpose
TBD - created by archiving change sandbox-manager. Update Purpose after archive.
## Requirements
### Requirement: SandboxManager abstract protocol
> Source: SPEC §3.1, §3.2, §10.1, §10.2

The system SHALL define a `SandboxManager` abstract base class with the following async methods:
- `provision(workspace_path: Path) -> SandboxResult` — provision a sandbox environment for the given workspace path
- `teardown(sandbox_id: str) -> None` — tear down a previously provisioned sandbox
- `is_ready() -> bool` — synchronous pre-flight check that the sandbox backend is available

The protocol SHALL be extensible for different sandbox backends (local, Docker, Daytona, E2B, Modal, etc.).

#### Scenario: Protocol defines required interface
- **WHEN** a concrete `SandboxManager` subclass is created
- **THEN** it MUST implement `provision()`, `teardown()`, and `is_ready()` methods

#### Scenario: Protocol supports async provisioning
- **WHEN** `provision()` is called
- **THEN** it SHALL be an async method returning a `SandboxResult`

### Requirement: SandboxResult carries sandbox identity and path
> Source: SPEC §10.1, §10.2

The system SHALL define a `SandboxResult` dataclass with:
- `sandbox_id` (str) — unique identifier for the provisioned sandbox, used for teardown and observability
- `effective_path` (Path) — the path where the agent subprocess should be launched (for local sandbox, this equals the workspace path)

#### Scenario: SandboxResult stores sandbox identity
- **WHEN** a sandbox is provisioned successfully
- **THEN** the returned `SandboxResult` SHALL contain a non-empty `sandbox_id`

#### Scenario: SandboxResult stores effective launch path
- **WHEN** a sandbox is provisioned for a given workspace path
- **THEN** the returned `SandboxResult` SHALL contain an absolute `effective_path`

### Requirement: SandboxManager integration into AgentRunner.start_session()
> Source: SPEC §10.2

The `AgentRunner.start_session()` method SHALL:
1. Provision the sandbox environment if `sandbox.kind` != `local`
2. Use the sandbox `effective_path` as the agent subprocess working directory
3. Return the `sandbox_id` as part of the session metadata

For `sandbox.kind == "local"`, provisioning is optional — the workspace path itself is the sandbox.

#### Scenario: Agent runner provisions sandbox before launch
- **WHEN** `start_session()` is called with a non-local sandbox manager
- **THEN** the sandbox SHALL be provisioned before the agent subprocess is launched

#### Scenario: Agent runner uses sandbox effective_path as cwd
- **WHEN** the agent subprocess is launched
- **THEN** its working directory SHALL be the sandbox `effective_path`

### Requirement: SandboxManager passed through Orchestrator to AgentRunner
> Source: SPEC §7, §10.2, §16

The `Orchestrator` SHALL accept a `SandboxManager` in its constructor and pass it to the `AgentRunner`.

The `SandboxManager` SHALL be created from `SandboxConfig` (SPEC §5.3.5) based on `sandbox.kind`.

#### Scenario: Orchestrator creates sandbox manager from config
- **WHEN** the orchestrator is initialized
- **THEN** it SHALL create a `SandboxManager` instance matching the configured `sandbox.kind`

#### Scenario: Orchestrator passes sandbox manager to agent runner
- **WHEN** the agent runner is constructed
- **THEN** it SHALL receive the `SandboxManager` instance from the orchestrator

### Requirement: SandboxManager teardown after session ends
> Source: SPEC §3.1, §10.2

The system SHALL tear down the sandbox when the agent session ends (success, failure, or cancellation). Teardown MUST be best-effort — failures SHALL be logged but MUST NOT prevent session cleanup or workspace teardown from proceeding.

#### Scenario: Sandbox torn down after successful session
- **WHEN** an agent session completes successfully
- **THEN** the sandbox SHALL be torn down via `teardown(sandbox_id)`

#### Scenario: Sandbox torn down after failed session
- **WHEN** an agent session fails
- **THEN** the sandbox SHALL be torn down via `teardown(sandbox_id)` as a best-effort operation

#### Scenario: Teardown failure does not block cleanup
- **WHEN** `teardown()` raises an exception
- **THEN** the error SHALL be logged and session cleanup SHALL proceed

