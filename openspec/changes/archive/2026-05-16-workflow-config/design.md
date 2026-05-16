## Context

The config layer is the foundation of Maestro. It parses `WORKFLOW.md` (YAML front matter + Markdown body), resolves environment variables, applies defaults, validates required fields, and supports dynamic reload. All other components (tracker, workspace, agent, orchestrator) depend on this layer.

Key SPEC sections:
- §5.2: WORKFLOW.md file format (YAML front matter + prompt body)
- §5.3: Front matter schema (tracker, polling, workspace, hooks, sandbox, agent, codex)
- §6.1: Configuration resolution pipeline (parse → defaults → $VAR → validate)
- §6.2: Dynamic reload semantics (watch, re-read, re-apply, keep last good on error)
- §6.3: Dispatch preflight validation (required fields before dispatch)

## Decisions

### Decision 1: Pydantic v2 for config models

**Why:** Typed validation, `$VAR` resolution via custom validators, clear error messages, and JSON schema generation. Pydantic's `model_validator` and `field_validator` decorators map cleanly to SPEC §6.1's resolution pipeline.

**Alternatives considered:**
- `dataclasses` + manual validation — more boilerplate, no built-in validation
- `attrs` — similar to dataclasses, less ecosystem support for JSON schema
- Plain dicts with validation functions — no type safety, harder to test

### Decision 2: Two-phase loading (raw → resolved)

**Why:** SPEC §6.1 defines a clear resolution pipeline: parse YAML → apply defaults → resolve `$VAR` → validate. A two-phase approach (`RawWorkflowConfig` → `WorkflowConfig`) makes this explicit and testable. The raw phase captures the YAML as-is; the resolved phase applies all transformations.

**Alternatives considered:**
- Single model with `__init__` doing everything — harder to test each phase independently
- Builder pattern — overkill for this use case

### Decision 3: `$VAR` resolution via Pydantic field validators

**Why:** SPEC §6.1 states that `$VAR_NAME` indirection applies only to config values that explicitly contain `$VAR_NAME`. A field validator that checks for `^\$[A-Za-z_][A-Za-z0-9_]*$` and resolves from `os.environ` is clean and testable. Empty resolved values are treated as missing (SPEC §5.3.1).

**Alternatives considered:**
- Pre-processing the raw YAML dict before Pydantic — loses type safety during resolution
- Custom `__getattribute__` — fragile, breaks IDE support

### Decision 4: `watchdog` for dynamic reload

**Why:** Cross-platform file watching, well-maintained, simple API. SPEC §6.2 requires detecting `WORKFLOW.md` changes and re-applying without restart. `watchdog`'s `FileSystemEventHandler` maps directly to this requirement.

**Alternatives considered:**
- Polling-based watch — simpler but less responsive, wastes CPU
- `inotify` (Linux only) — not cross-platform

### Decision 5: Keep last known good config on reload error

**Why:** SPEC §6.2 explicitly states: "Invalid reloads MUST NOT crash the service; keep operating with the last known good effective configuration and emit an operator-visible error." The reload handler catches parse/validation errors, logs them, and retains the previous config.

### Decision 6: Jinja2 in strict undefined mode for prompt template

**Why:** SPEC §5.4 requires that unknown variables and unknown filters MUST fail rendering. Jinja2's `Undefined` class with `StrictUndefined` enforces this. Jinja2 is Liquid-compatible for the template features used in this spec.

**Alternatives considered:**
- `liquidpy` — closer to Liquid spec but less maintained, fewer features
- `string.Template` — no filter support, too limited

## Non-Decisions

- **Config file formats other than WORKFLOW.md** — SPEC §5.1 defines only WORKFLOW.md as the workflow file
- **Global env var overrides** — SPEC §6.1 explicitly states: "Environment variables do not globally override YAML values. They are used only when a config value explicitly references them."
- **Config validation at import time** — validation happens at load time, not import time, to support dynamic reload

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pydantic v2 API changes | Low | Pin version in `pyproject.toml`, test against pinned version |
| `watchdog` missing file change events | Medium | Defensive re-validation before each dispatch (SPEC §6.2) |
| `$VAR` resolution order confusion | Low | Clear validator logic, unit tests for all resolution scenarios |
| Large WORKFLOW.md files slow to parse | Low | YAML parsing is fast; prompt body is just string slicing |
