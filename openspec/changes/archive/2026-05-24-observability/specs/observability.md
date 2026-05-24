## ADDED Requirements

### Requirement: Structured logging conventions
> Source: SPEC §13.1

Logs for issue-related operations SHALL include these context fields:
- `issue_id`
- `issue_identifier`

Logs for coding-agent session lifecycle SHALL include:
- `session_id`

Message formatting requirements:
- Use stable `key=value` phrasing
- Include action outcome (`completed`, `failed`, `retrying`, etc.)
- Include concise failure reason when present
- Avoid logging large raw payloads unless necessary

**Tests:**
- Structured logging includes issue/session context fields
- Log messages use key=value phrasing with action outcomes

### Requirement: Logging outputs and sinks
> Source: SPEC §13.2

Operators MUST be able to see startup/validation/dispatch failures without attaching a debugger.

If a configured log sink fails, the service SHOULD continue running when possible and emit an operator-visible warning through any remaining sink.

**Tests:**
- Logging sink failures do not crash orchestration

### Requirement: Runtime snapshot
> Source: SPEC §13.3

If the implementation exposes a synchronous runtime snapshot, it SHALL return:
- `running` (list of running session rows)
- each running row SHALL include `turn_count`
- `retrying` (list of retry queue rows)
- `codex_totals` with `input_tokens`, `output_tokens`, `total_tokens`, `seconds_running`
- `rate_limits` (latest coding-agent rate limit payload, if available)

RECOMMENDED snapshot error modes:
- `timeout`
- `unavailable`

**Tests:**
- If a snapshot API is implemented, it returns running rows, retry rows, token totals, and rate limits
- If a snapshot API is implemented, timeout/unavailable cases are surfaced

### Requirement: Token accounting
> Source: SPEC §13.5

Token accounting rules:
- Prefer absolute thread totals when available
- Ignore delta-style payloads such as `last_token_usage` for dashboard/API totals
- Extract input/output/total token counts leniently from common field names
- For absolute totals, track deltas relative to last reported totals to avoid double-counting
- Do not treat generic `usage` maps as cumulative totals unless the event type defines them that way
- Accumulate aggregate totals in orchestrator state

Runtime accounting:
- Runtime SHOULD be reported as a live aggregate at snapshot/render time
- Add run duration seconds to the cumulative ended-session runtime when a session ends
- Continuous background ticking of runtime totals is not REQUIRED

**Tests:**
- Token/rate-limit aggregation remains correct across repeated agent updates

### Requirement: Humanized agent event summaries
> Source: SPEC §13.6

Humanized summaries of raw agent protocol events are OPTIONAL.

If implemented:
- Treat them as observability-only output
- Do not make orchestrator logic depend on humanized strings

**Tests:**
- If humanized event summaries are implemented, they cover key wrapper/agent event classes without changing orchestrator behavior
