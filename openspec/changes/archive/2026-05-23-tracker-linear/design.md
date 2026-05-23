## Context

The Linear tracker adapter is the first tracker implementation for Maestro. It uses Linear's GraphQL API to fetch candidate issues, refresh issue states, and fetch terminal issues for startup cleanup. SPEC §11.2 defines the exact query semantics for Linear.

Key SPEC sections:
- §4.1.1: Issue entity fields (normalized issue model)
- §11.1: REQUIRED tracker operations (fetch_candidate_issues, fetch_issues_by_states, fetch_issue_states_by_ids)
- §11.2: Linear query semantics (GraphQL endpoint, auth, project slug filter, pagination, timeout)
- §11.3: Normalization rules (labels lowercase, blocked_by from inverse blocks, priority integer, ISO-8601 timestamps)
- §11.4: Error handling contract (typed error categories)

## Decisions

### Decision 1: httpx for HTTP client

**Why:** Async-capable, modern type-safe HTTP client already in `pyproject.toml`. Linear's GraphQL API is HTTP POST with JSON body, which httpx handles cleanly. The async capability will be useful when the orchestrator runs concurrent tracker calls.

**Alternatives considered:**
- `requests` — sync-only, would need thread pool for async orchestrator
- `aiohttp` — more complex API, httpx is simpler and already a dependency

### Decision 2: Single GraphQL query per operation

**Why:** SPEC §11.1 defines three distinct operations. Each maps to a separate GraphQL query:
- `fetch_candidate_issues` → paginated issues query with project filter
- `fetch_issues_by_states` → issues filtered by state names (for terminal cleanup)
- `fetch_issue_states_by_ids` → minimal state refresh query with `[ID!]` variable type

Keeping queries separate avoids over-fetching and matches the spec's operation boundaries.

**Alternatives considered:**
- Single mega-query with fragments — over-fetches, harder to maintain
- GraphQL client library (e.g., `gql`) — adds dependency, raw httpx is sufficient for simple queries

### Decision 3: Cursor-based pagination with `endCursor`

**Why:** SPEC §11.2 requires pagination for candidate issues with default page size 50. Linear's GraphQL API uses cursor-based pagination with `pageInfo { hasNextPage, endCursor }`. The adapter loops until `hasNextPage` is false, accumulating results.

**Alternatives considered:**
- Offset-based pagination — Linear doesn't support it
- Single-page fetch with large limit — risks API limits, spec requires pagination

### Decision 4: Issue normalization as pure functions

**Why:** SPEC §11.3 defines normalization rules (labels lowercase, blocked_by from inverse blocks, priority integer, ISO-8601 timestamps). Implementing these as pure functions (`normalize_issue(raw: dict) -> Issue`) makes them easily testable and reusable across tracker adapters.

**Alternatives considered:**
- Normalization in the GraphQL query — harder to test, couples query to normalization logic
- Pydantic validators — overkill for simple field transformations

### Decision 5: Typed error classes per SPEC §11.4

**Why:** SPEC §11.4 recommends error categories: `linear_api_request`, `linear_api_status`, `linear_graphql_errors`, `linear_unknown_payload`, `linear_missing_end_cursor`. Typed exception classes allow the orchestrator to handle each error class differently (e.g., retry on transport failure, skip dispatch on GraphQL errors).

**Alternatives considered:**
- Single `LinearError` with error code string — harder to catch specific errors
- Return error dicts instead of exceptions — breaks Python error handling conventions

### Decision 6: Auth via `Authorization` header

**Why:** SPEC §11.2 states: "Auth token sent in `Authorization` header." The adapter reads `api_key` from `TrackerConfig` (already resolved via `$VAR` by workflow-config) and sets `Authorization: Bearer <token>`.

## Non-Decisions

- **GraphQL schema introspection** — not needed; queries are hand-crafted per spec
- **Webhook support** — spec uses polling, not webhooks
- **Linear mutations** — spec §11.5 states tracker writes are handled by agent tools, not the orchestrator

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Linear GraphQL API schema changes | Medium | Pin query fields, test with real API, isolate query construction |
| Rate limiting from Linear API | Medium | Respect rate limits, configurable timeout (30s per spec) |
| Large project with many issues | Low | Pagination handles this; page size 50 per spec |
| Missing `endCursor` in pagination response | Low | `linear_missing_end_cursor` error, skip dispatch for that tick |
