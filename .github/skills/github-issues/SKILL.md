---
name: github-issues
description: 'Create, read, update, and manage GitHub issues using the GitHub CLI (gh). Use when: creating issues, listing issues, viewing issue details, editing issues, managing labels, adding comments, closing/reopening issues, searching issues, working with assignees or milestones, or managing issue lifecycle.'
argument-hint: What issue operation do you need? (create, list, view, edit, comment, close, search, label)
---

# GitHub Issues Management

Manage GitHub issues using the GitHub CLI (`gh`). This skill covers the full issue lifecycle: creation, discovery, editing, commenting, labeling, and closure.

## Prerequisites

- GitHub CLI (`gh`) must be installed and authenticated (`gh auth status`)
- Working directory should be inside a GitHub repository, or specify `--repo owner/repo`

## Core Commands Reference

| Operation | Command |
|-----------|---------|
| List issues | `gh issue list` |
| View issue | `gh issue view <number>` |
| Create issue | `gh issue create` |
| Edit issue | `gh issue edit <number>` |
| Comment | `gh issue comment <number>` |
| Close issue | `gh issue close <number>` |
| Reopen issue | `gh issue reopen <number>` |
| Delete issue | `gh issue delete <number>` |
| Search issues | `gh issue list --search "<query>"` |

## Procedures

### Create an Issue

Basic creation:
```bash
gh issue create --title "Title" --body "Description"
```

With labels and assignees:
```bash
gh issue create \
  --title "Title" \
  --body "Description" \
  --label "bug,high-priority" \
  --assignee "@me"
```

From a file (useful for long descriptions):
```bash
gh issue create --title "Title" --body-file ./issue-body.md
```

Interactive mode (prompts for all fields):
```bash
gh issue create
```

### List Issues

Default (open issues, assigned to you):
```bash
gh issue list
```

All open issues:
```bash
gh issue list --limit 50
```

Filter by label:
```bash
gh issue list --label "bug"
```

Filter by assignee:
```bash
gh issue list --assignee "@me"
```

Filter by author:
```bash
gh issue list --author "username"
```

Filter by milestone:
```bash
gh issue list --milestone "v1.0"
```

View closed issues:
```bash
gh issue list --state closed
```

### View Issue Details

Basic view:
```bash
gh issue view <number>
```

View with comments:
```bash
gh issue view <number> --comments
```

View in browser:
```bash
gh issue view <number> --web
```

View specific repo:
```bash
gh issue view <number> --repo owner/repo
```

### Edit an Issue

Update title:
```bash
gh issue edit <number> --title "New Title"
```

Update body:
```bash
gh issue edit <number> --body "Updated description"
```

Update body from file:
```bash
gh issue edit <number> --body-file ./updated-body.md
```

Add/remove labels:
```bash
gh issue edit <number> --add-label "enhancement"
gh issue edit <number> --remove-label "wontfix"
```

Change assignees:
```bash
gh issue edit <number> --add-assignee "@me"
gh issue edit <number> --remove-assignee "username"
```

Change milestone:
```bash
gh issue edit <number> --milestone "v2.0"
```

### Add Comments

Add a comment:
```bash
gh issue comment <number> --body "Comment text"
```

Comment from file:
```bash
gh issue comment <number> --body-file ./comment.md
```

### Close and Reopen

Close an issue:
```bash
gh issue close <number> --reason "completed"
```

Close with reason (completed or not_planned):
```bash
gh issue close <number> --reason "not_planned" --comment "Closing as out of scope"
```

Reopen an issue:
```bash
gh issue reopen <number>
```

### Search Issues

Search by keyword:
```bash
gh issue list --search "memory leak"
```

Search with GitHub search syntax:
```bash
gh issue list --search "is:open label:bug author:@me"
gh issue list --search "is:closed created:>2024-01-01"
gh issue list --search "is:open no:assignee sort:created-asc"
```

Common search qualifiers:
- `is:open` / `is:closed` — state
- `label:<name>` — by label
- `author:<user>` — by author
- `assignee:<user>` — by assignee
- `milestone:<name>` — by milestone
- `created:>YYYY-MM-DD` — creation date
- `updated:>YYYY-MM-DD` — last update
- `no:assignee` — unassigned issues
- `sort:created-asc` / `sort:created-desc` — sort order
- `sort:updated-asc` / `sort:updated-desc` — sort order

### Manage Labels

List all labels in repo:
```bash
gh label list
```

Create a label:
```bash
gh label create "bug" --color "d73a4a" --description "Something isn't working"
```

Edit a label:
```bash
gh label edit "bug" --color "ff0000"
```

Delete a label:
```bash
gh label delete "old-label"
```

## Cross-Repo Operations

When working outside a cloned repo or targeting a different repo:
```bash
gh issue list --repo owner/repo
gh issue view 123 --repo owner/repo
gh issue create --repo owner/repo --title "Title" --body "Body"
```

## JSON Output for Scripting

Get structured output for programmatic use:
```bash
gh issue list --json number,title,state,labels,assignees
gh issue view <number> --json number,title,body,comments,labels
```

Filter with jq:
```bash
gh issue list --json number,title --jq '.[] | "\(.number): \(.title)"'
```

## Workflow Patterns

### Triage New Issues
```bash
# List unassigned open issues
gh issue list --search "is:open no:assignee" --limit 20

# View details of a specific issue
gh issue view <number> --comments

# Label and assign
gh issue edit <number> --add-label "needs-triage" --assignee "@me"
```

### Bulk Label Update
```bash
# Get all issues with a specific label
gh issue list --label "old-label" --json number --jq '.[].number' | \
  while read num; do
    gh issue edit "$num" --add-label "new-label" --remove-label "old-label"
  done
```

### Issue Template Creation
When creating issues from templates:
```bash
gh issue create --template "Bug Report"
gh issue create --template "Feature Request"
```

List available templates:
```bash
gh issue create --help  # shows --template option
```

## Error Handling

- **Not authenticated**: Run `gh auth login`
- **Permission denied**: Verify you have access to the repo
- **Rate limited**: Wait and retry; GitHub API has rate limits
- **Issue not found**: Verify the issue number and repo context

## Best Practices

1. **Use `--body-file`** for long descriptions to avoid shell escaping issues
2. **Quote labels with spaces**: `--label "needs triage"`
3. **Use `@me`** as shorthand for your own username
4. **Prefer `--json`** output when scripting or parsing results
5. **Always verify repo context** with `gh repo view` if unsure
6. **Use search qualifiers** for precise filtering instead of client-side filtering
