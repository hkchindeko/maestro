## 1. Path safety utilities

- [x] 1.1 Implement `sanitize_key(identifier: str) -> str` replacing non `[A-Za-z0-9._-]` with `_` per SPEC §9.5
- [x] 1.2 Implement `is_path_under_root(path: Path, root: Path) -> bool` with resolved path comparison
- [x] 1.3 Implement `validate_workspace_path(workspace_path: Path, workspace_root: Path)` raising error if not under root
- [x] 1.4 Write unit tests for sanitization (special chars, valid chars, empty)
- [x] 1.5 Write unit tests for path containment (under root, outside root, symlink resolution)

## 2. Hook execution

- [x] 2.1 Implement `run_hook(script: str, cwd: Path, timeout_ms: int) -> HookResult` using `subprocess.run`
- [x] 2.2 Handle hook success (return code 0) with captured stdout/stderr
- [x] 2.3 Handle hook failure (non-zero return code) with error details
- [x] 2.4 Handle hook timeout (`subprocess.TimeoutExpired`) with truncated output in logs
- [x] 2.5 Write unit tests for hook success, failure, and timeout

## 3. Workspace manager

- [x] 3.1 Implement `WorkspaceManager` class with `workspace_root` and `hooks_config`
- [x] 3.2 Implement `create_for_issue(identifier: str) -> WorkspaceResult` with sanitization and directory creation
- [x] 3.3 Implement `after_create` hook execution only when directory is newly created
- [x] 3.4 Implement `before_run` hook execution (fatal on failure)
- [x] 3.5 Implement `after_run` hook execution (logged and ignored on failure)
- [x] 3.6 Implement `before_remove` hook execution (logged and ignored on failure)
- [x] 3.7 Implement `cleanup_for_issue(identifier: str)` removing workspace directory
- [x] 3.8 Handle existing non-directory path at workspace location safely
- [x] 3.9 Write unit tests for workspace lifecycle (create, reuse, cleanup)

## 4. Error handling

- [x] 4.1 Define `WorkspaceError` base exception class
- [x] 4.2 Define `WorkspacePathError` for path containment violations
- [x] 4.3 Define `HookTimeoutError` for hook timeout with truncated output
- [x] 4.4 Define `HookExecutionError` for hook failure with return code and output
- [x] 4.5 Write unit tests for each error class

## 5. Integration tests

- [x] 5.1 Test full workspace create → before_run → after_run → cleanup lifecycle
- [x] 5.2 Test workspace reuse (directory already exists, no after_create hook)
- [x] 5.3 Test after_create hook failure aborts workspace creation
- [x] 5.4 Test before_run hook failure aborts run attempt
- [x] 5.5 Test after_run hook failure is logged and ignored
- [x] 5.6 Test workspace path safety validation before agent launch
