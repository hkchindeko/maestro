## Problem

SPEC §11.1, §11.2, and §11.3 define the Linear issue tracker adapter requirements:

1. **REQUIRED operations** — `fetch_candidate_issues()`, `fetch_issues_by_states()`, `fetch_issue_states_by_ids()` (§11.1)
2. **Linear query semantics** — GraphQL endpoint, auth token, project slug filter via `slugId`, pagination (page size 50), network timeout 30s (§11.2)
3. **Issue normalization** — labels to lowercase, `blocked_by` from inverse `blocks` relations, priority as integer, ISO-8601 timestamp parsing (§11.3)
4. **Error handling** — typed error categories for transport failures, non-200 status, GraphQL errors, malformed payloads (§11.4)

The `workflow-config` and `prompt-builder` changes provide config loading and prompt rendering, but no tracker integration exists yet. The Linear adapter is the first and primary tracker implementation per SPEC §11.2.

## What Changes

- Define `Tracker` abstract base class with the three required operations
- Implement `LinearTracker` using `httpx` for GraphQL API calls
- Implement Linear candidate issue query with project slug filter and pagination
- Implement issue state refresh query with GraphQL ID typing (`[ID!]`)
- Implement terminal state fetch for startup cleanup
- Implement issue normalization (labels, blockers, priority, timestamps)
- Implement typed error classes for all SPEC §11.4 error categories
- Write unit tests for query construction, pagination, normalization, and error handling

## Capabilities

### New Capabilities

- `tracker-protocol`: Abstract `Tracker` interface with `fetch_candidate_issues`, `fetch_issues_by_states`, `fetch_issue_states_by_ids`
- `linear-tracker`: Linear GraphQL adapter with pagination, project slug filter, and auth
- `issue-normalization`: Normalize Linear API responses to stable issue model per SPEC §4.1.1

### Modified Capabilities

None — this is a new capability.

## Impact

- **New modules:**
  - `src/maestro/tracker/base.py` — `Tracker` ABC and `Issue`, `IssueSnapshot` models
  - `src/maestro/tracker/linear.py` — Linear GraphQL client
- **Dependencies added:** `httpx` (already in `pyproject.toml` from workflow-config)
- **Depends on:** `workflow-config` change (for `TrackerConfig` with Linear endpoint/api_key/project_slug)
- **No breaking changes**
