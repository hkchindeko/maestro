## ADDED Requirements

### Requirement: Workspace layout
> Source: SPEC §9.1

The workspace manager SHALL organize workspaces under a configured root directory:
- Workspace root: `workspace.root` (normalized absolute path)
- Per-issue workspace path: `<workspace.root>/<sanitized_issue_identifier>`

Workspaces SHALL be reused across runs for the same issue.
Successful runs SHALL NOT auto-delete workspaces.

**Tests:**
- Deterministic workspace path per issue identifier
- Workspace path is under configured workspace root

### Requirement: Workspace key sanitization
> Source: SPEC §4.2, §9.5

The workspace key SHALL be derived from `issue.identifier` by replacing any character not in `[A-Za-z0-9._-]` with `_`.

**Tests:**
- Sanitization replaces special characters with underscore
- Valid characters (`[A-Za-z0-9._-]`) are preserved
- Empty identifier produces empty or minimal key

### Requirement: Workspace creation and reuse
> Source: SPEC §9.2

The workspace manager SHALL:
1. Sanitize the issue identifier to a workspace key
2. Compute the workspace path under the workspace root
3. Ensure the workspace path exists as a directory
4. Mark `created_now=true` only if the directory was created during this call
5. If `created_now=true`, run the `after_create` hook if configured

Existing workspace directories SHALL be reused without modification.

**Tests:**
- Missing workspace directory is created
- Existing workspace directory is reused
- `after_create` hook runs only on new workspace creation

### Requirement: Workspace lifecycle hooks
> Source: SPEC §9.4

The workspace manager SHALL support these hooks:
- `after_create` — runs only when a workspace directory is newly created; failure aborts workspace creation
- `before_run` — runs before each agent attempt; failure aborts the current attempt
- `after_run` — runs after each agent attempt; failure is logged but ignored
- `before_remove` — runs before workspace deletion; failure is logged but ignored

Hook execution SHALL:
- Use the workspace directory as `cwd`
- Apply `hooks.timeout_ms` timeout (default 60000 ms)
- Log hook start, failures, and timeouts

**Tests:**
- `after_create` hook runs only on new workspace creation
- `before_run` hook runs before each attempt and failure/timeouts abort the current attempt
- `after_run` hook runs after each attempt and failure/timeouts are logged and ignored
- `before_remove` hook runs on cleanup and failures/timeouts are ignored

### Requirement: Workspace path safety
> Source: SPEC §9.5

The workspace manager SHALL enforce these safety invariants:

Invariant 1: Agent cwd must equal workspace path.
- Before launching the coding-agent subprocess, validate `cwd == workspace_path`

Invariant 2: Workspace path MUST stay inside workspace root.
- Normalize both paths to absolute
- Require `workspace_path` to have `workspace_root` as a prefix directory
- Reject any path outside the workspace root

Invariant 3: Workspace key is sanitized.
- Only `[A-Za-z0-9._-]` allowed in workspace directory names
- Replace all other characters with `_`

**Tests:**
- Workspace path sanitization and root containment invariants are enforced before agent launch
- Agent launch uses the per-issue workspace path as cwd and rejects out-of-root paths

### Requirement: Workspace cleanup
> Source: SPEC §8.6, §9.4

The workspace manager SHALL support workspace cleanup for terminal issues:
- Run `before_remove` hook if configured (failure logged and ignored)
- Remove the workspace directory
- If the directory does not exist, cleanup is a no-op

**Tests:**
- Terminal workspace is removed after cleanup
- `before_remove` hook runs before deletion
- Missing workspace directory is handled gracefully

### Requirement: Non-directory path handling
> Source: SPEC §17.2

If a non-directory path exists at the workspace location, the workspace manager SHALL handle it safely (replace or fail per implementation policy).

**Tests:**
- Existing non-directory path at workspace location is handled safely
