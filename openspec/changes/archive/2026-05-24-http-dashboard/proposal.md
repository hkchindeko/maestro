## Why

Operators need visibility into running orchestrator state without attaching a debugger or tailing logs. SPEC §13.7 defines an optional HTTP server extension with a human-readable dashboard at `/` and a JSON REST API at `/api/v1/*`. The observability module already has snapshot, token accounting, and logging capabilities — this change wires them into a FastAPI server so operators can inspect running sessions, retry queues, token consumption, and trigger refresh cycles from a browser or `curl`.

## What Changes

- Add FastAPI as a dependency
- Implement HTTP server in `src/maestro/web/` with FastAPI
- Expose `GET /api/v1/state` returning runtime snapshot from orchestrator state
- Expose `GET /api/v1/<issue_identifier>` returning per-issue debug details
- Expose `POST /api/v1/refresh` for on-demand poll-and-reconciliation trigger
- Serve a human-readable dashboard at `/` (server-rendered HTML using Jinja2)
- Wire server enablement through CLI `--port` (already present) and workflow `server.port` config
- Bind loopback by default (`127.0.0.1`) per SPEC
- Return proper error envelopes (`404`, `405`) per SPEC §13.7

## Capabilities

### New Capabilities

- `http-dashboard`: FastAPI HTTP server with REST API and HTML dashboard per SPEC §13.7

### Modified Capabilities

None — this is a new capability built on top of existing `observability` and `core-orchestrator` modules.

## Impact

- **New dependency:** `fastapi>=0.115`, `uvicorn>=0.30`
- **New modules:**
  - `src/maestro/web/app.py` — FastAPI application factory
  - `src/maestro/web/routes.py` — API endpoint handlers
  - `src/maestro/web/dashboard.py` — Server-rendered HTML dashboard
  - `src/maestro/web/templates/` — Jinja2 templates for dashboard
- **Modified modules:**
  - `src/maestro/cli/main.py` — Wire `--port` into server startup
  - `src/maestro/core/config.py` — Add `server.port` to config model
- **Depends on:** `observability` (snapshot, tokens), `core-orchestrator` (state)
- **No breaking changes**