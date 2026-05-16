## Problem

SPEC §5.2, §5.3, §6.1, and §6.3 define the workflow configuration system that every other component depends on:

1. **WORKFLOW.md parsing** — YAML front matter + Markdown body split (§5.2)
2. **Typed config models** — all front-matter keys with defaults, validation, and `$VAR` resolution (§5.3, §6.1)
3. **Dispatch preflight validation** — required fields checked before any dispatch (§6.3)
4. **Dynamic reload** — detect file changes and re-apply without restart (§6.2)

No implementation exists yet. This is the foundational layer that unblocks all other changes (tracker, workspace, agent, orchestrator).

## What Changes

- Add Pydantic v2 models for all workflow front-matter keys (`tracker`, `polling`, `workspace`, `hooks`, `sandbox`, `agent`, `codex`)
- Implement `WORKFLOW.md` loader: YAML front matter parsing + Markdown body extraction
- Implement `$VAR_NAME` environment variable indirection for config values
- Implement `~` home expansion and relative path resolution for `workspace.root`
- Implement dispatch preflight validation (§6.3)
- Implement dynamic file watch + reload via `watchdog`
- Add CLI commands: `maestro config validate` and `maestro config show`

## Capabilities

### New Capabilities

- `workflow-config-load`: Parse `WORKFLOW.md` into typed config + prompt template
- `config-validation`: Validate required fields before dispatch (SPEC §6.3)
- `config-reload`: Detect `WORKFLOW.md` changes and re-apply without restart (SPEC §6.2)
- `config-cli`: Inspect and validate workflow config via CLI commands

### Modified Capabilities

None — this is a new capability.

## Impact

- **New modules:**
  - `src/maestro/core/config.py` — Pydantic config models
  - `src/maestro/core/workflow.py` — WORKFLOW.md loader + dynamic reload
  - `src/maestro/cli/config.py` — CLI subcommands for config
- **Dependencies added:** `pydantic`, `pyyaml`, `jinja2`, `watchdog`, `typer`
- **No breaking changes** — this is the first implementation change
