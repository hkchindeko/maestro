## Problem

SPEC §9 defines the workspace management and safety requirements:

1. **Workspace layout** — per-issue workspace paths under a configured root (§9.1)
2. **Workspace creation and reuse** — sanitize identifiers, create directories, run `after_create` hook (§9.2)
3. **Workspace hooks** — `after_create`, `before_run`, `after_run`, `before_remove` with timeout enforcement (§9.4)
4. **Safety invariants** — agent cwd must equal workspace path, workspace path must stay under root, workspace keys sanitized (§9.5)

The `workflow-config` change provides config models including `WorkspaceConfig` and `HooksConfig`, but no workspace management implementation exists yet. This is a foundational layer needed before the agent runner can dispatch work.

## What Changes

- Implement `WorkspaceManager` with per-issue workspace creation and reuse
- Implement workspace key sanitization (`[A-Za-z0-9._-]` only, replace others with `_`)
- Implement path safety checks (workspace path must be under workspace root)
- Implement workspace lifecycle hooks (`after_create`, `before_run`, `after_run`, `before_remove`) with timeout enforcement
- Implement workspace cleanup for terminal issues
- Implement typed error classes for workspace failures
- Write unit tests for sanitization, path safety, hook execution, and lifecycle

## Capabilities

### New Capabilities

- `workspace-create`: Create or reuse per-issue workspace directories under configured root
- `workspace-hooks`: Execute lifecycle hooks with timeout enforcement
- `workspace-safety`: Enforce path containment and key sanitization invariants
- `workspace-cleanup`: Remove workspaces for terminal issues

### Modified Capabilities

None — this is a new capability.

## Impact

- **New modules:**
  - `src/maestro/workspace/manager.py` — `WorkspaceManager` with create/reuse/cleanup
  - `src/maestro/workspace/hooks.py` — Shell hook execution with timeout
  - `src/maestro/workspace/safety.py` — Path containment and key sanitization
- **Depends on:** `workflow-config` change (for `WorkspaceConfig`, `HooksConfig`)
- **No breaking changes**
