## ADDED Requirements

### Requirement: Tracker protocol
> Source: SPEC §11.1

An implementation MUST support these tracker adapter operations:

1. `fetch_candidate_issues()` — return issues in configured active states for a configured project
2. `fetch_issues_by_states(state_names)` — used for startup terminal cleanup
3. `fetch_issue_states_by_ids(issue_ids)` — used for active-run reconciliation

The `Tracker` interface SHALL be defined as an abstract base class so that multiple tracker kinds (Linear, GitHub, etc.) can be implemented.

**Tests:**
- `Tracker` ABC defines all three required methods
- Concrete implementations can be substituted via the protocol

### Requirement: Linear candidate issue fetch
> Source: SPEC §11.2

For `tracker.kind == "linear"`, the adapter SHALL:
- Use the GraphQL endpoint (default `https://api.linear.app/graphql`)
- Send auth token in `Authorization` header
- Filter candidate issues by project using `project: { slugId: { eq: $projectSlug } }`
- Use cursor-based pagination with default page size 50
- Apply network timeout of 30000 ms

**Tests:**
- Candidate issue fetch uses active states and project slug
- Linear query uses the specified project filter field (`slugId`)
- Pagination preserves order across multiple pages

### Requirement: Linear issue state refresh
> Source: SPEC §11.2

The issue state refresh query SHALL use GraphQL issue IDs with variable type `[ID!]`.

**Tests:**
- Issue state refresh by ID returns minimal normalized issues
- Issue state refresh query uses GraphQL ID typing (`[ID!]`) as specified

### Requirement: Issue normalization
> Source: SPEC §4.1.1, §11.3

Candidate issue normalization SHALL produce fields listed in SPEC §4.1.1:
- `id` (string) — stable tracker-internal ID
- `identifier` (string) — human-readable ticket key
- `title` (string)
- `description` (string or null)
- `priority` (integer or null) — lower numbers are higher priority
- `state` (string) — current tracker state name
- `branch_name` (string or null)
- `url` (string or null)
- `labels` (list of strings) — normalized to lowercase
- `blocked_by` (list of blocker refs) — derived from inverse relations of type `blocks`
- `created_at` (timestamp or null) — parsed from ISO-8601
- `updated_at` (timestamp or null) — parsed from ISO-8601

Additional normalization:
- `labels` → lowercase strings
- `blocked_by` → derived from inverse relations where relation type is `blocks`
- `priority` → integer only (non-integers become null)
- `created_at` and `updated_at` → parse ISO-8601 timestamps

**Tests:**
- Blockers are normalized from inverse relations of type `blocks`
- Labels are normalized to lowercase
- Priority is converted to integer (non-integers become null)
- Timestamps are parsed from ISO-8601

### Requirement: Linear error handling
> Source: SPEC §11.4

The adapter SHALL categorize errors into typed classes:
- `linear_api_request` — transport failures (network errors, timeouts)
- `linear_api_status` — non-200 HTTP status codes
- `linear_graphql_errors` — GraphQL errors in response body
- `linear_unknown_payload` — malformed or unexpected response payloads
- `linear_missing_end_cursor` — pagination integrity error (missing endCursor when hasNextPage is true)

Orchestrator behavior on tracker errors:
- Candidate fetch failure: log and skip dispatch for this tick
- Running-state refresh failure: log and keep active workers running
- Startup terminal cleanup failure: log warning and continue startup

**Tests:**
- Error mapping for request errors, non-200, GraphQL errors, malformed payloads
- Empty `fetch_issues_by_states([])` returns empty without API call
