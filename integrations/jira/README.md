# Jira Integration for RedGit

Full-featured Jira Cloud integration with Scrum/Kanban support.

## Features

- Create and manage Jira issues from commits
- Automatic sprint assignment
- Status transitions based on workflow
- Issue linking and epic hierarchies
- Bulk operations
- Story points management
- User assignment

## Installation

```bash
rg integration install jira
```

## Configuration

```yaml
integrations:
  jira:
    site: "https://your-domain.atlassian.net"
    email: "you@example.com"
    # API token: Use JIRA_API_TOKEN env var or token field
    project_key: "PROJ"
    board_type: "scrum"  # scrum, kanban, none

    # Optional settings
    board_id: 1  # auto-detected if empty
    story_points_field: "customfield_10016"
    issue_language: "tr"  # Language for issue titles
    transition_strategy: "auto"  # auto or ask

    # Status mappings
    statuses:
      after_propose: ["In Progress", "Devam Ediyor"]
      after_push: ["Done", "Tamamlandı"]
```

## Environment Variables

- `JIRA_API_TOKEN`: Jira API token (recommended)

## Transition Strategies

### Auto (default)
Automatically transitions issues based on status mappings:
- `rg propose` → moves to `after_propose` status
- `rg push` → moves to `after_push` status

### Ask
Prompts user to select target status for each issue from available transitions.

## Commands

```bash
# Workflow
rg propose          # Creates issues, moves to "In Progress"
rg push             # Pushes to remote, moves to "Done"

# Manual transitions
rg task transition PROJ-123 "In Progress"
rg task transition PROJ-123 "Done"
```

## API Features

### Issue Management
- Create issues with parent (epic/story)
- Link issues (blocks, relates, duplicates)
- Add comments
- Assign users
- Set story points

### Sprint Management
- Get active sprint
- Create sprints
- Add issues to sprints
- Start/close sprints

### Bulk Operations
- Create multiple issues
- Assign multiple issues
- Transition multiple issues

## License

MIT