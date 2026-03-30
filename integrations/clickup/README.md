# ClickUp Integration for RedGit

Flexible task management integration for ClickUp - the all-in-one project management tool with workspaces, spaces, lists, and tasks.

## Features

- **Task Management**: Create, view, assign, and transition tasks
- **Workspace Support**: Manage tasks across multiple workspaces and teams
- **Lists & Spaces**: Organize tasks in spaces and lists
- **Team Collaboration**: View team members, assign tasks
- **Task Relationships**: Support for parent-child task relationships
- **Custom Fields**: Full support for custom fields and estimates
- **Advanced Search**: Search tasks by text across workspaces
- **Status Management**: View and transition task statuses

## Installation

```bash
rg install clickup
```

## Configuration

During installation, you'll be prompted for:

1. **API Token**: Generate at [ClickUp Settings > Apps > Integrations](https://app.clickup.com/settings/integrations/api)
2. **Workspace ID**: Your ClickUp workspace/team ID
3. **List ID**: Default list for creating new tasks
4. **Branch Pattern** (optional): How to format git branch names
5. **Issue Language** (optional): Language for AI-generated content

### Manual Configuration

Add to `.redgit/config.yaml`:

```yaml
integrations:
  clickup:
    api_token: "pk_xxxxx"  # Or use CLICKUP_API_TOKEN env var
    team_id: "123456"      # Workspace ID
    list_id: "789012"      # Default list ID
    branch_pattern: "feature/CU-{issue_key}-{description}"
    issue_language: "en"

active:
  task_management: clickup
```

### Getting Your IDs

1. **API Token**:
   - Go to ClickUp Settings
   - Click "Integrations" → "API"
   - Create or copy your Personal API Token

2. **Workspace ID**:
   - View in ClickUp API docs or use `rg clickup workspaces`
   - Run the installer to auto-detect if you have only one workspace

3. **List ID**:
   - Use `rg clickup lists` to find available lists
   - Copy the numeric ID of your preferred list

## Commands

### Workspace & Team

```bash
# List all accessible workspaces
rg clickup workspaces

# Show workspace members
rg clickup team

# Show integration status
rg clickup status
```

### Lists & Organization

```bash
# List all spaces and lists in workspace
rg clickup lists

# Show available statuses for current list
rg clickup statuses

# Show statuses for specific list
rg clickup statuses --list 789012
```

### Task Management

```bash
# List my active tasks
rg clickup issues

# List all tasks in the list
rg clickup issues --all

# Show single task details
rg clickup task 456789

# Create a new task
rg clickup create "Fix login bug"
rg clickup create "Add dark mode" --desc "Implement dark theme"
rg clickup create "Subtask" --parent 456789

# Assign task to team member
rg clickup assign 456789 "John"
rg clickup assign 456789 1  # By number from team list
```

### Search & Discovery

```bash
# Search tasks by text
rg clickup search "login bug"

# Search in specific list
rg clickup search "dark mode" --list 789012
```

## Branch Naming

Default pattern: `feature/CU-{issue_key}-{description}`

Available variables:
- `{issue_key}`: ClickUp task ID
- `{description}`: Cleaned task title

Example branches:
- `feature/CU-456789-fix-login-bug`
- `feature/CU-123456-add-dark-mode`

Custom patterns:
```yaml
branch_pattern: "feature/{issue_key}-{description}"     # CU-456789-fix-login
branch_pattern: "{issue_key}/{description}"             # 456789/fix-login
branch_pattern: "CU-{issue_key}-{description}"          # CU-456789-fix-login
```

## Git Workflow Integration

When you select a ClickUp task with `rg work`:

1. Branch is created from task ID using your pattern
2. Commits can reference the task
3. Task comments are added on commit (optional)
4. Task status can be auto-updated

## API Reference

ClickUp uses REST API v2. Key endpoints:

- `/user` - Current user info
- `/team/{team_id}/task` - Team/workspace tasks
- `/task/{task_id}` - Single task
- `/list/{list_id}/task` - List tasks
- `/task/{task_id}/comment` - Task comments
- `/team/{team_id}/space` - Workspaces and spaces
- `/space/{space_id}/list` - Lists in a space

See [ClickUp API Docs](https://clickup.com/api) for full reference.

## Environment Variables

- `CLICKUP_API_TOKEN`: API token (alternative to config file)

## Task Status Names

Common ClickUp statuses (customize in config):

```yaml
statuses:
  todo:        ["To Do", "Open", "Backlog"]
  in_progress: ["In Progress", "In Review", "Active"]
  done:        ["Complete", "Closed", "Done"]
```

Use these in `rg clickup task <id>` or when transitioning statuses.

## Comparison with Other Task Managers

| Feature | ClickUp | Linear | Jira |
|---------|---------|--------|------|
| Workspaces | Yes | Yes | Yes |
| Hierarchies | Spaces > Lists > Tasks | Team only | Projects |
| Custom Fields | Extensive | Limited | Extensive |
| Status Names | Custom | Fixed | Custom |
| Subtasks | Parent-child | Sub-issues | Subtasks |
| API | REST | GraphQL | REST |

## Troubleshooting

### "API token invalid"

1. Generate a new token at ClickUp Settings > API
2. Make sure you're using Personal API Token, not OAuth
3. Check the token has access to your workspace

### "Workspace not found"

Run `rg clickup workspaces` to see available workspaces and their IDs. Update `team_id` in config.

### "List not found"

Run `rg clickup lists` to see available lists and their IDs. Update `list_id` in config.

### "Task not found"

Verify the task ID is correct and that you have access to it in ClickUp. You can search for it with `rg clickup search "<task-name>"`.

### Rate Limiting

ClickUp has API rate limits. If requests fail:
- Wait a few moments and retry
- Reduce batch operations
- Check your API usage at ClickUp settings

## Advanced Usage

### Custom Status Names

Configure how RedGit maps statuses in `.redgit/config.yaml`:

```yaml
integrations:
  clickup:
    statuses:
      todo: ["To Do", "Backlog", "New Request"]
      in_progress: ["In Progress", "Code Review"]
      done: ["Complete", "Shipped", "Closed"]
```

### Language Settings

AI-generated content (if enabled) respects the `issue_language` setting:

```yaml
integrations:
  clickup:
    issue_language: "tr"  # Turkish
    # or: en, de, fr, es, pt, it, ja
```

## API Token Security

- Never commit your API token to git
- Use environment variable `CLICKUP_API_TOKEN` for CI/CD
- Rotate tokens regularly
- Use workspace-specific tokens if available

## Support

For issues or questions:
- Check ClickUp API documentation
- Review RedGit integration docs
- Search existing issues in the repository