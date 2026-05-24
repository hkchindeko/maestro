## ADDED Requirements

### Requirement: HTTP server enablement
> Source: SPEC §13.7

The HTTP server SHALL be enabled when either CLI `--port` is provided or `server.port` is present in `WORKFLOW.md` front matter.

CLI `--port` SHALL override `server.port` when both are present.

A `server.port` value of `0` SHALL request an ephemeral port for local development and tests.

The server SHALL bind loopback (`127.0.0.1`) by default unless explicitly configured otherwise.

The server SHALL be started as an `asyncio` task alongside the orchestrator event loop.

#### Scenario: Server starts from CLI --port
- **WHEN** `maestro run --port 8080` is invoked
- **THEN** the HTTP server starts on `127.0.0.1:8080`

#### Scenario: Server starts from workflow config
- **WHEN** `WORKFLOW.md` contains `server.port: 9090` and no `--port` is given
- **THEN** the HTTP server starts on `127.0.0.1:9090`

#### Scenario: CLI --port overrides workflow config
- **WHEN** `WORKFLOW.md` contains `server.port: 9090` and `--port 8080` is given
- **THEN** the HTTP server starts on `127.0.0.1:8080`

#### Scenario: Ephemeral port
- **WHEN** `server.port` is `0`
- **THEN** the HTTP server starts on an OS-assigned port on loopback

#### Scenario: No server without port config
- **WHEN** neither `--port` nor `server.port` is present
- **THEN** no HTTP server is started

### Requirement: Config model for server settings
> Source: SPEC §13.7

The configuration system SHALL support a `server` key with a `port` field (integer, optional).

This SHALL be modeled as a Pydantic v2 model consistent with existing config patterns.

#### Scenario: Server config with port
- **WHEN** `server.port` is `8080` in workflow config
- **THEN** the parsed config has `server.port == 8080`

#### Scenario: Server config without port
- **WHEN** no `server` key is present in workflow config
- **THEN** the parsed config has `server.port is None`

### Requirement: JSON REST API — state endpoint
> Source: SPEC §13.7.2

The server SHALL expose `GET /api/v1/state` returning the current system state.

The response SHALL include:
- `generated_at` (ISO 8601 timestamp)
- `counts.running` and `counts.retrying`
- `running` array with rows containing `issue_id`, `issue_identifier`, `state`, `session_id`, `turn_count`, `last_event`, `last_message`, `started_at`, `last_event_at`, `tokens`
- `retrying` array with rows containing `issue_id`, `issue_identifier`, `attempt`, `due_at`, `error`
- `codex_totals` with `input_tokens`, `output_tokens`, `total_tokens`, `seconds_running`
- `rate_limits` (latest rate-limit payload or null)

#### Scenario: State endpoint returns running sessions
- **WHEN** `GET /api/v1/state` is called while 2 sessions are running
- **THEN** response has `counts.running: 2` and 2 entries in `running` array

#### Scenario: State endpoint returns retry queue
- **WHEN** `GET /api/v1/state` is called while 1 issue is in retry queue
- **THEN** response has `counts.retrying: 1` and 1 entry in `retrying` array

#### Scenario: State endpoint with no activity
- **WHEN** `GET /api/v1/state` is called with no running sessions and empty retry queue
- **THEN** response has `counts.running: 0`, `counts.retrying: 0`, empty arrays, and `codex_totals`

### Requirement: JSON REST API — per-issue endpoint
> Source: SPEC §13.7.2

The server SHALL expose `GET /api/v1/<issue_identifier>` returning issue-specific debug details.

The response SHALL include:
- `issue_identifier`, `issue_id`, `status`
- `workspace.path` (if available)
- `attempts` with `restart_count` and `current_retry_attempt`
- `running` section (if the issue is actively running)
- `retry` section (if the issue is in retry queue)
- `recent_events` array
- `last_error` (or null)

#### Scenario: Issue endpoint for running issue
- **WHEN** `GET /api/v1/MT-649` is called and MT-649 is running
- **THEN** response has `status: "running"` and populated `running` section

#### Scenario: Issue endpoint for retrying issue
- **WHEN** `GET /api/v1/MT-650` is called and MT-650 is in retry queue
- **THEN** response has `status: "retrying"` and populated `retry` section

#### Scenario: Issue endpoint for unknown issue
- **WHEN** `GET /api/v1/UNKNOWN-999` is called and the issue is not in state
- **THEN** response is `404` with `{"error": {"code": "issue_not_found", "message": "..."}}`

### Requirement: JSON REST API — refresh endpoint
> Source: SPEC §13.7.2

The server SHALL expose `POST /api/v1/refresh` as a best-effort trigger for poll-and-reconciliation.

The endpoint SHALL accept an empty body or `{}`.

The response SHALL be `202 Accepted` with `queued`, `coalesced`, `requested_at`, and `operations` fields.

Repeated requests MAY be coalesced.

#### Scenario: Refresh triggers poll cycle
- **WHEN** `POST /api/v1/refresh` is called
- **THEN** response is `202` with `{"queued": true, "operations": ["poll", "reconcile"]}`

#### Scenario: Coalesced refresh
- **WHEN** `POST /api/v1/refresh` is called while a previous refresh is still pending
- **THEN** response is `202` with `{"queued": true, "coalesced": true, ...}`

### Requirement: HTTP API error handling
> Source: SPEC §13.7.2

Unsupported HTTP methods on defined routes SHALL return `405 Method Not Allowed`.

API errors SHALL use a JSON envelope: `{"error": {"code": "<code>", "message": "<message>"}}`.

#### Scenario: Method not allowed
- **WHEN** `POST /api/v1/state` is called
- **THEN** response is `405` with error envelope

#### Scenario: Error envelope format
- **WHEN** any API error occurs
- **THEN** response body has `error.code` and `error.message` fields

### Requirement: Human-readable dashboard
> Source: SPEC §13.7.1

The server SHALL host a human-readable dashboard at `/`.

The dashboard SHALL depict current system state including active sessions, retry delays, token consumption, runtime totals, and health indicators.

The dashboard SHALL be server-rendered HTML using Jinja2 templates.

The dashboard page SHALL include a manual refresh link/button that triggers `/api/v1/refresh`.

#### Scenario: Dashboard shows running sessions
- **WHEN** `/` is loaded in a browser while sessions are running
- **THEN** the page shows session identifiers, turn counts, and token usage

#### Scenario: Dashboard shows empty state
- **WHEN** `/` is loaded with no running sessions
- **THEN** the page shows "No active sessions" or equivalent empty state

#### Scenario: Dashboard includes refresh button
- **WHEN** `/` is loaded
- **THEN** the page includes a button or link to trigger a refresh cycle