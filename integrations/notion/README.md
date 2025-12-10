# Notion Integration for RedGit

Use Notion databases as task boards for your development workflow.

## Features

- **Database Tasks**: Use any Notion database as a task board
- **Status Tracking**: Map Notion status to workflow states
- **Assignees**: Assign tasks to workspace members
- **Comments**: Add commit info as comments
- **Search**: Find tasks by title

## Installation

```bash
rg install notion
```

## Setup

1. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Share your database with the integration
3. Get the database ID from the URL

### Configuration

```yaml
integrations:
  notion:
    api_key: "secret_xxx"  # Or NOTION_API_KEY env var
    database_id: "abc123..."
    project_key: "PROJ"
    status_property: "Status"
    assignee_property: "Assignee"

active:
  task_management: notion
```

## Database Setup

Your Notion database should have:

| Property | Type | Description |
|----------|------|-------------|
| Name | Title | Task title (required) |
| Status | Status | Task status |
| Assignee | Person | Assigned member |
| Points | Number | Story points (optional) |
| Sprint | Select | Sprint name (optional) |

## Commands

```bash
# List databases
rg notion databases

# List my tasks
rg notion issues

# List all tasks
rg notion issues --all

# Show team members
rg notion team

# Create task
rg notion create "Fix login bug"
rg notion create "Add feature" --desc "Details..." --points 3

# Assign task
rg notion assign NOTION-abc123 "John"

# Unassign
rg notion unassign NOTION-abc123

# Search
rg notion search "login"

# Status
rg notion status
```

## How It Works

1. Tasks are stored as Notion database pages
2. Issue IDs are formatted as `{project_key}-{page_id_short}`
3. Status changes update the Status property
4. Commits can add comments to pages

## Limitations

- Notion doesn't have native sprints (use Select property)
- Issue types are not supported (all items are "tasks")
- Rich text descriptions limited to plain text

## Troubleshooting

### "Database not found"
- Ensure the database is shared with your integration
- Check the database ID is correct

### "Unauthorized"
- Verify your integration token
- Make sure the integration has access to the workspace