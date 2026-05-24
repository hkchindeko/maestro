## 1. Dependencies and config

- [x] 1.1 Add `fastapi` and `uvicorn` to project dependencies in `pyproject.toml`
- [x] 1.2 Add `ServerConfig` Pydantic model with `port: int | None` to `src/maestro/core/config.py`
- [x] 1.3 Integrate `ServerConfig` into the workflow config resolution in `src/maestro/core/workflow.py`

## 2. FastAPI application

- [x] 2.1 Create `src/maestro/web/app.py` with FastAPI app factory accepting `OrchestratorState`
- [x] 2.2 Create `src/maestro/web/routes.py` with route handler stubs (state, issue, refresh)
- [x] 2.3 Create `src/maestro/web/dashboard.py` with Jinja2 template rendering
- [x] 2.4 Create `src/maestro/web/templates/dashboard.html` Jinja2 template

## 3. REST API — state endpoint

- [x] 3.1 Implement `GET /api/v1/state` handler using `SnapshotBuilder` from orchestrator state
- [x] 3.2 Shape response to match SPEC §13.7.2 schema (counts, running, retrying, codex_totals, rate_limits)
- [x] 3.3 Include `generated_at` timestamp and `turn_count` in running rows

## 4. REST API — per-issue endpoint

- [x] 4.1 Implement `GET /api/v1/{issue_identifier}` handler with orchestrator state lookup
- [x] 4.2 Return `404` with error envelope when issue is not in running, retrying, or claimed
- [x] 4.3 Return issue-specific details (status, workspace, attempts, running/retry, recent_events) per SPEC

## 5. REST API — refresh endpoint

- [x] 5.1 Implement `POST /api/v1/refresh` handler with `asyncio.Event` trigger
- [x] 5.2 Return `202 Accepted` with `queued`, `coalesced`, `requested_at`, `operations`
- [x] 5.3 Support coalescing of repeated refresh requests

## 6. Error handling

- [x] 6.1 Return `405 Method Not Allowed` for unsupported methods on defined routes
- [x] 6.2 Ensure all API errors use `{"error": {"code": "...", "message": "..."}}` envelope

## 7. HTML dashboard

- [x] 7.1 Implement HTML dashboard template showing running sessions, retry queue, token totals, runtime
- [x] 7.2 Include refresh button that POSTs to `/api/v1/refresh`
- [x] 7.3 Show empty state when no sessions are running
- [x] 7.4 Add basic CSS styling for readability (inline or minimal stylesheet)

## 8. CLI and server wiring

- [x] 8.1 Wire `--port` CLI argument into server startup in `src/maestro/cli/main.py`
- [x] 8.2 Resolve port precedence: CLI `--port` overrides `server.port` config
- [x] 8.3 Start uvicorn server as an `asyncio` task alongside the orchestrator
- [x] 8.4 Bind to `127.0.0.1` by default (loopback)

## 9. Unit tests

- [x] 9.1 Test state endpoint returns correct shape with mock orchestrator state
- [x] 9.2 Test per-issue endpoint returns issue details and 404 for unknown issue
- [x] 9.3 Test refresh endpoint returns 202 and triggers event
- [x] 9.4 Test 405 for unsupported methods
- [x] 9.5 Test dashboard renders with running sessions and empty state
- [x] 9.6 Test server config model parsing and port precedence

## 10. Integration tests

- [x] 10.1 Test full server startup with TestClient against mock orchestrator state
- [x] 10.2 Test state endpoint with running sessions and retry queue populated
- [x] 10.3 Test per-issue endpoint with multiple states (running, retrying, unknown)
- [x] 10.4 Test ephemeral port (`server.port: 0`) binding