## ADDED Requirements

### Requirement: WORKFLOW.md file parsing
> Source: SPEC §5.1, §5.2

The workflow loader SHALL support two file discovery paths:
1. Explicit runtime path (set by CLI or application setting)
2. Default: `WORKFLOW.md` in the current process working directory

If the file cannot be read, the loader SHALL return a `missing_workflow_file` error.

The loader SHALL parse the file as follows:
- If the file starts with `---`, parse lines until the next `---` as YAML front matter
- Remaining lines become the prompt body (trimmed)
- If front matter is absent, treat the entire file as prompt body with an empty config map
- YAML front matter MUST decode to a map/object; non-map YAML SHALL return a `workflow_front_matter_not_a_map` error
- Prompt body is trimmed before use

The loader SHALL return a `WorkflowDefinition` containing:
- `config`: front matter root object (not nested under a `config` key)
- `prompt_template`: trimmed Markdown body

**Tests:**
- Explicit runtime path is used when provided
- Cwd default is `WORKFLOW.md` when no explicit runtime path is provided
- Missing `WORKFLOW.md` returns typed error
- Invalid YAML front matter returns typed error
- Front matter non-map returns typed error
- Empty front matter produces empty config map
- Prompt body is trimmed

### Requirement: Config resolution pipeline
> Source: SPEC §6.1

Configuration SHALL be resolved in this order:
1. Select the workflow file path (explicit runtime setting, otherwise cwd default)
2. Parse YAML front matter into a raw config map
3. Apply built-in defaults for missing OPTIONAL fields
4. Resolve `$VAR_NAME` indirection only for config values that explicitly contain `$VAR_NAME`
5. Coerce and validate typed values

Environment variables SHALL NOT globally override YAML values. They SHALL be used only when a config value explicitly references them via `$VAR_NAME`.

**Tests:**
- Config defaults apply when OPTIONAL values are missing
- `$VAR` resolution works for tracker API key and path values
- Empty resolved value treated as missing

### Requirement: $VAR_NAME environment variable indirection
> Source: SPEC §5.3.1, §6.1

When a config value contains `$VAR_NAME` (where VAR_NAME matches `[A-Za-z_][A-Za-z0-9_]*`), the config layer SHALL:
1. Read the corresponding environment variable
2. Replace the `$VAR_NAME` reference with the resolved value
3. If the resolved value is an empty string, treat the key as missing

**Tests:**
- `$VAR` resolution works for tracker API key
- `$VAR` resolution works for path values
- Empty resolved value treated as missing
- Missing env var treated as missing config value

### Requirement: Path normalization
> Source: SPEC §5.3.3, §6.1

Path fields (specifically `workspace.root`) SHALL support:
- `~` home expansion
- `$VAR` expansion for env-backed path values
- Relative path resolution relative to the directory containing the selected `WORKFLOW.md`
- Normalization to an absolute path before use

Relative `workspace.root` values SHALL resolve relative to the directory containing the selected `WORKFLOW.md`.

**Tests:**
- `~` path expansion works
- Relative path resolves relative to WORKFLOW.md directory
- Absolute path is preserved as-is

### Requirement: Front matter schema defaults
> Source: SPEC §5.3

The config layer SHALL apply the following defaults for missing OPTIONAL fields:

| Field | Default |
|-------|---------|
| `tracker.endpoint` | `https://api.linear.app/graphql` (when `tracker.kind == "linear"`) |
| `tracker.active_states` | `["Todo", "In Progress"]` |
| `tracker.terminal_states` | `["Closed", "Cancelled", "Canceled", "Duplicate", "Done"]` |
| `polling.interval_ms` | `30000` |
| `workspace.root` | `<system-temp>/symphony_workspaces` |
| `hooks.timeout_ms` | `60000` |
| `sandbox.kind` | `local` |
| `agent.kind` | `codex` |
| `agent.max_concurrent_agents` | `10` |
| `agent.max_turns` | `20` |
| `agent.max_retry_backoff_ms` | `300000` |
| `agent.max_concurrent_agents_by_state` | `{}` |
| `codex.command` | `codex app-server` |
| `codex.turn_timeout_ms` | `3600000` |
| `codex.read_timeout_ms` | `5000` |
| `codex.stall_timeout_ms` | `300000` |

Unknown top-level keys in the front matter SHALL be ignored for forward compatibility.

**Tests:**
- Config defaults apply when OPTIONAL values are missing
- Unknown keys are ignored

### Requirement: Dispatch preflight validation
> Source: SPEC §6.3

Before dispatching work, the config layer SHALL validate:
- Workflow file can be loaded and parsed
- `tracker.kind` is present and supported
- `tracker.api_key` is present after `$` resolution
- `tracker.project_slug` is present when REQUIRED by the selected tracker kind
- `agent.command` (or `codex.command`) is present and non-empty

Validation failures SHALL return typed errors and block new dispatches until fixed.

**Tests:**
- Missing `tracker.kind` fails validation
- Missing `tracker.api_key` (after $ resolution) fails validation
- Missing `tracker.project_slug` for Linear fails validation
- Missing `agent.command` fails validation
- Valid config passes validation

### Requirement: Dynamic WORKFLOW.md reload
> Source: SPEC §6.2

The software SHALL detect `WORKFLOW.md` changes and re-read and re-apply workflow config and prompt template without restart.

On change, the software SHALL:
- Re-read the workflow file
- Re-parse and re-validate the config
- Re-apply the new config to future dispatch, retry scheduling, reconciliation decisions, hook execution, and agent launches

Invalid reloads SHALL NOT crash the service. The software SHALL:
- Keep operating with the last known good effective configuration
- Emit an operator-visible error

**Tests:**
- Workflow file changes are detected and trigger re-read/re-apply without restart
- Invalid workflow reload keeps last known good effective configuration and emits an operator-visible error

### Requirement: Workspace key sanitization
> Source: SPEC §4.2, §9.5

The workspace key SHALL be derived from `issue.identifier` by replacing any character not in `[A-Za-z0-9._-]` with `_`.

**Tests:**
- Sanitization replaces special characters with underscore
- Valid characters are preserved
