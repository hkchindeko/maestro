## 1. Tracker protocol

- [x] 1.1 Define `Issue` dataclass with all normalized fields per SPEC §4.1.1
- [x] 1.2 Define `IssueSnapshot` dataclass for state refresh (minimal: id, identifier, state)
- [x] 1.3 Define `BlockerRef` dataclass (reuse from prompt models or define in tracker)
- [x] 1.4 Define `Tracker` ABC with `fetch_candidate_issues()`, `fetch_issues_by_states()`, `fetch_issue_states_by_ids()`
- [x] 1.5 Write unit tests for protocol types

## 2. Linear GraphQL client

- [x] 2.1 Implement `LinearTracker` class with `httpx.AsyncClient`, endpoint, and auth from `TrackerConfig`
- [x] 2.2 Implement `_execute_query(query, variables)` with 30s timeout and `Authorization` header
- [x] 2.3 Implement `fetch_candidate_issues()` with project slug filter (`project: { slugId: { eq: $projectSlug } }`)
- [x] 2.4 Implement cursor-based pagination with `pageInfo { hasNextPage, endCursor }`, page size 50
- [x] 2.5 Implement `fetch_issues_by_states(state_names)` for terminal state cleanup
- [x] 2.6 Implement `fetch_issue_states_by_ids(issue_ids)` with `[ID!]` variable type for state refresh
- [x] 2.7 Write unit tests for query construction and pagination

## 3. Issue normalization

- [x] 3.1 Implement `normalize_issue(raw: dict) -> Issue` function
- [x] 3.2 Normalize `labels` to lowercase strings
- [x] 3.3 Extract `blocked_by` from inverse relations of type `blocks`
- [x] 3.4 Convert `priority` to integer only (non-integers become null)
- [x] 3.5 Parse `created_at` and `updated_at` as ISO-8601 timestamps
- [x] 3.6 Write unit tests for all normalization rules

## 4. Error handling

- [x] 4.1 Define `LinearApiRequestError` for transport failures
- [x] 4.2 Define `LinearApiStatusError` for non-200 HTTP status
- [x] 4.3 Define `LinearGraphQLError` for GraphQL errors in response
- [x] 4.4 Define `LinearUnknownPayloadError` for malformed/unexpected payloads
- [x] 4.5 Define `LinearMissingEndCursorError` for pagination integrity errors
- [x] 4.6 Write unit tests for each error class

## 5. Integration tests

- [x] 5.1 Test full candidate fetch → normalize pipeline with mock Linear response
- [x] 5.2 Test state refresh with mock response
- [x] 5.3 Test terminal state fetch with mock response
- [x] 5.4 Test empty `fetch_issues_by_states([])` returns empty without API call
