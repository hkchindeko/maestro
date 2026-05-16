## 1. Pydantic config models

- [x] 1.1 Create `TrackerConfig` with `kind`, `endpoint`, `api_key`, `project_slug`, `active_states`, `terminal_states` and defaults per SPEC §5.3.1
- [x] 1.2 Create `PollingConfig` with `interval_ms` (default 30000) per SPEC §5.3.2
- [x] 1.3 Create `WorkspaceConfig` with `root` (default system temp path) per SPEC §5.3.3
- [x] 1.4 Create `HooksConfig` with `after_create`, `before_run`, `after_run`, `before_remove`, `timeout_ms` (default 60000) per SPEC §5.3.4
- [x] 1.5 Create `SandboxConfig` with `kind` (default "local"), `image`, `resources`, `env` per SPEC §5.3.5
- [x] 1.6 Create `AgentConfig` with `kind`, `command`, `approval_policy`, `max_concurrent_agents`, `max_turns`, `max_retry_backoff_ms`, `max_concurrent_agents_by_state` per SPEC §5.3.6
- [x] 1.7 Create `CodexConfig` (deprecated) with pass-through fields per SPEC §5.3.7
- [x] 1.8 Create `WorkflowConfig` root model combining all sub-configs
- [x] 1.9 Write unit tests for model defaults and validation

## 2. $VAR resolution and path normalization

- [x] 2.1 Implement `$VAR_NAME` resolution validator: resolve from `os.environ`, treat empty as missing
- [x] 2.2 Implement `~` home expansion for path fields (`workspace.root`)
- [x] 2.3 Implement relative path resolution for `workspace.root` relative to WORKFLOW.md directory
- [x] 2.4 Write unit tests for $VAR resolution (valid, empty, missing env var)
- [x] 2.5 Write unit tests for path normalization (~, relative, absolute)

## 3. WORKFLOW.md loader

- [x] 3.1 Implement file discovery: explicit path → cwd default (`./WORKFLOW.md`)
- [x] 3.2 Implement YAML front matter parsing (split on `---` markers)
- [x] 3.3 Handle missing front matter (entire file = prompt body, empty config)
- [x] 3.4 Validate front matter is a map (not list/scalar) → `workflow_front_matter_not_a_map` error
- [x] 3.5 Return `WorkflowDefinition(config, prompt_template)` tuple
- [x] 3.6 Write unit tests for valid/invalid WORKFLOW.md files

## 4. Dispatch preflight validation

- [x] 4.1 Implement `validate_dispatch_config()`: workflow file loadable, `tracker.kind` present/supported, `tracker.api_key` present after $ resolution, `tracker.project_slug` when required, `agent.command` non-empty
- [x] 4.2 Return typed error for each validation failure class
- [x] 4.3 Write unit tests for all validation failure scenarios

## 5. Dynamic reload

- [x] 5.1 Set up `watchdog` file watcher on WORKFLOW.md path
- [x] 5.2 Re-read and re-apply config on file change event
- [x] 5.3 Keep last known good config on parse/validation error, emit operator-visible warning
- [x] 5.4 Write unit tests for reload behavior (valid change, invalid change, keep last good)

## 6. CLI commands

- [x] 6.1 Implement `maestro config validate [WORKFLOW.md]` — validate and report errors
- [x] 6.2 Implement `maestro config show [WORKFLOW.md]` — show resolved config with defaults applied
- [x] 6.3 Write integration tests for CLI commands
