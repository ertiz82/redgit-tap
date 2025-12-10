# Asana Integration for RedGit

Project and task management integration for Asana.

## Features

- **Task Management**: Create, view, assign, complete tasks
- **Sections as Status**: Use project sections as workflow states
- **Subtasks**: Full subtask support
- **Tags**: Add tags to tasks
- **Team Collaboration**: View members, assign tasks
- **Search**: Find tasks by name

## Installation

```bash
rg install asana
```

## Setup

1. Generate Personal Access Token at [Asana Developer Console](https://app.asana.com/0/developer-console)
2. Get your Project ID from the project URL

### Configuration

```yaml
integrations:
  asana:
    api_key: "1/xxx:yyy"  # Or ASANA_API_KEY env var
    workspace_id: "123456"  # Auto-detected if empty
    project_id: "789012"
    project_key: "PROJ"

active:
  task_management: asana
```

## Commands

### Workspace & Projects

```bash
# List workspaces
rg asana workspaces

# List projects
rg asana projects

# List sections (statuses)
rg asana sections
```

### Tasks

```bash
# List my tasks
rg asana issues

# List all project tasks
rg asana issues --all

# Create task
rg asana create "Fix login bug"
rg asana create "Add feature" --notes "Details..." --section "In Progress"

# Move task to section
rg asana move ASANA-123 "Done"

# Complete task
rg asana complete ASANA-123

# Search
rg asana search "login"
```

### Assignment

```bash
# List team members
rg asana team

# List unassigned tasks
rg asana unassigned

# Assign task
rg asana assign ASANA-123 "John"
```

### Subtasks & Tags

```bash
# Show subtasks
rg asana subtasks ASANA-123

# Add subtask
rg asana add-subtask ASANA-123 "Sub-item"

# Add tag
rg asana tag ASANA-123 "urgent"
```

### Status

```bash
rg asana status
```

## How Sections Work

Asana uses sections within projects as status columns:

```
Project
├── Backlog
├── To Do
├── In Progress
├── Review
└── Done
```

Use `rg asana move` to change task status by moving to a section.

## ID Format

Task IDs are formatted as `{project_key}-{asana_gid}`:
- `ASANA-1234567890`
- `PROJ-9876543210`

## Limitations

- No native sprint support (use sections or tags)
- Story points not native (use custom fields)
- Issue types not supported (all items are tasks)

## Troubleshooting

### "Project not found"
- Verify project_id is correct
- Check you have access to the project

### "Workspace not found"
- Run `rg asana workspaces` to list available workspaces
- Set workspace_id in config