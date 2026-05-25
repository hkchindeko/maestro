## MODIFIED Requirements

### Requirement: Refresh endpoint reports wiring status
> Source: SPEC §13.7.2

The POST `/api/v1/refresh` endpoint SHALL report whether a refresh was actually queued. If no refresh callback is configured (`refresh_callback is None`), the response SHALL include `queued: false` and a `reason` field indicating no callback is wired.

#### Scenario: Refresh with callback wired
- **WHEN** POST `/api/v1/refresh` is called and a refresh callback is configured
- **THEN** the response SHALL include `queued: true`

#### Scenario: Refresh with no callback wired
- **WHEN** POST `/api/v1/refresh` is called and no refresh callback is configured
- **THEN** the response SHALL include `queued: false` and `reason: "no_callback_configured"`

### Requirement: Per-issue detail includes workspace path
> Source: SPEC §13.7.2

The GET `/api/v1/<issue_identifier>` endpoint SHALL include the actual workspace path for running issues. The web layer SHALL receive a `WorkspaceManager` reference to compute workspace paths.

For running issues, `workspace.path` SHALL be the absolute workspace directory path. For retrying issues where no workspace is active, `workspace.path` MAY be `None`.

#### Scenario: Running issue includes workspace path
- **WHEN** GET `/api/v1/<issue_identifier>` is called for a running issue
- **THEN** the response SHALL include `workspace.path` set to the absolute workspace directory

#### Scenario: Retrying issue may omit workspace path
- **WHEN** GET `/api/v1/<issue_identifier>` is called for a retrying issue
- **THEN** `workspace.path` MAY be `null` if no active workspace exists