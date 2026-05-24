## Context

SPEC §13.7 defines an OPTIONAL HTTP server extension with two surfaces: a human-readable dashboard at `/` and a JSON REST API at `/api/v1/*`. The CLI already has a `--port` flag placeholder. The observability module (`maestro.observability`) already provides `RuntimeSnapshot`, `SnapshotBuilder`, token accounting, and structured logging. The orchestrator (`maestro.core.state`) has `OrchestratorState` with running entries, retry entries, codex totals, and rate limits.

What's missing is the HTTP server that wires these together and serves them.

## Goals / Non-Goals

**Goals:**
- Serve `GET /api/v1/state` returning runtime snapshot conforming to SPEC §13.7 shape
- Serve `GET /api/v1/<issue_identifier>` returning per-issue debug details with 404 handling
- Serve `POST /api/v1/refresh` triggering poll-and-reconciliation
- Serve `/` as a server-rendered HTML dashboard using Jinja2 (already a dependency)
- Bind loopback (`127.0.0.1`) by default per SPEC
- Enable via CLI `--port` (already wired in CLI) and workflow `server.port` config
- Return proper error envelopes (`404`, `405`) per SPEC

**Non-Goals:**
- Client-side SPA dashboard — server-rendered HTML is simpler and sufficient
- Hot-reload on port changes — restart-required is conformant per SPEC
- Authentication/authorization — out of scope for v1
- WebSocket or SSE streaming — out of scope; dashboard can poll
- TLS termination — operator concern, not application concern

## Decisions

### Decision 1: FastAPI over Starlette or aiohttp

**Why:** FastAPI provides automatic OpenAPI docs, Pydantic integration, and clean decorator-based routing. It's the de facto standard for Python REST APIs and works well with `asyncio` (which the orchestrator already uses). Pydantic is already a project dependency.

**Alternatives considered:**
- Raw Starlette — FastAPI is Starlette under the hood; no benefit to using raw Starlette
- aiohttp — more boilerplate, less ecosystem support than FastAPI
- Flask — synchronous, doesn't fit the async orchestrator architecture

### Decision 2: Server-rendered HTML dashboard (Jinja2)

**Why:** SPEC §13.7 says "The implementation MAY serve server-rendered HTML or a client-side application." Jinja2 is already a project dependency (for prompt templates). Server-rendered HTML avoids a separate frontend build step and keeps deployment simple.

**Alternatives considered:**
- Client-side SPA (React/Vue) — more interactive but adds build toolchain, separate deployment concerns
- HTMX — interesting but adds another dependency for marginal benefit

### Decision 3: Shared orchestrator state reference (not copy)

**Why:** The FastAPI app needs access to `OrchestratorState` to build snapshots. Passing a reference to the state object is simpler than a pub/sub or message-passing model. The state already has `asyncio.Lock` for thread safety.

**Alternatives considered:**
- Event bus / pub-sub — overengineered for read-only API access
- Snapshot polling via file — adds I/O latency, no benefit

### Decision 4: `/refresh` as a best-effort trigger

**Why:** SPEC says "best-effort trigger; implementations MAY coalesce repeated requests." The endpoint sets an `asyncio.Event` that the poll loop checks. This is simple and avoids complex queueing.

**Alternatives considered:**
- Direct orchestrator method call — couples HTTP layer to orchestrator internals
- Message queue — overkill for a single-process trigger

### Decision 5: 404 on unknown issue identifiers

**Why:** SPEC §13.7 explicitly requires: "If the issue is unknown to the current in-memory state, return `404`." Simple lookup in orchestrator state — if not in running, retrying, or claimed, return 404.

### Decision 6: Config via Pydantic model extension

**Why:** The project already uses Pydantic v2 for all config. Adding `server: ServerConfig` with `port: int | None` to the existing config model follows the established pattern.

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| FastAPI adds startup overhead | Low | Uvicorn with 1 worker is lightweight; dashboard is optional |
| Dashboard HTML grows complex | Low | Keep it simple — single template, no JavaScript framework |
| State lock contention (API reads while orchestrator writes) | Low | Reads are fast (snapshot assembly is O(n) in running count) |
| `uvicorn` requires `click` dependency conflict with `typer` | Low | Typer is built on Click; versions should be compatible |

## Open Questions

None — all decisions are resolved in this design.