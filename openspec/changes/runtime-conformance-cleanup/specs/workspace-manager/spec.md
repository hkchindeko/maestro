## MODIFIED Requirements

### Requirement: Workspace layout
> Source: SPEC §5.3.3, §6.1

The workspace manager SHALL organize workspaces under a configured root directory:
- Workspace root: `workspace.root` (normalized absolute path)
- Default: `<system-temp>/symphony_workspaces` (applied at config model level per SPEC §6.1)
- Per-issue workspace path: `<workspace.root>/<sanitized_issue_identifier>`

The default workspace root SHALL be applied by the config model (`WorkspaceConfig.root`), not deferred to the runtime builder.

Workspaces SHALL be reused across runs for the same issue.
Successful runs SHALL NOT auto-delete workspaces.

**Tests:**
- `WorkspaceConfig.root` defaults to `<tempdir>/symphony_workspaces` when not explicitly set
- `WorkspaceConfig.root` can be overridden by workflow YAML
- `build_workspace_manager()` uses the resolved config value directly without re-applying the default