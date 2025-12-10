# Linear Integration for RedGit

Modern issue tracking integration for Linear - the issue tracker built for modern software teams.

## Features

- **Issue Management**: Create, view, assign, and transition issues
- **Cycle Support**: Work with Linear's cycles (similar to sprints)
- **Team Collaboration**: View team members, assign issues
- **Project Support**: Access Linear projects
- **Sub-issues**: Parent-child issue relationships
- **Labels & Estimates**: Full support for labeling and estimation
- **Workflow States**: View and use custom workflow states
- **Issue Relations**: Link issues with blocks, related, duplicate

## Installation

```bash
rg install linear
```

## Configuration

During installation, you'll be prompted for:

1. **API Key**: Generate at [Linear Settings > API](https://linear.app/settings/api)
2. **Team Key**: Your team identifier (e.g., `ENG`, `PROD`)

### Manual Configuration

Add to `.redgit/config.yaml`:

```yaml
integrations:
  linear:
    api_key: "lin_api_xxxxx"  # Or use LINEAR_API_KEY env var
    team_key: "ENG"
    branch_pattern: "feature/{issue_id}-{description}"

active:
  task_management: linear
```

## Commands

### Team & Issues

```bash
# List accessible teams
rg linear teams

# List my active issues
rg linear issues

# List all team issues
rg linear issues --all

# Show team members
rg linear team

# List unassigned issues
rg linear unassigned

# Search issues
rg linear search "login bug"
```

### Issue Operations

```bash
# Create an issue
rg linear create "Fix login bug"
rg linear create "Add dark mode" --desc "Implement dark theme" --points 3
rg linear create "Sub-task" --parent ENG-100

# Assign/unassign
rg linear assign ENG-123 "John"
rg linear assign ENG-123 1  # By number from team list
rg linear unassign ENG-123

# Set estimate
rg linear estimate ENG-123 5
```

### Cycles (Sprints)

```bash
# Show active cycle
rg linear cycle

# List all cycles
rg linear cycles

# Show backlog
rg linear backlog

# Move issues to cycle
rg linear move-cycle ENG-1,ENG-2,ENG-3
rg linear move-cycle ENG-123 --cycle <cycle-id>
```

### Issue Relations

```bash
# Link issues
rg linear link ENG-123 ENG-456 --type blocks
rg linear link ENG-123 ENG-456 --type related

# Show issue links
rg linear links ENG-123

# Show child issues
rg linear children ENG-100
```

### Workflow & Labels

```bash
# Show workflow states
rg linear states

# Show available labels
rg linear labels

# Show projects
rg linear projects
```

### Status

```bash
# Check integration status
rg linear status
```

## Branch Naming

Default pattern: `feature/{issue_id}-{description}`

Available variables:
- `{issue_id}`: Full issue ID (e.g., ENG-123)
- `{issue_number}`: Just the number (e.g., 123)
- `{description}`: Cleaned issue title
- `{team_key}`: Team key (e.g., ENG)

Example branches:
- `feature/ENG-123-fix-login-bug`
- `feature/ENG-456-add-dark-mode`

## Git Workflow Integration

When you select a Linear issue with `rg work`:

1. Branch is created from issue ID
2. Commits can reference the issue
3. Issue comments are added on commit (optional)
4. Issue status can be auto-updated

## API Reference

Linear uses GraphQL API. Key endpoints:

- Issues, Comments, Projects
- Cycles (sprints), Teams, Users
- Workflow states, Labels
- Issue relations

See [Linear API Docs](https://developers.linear.app/docs/graphql/working-with-the-graphql-api) for details.

## Environment Variables

- `LINEAR_API_KEY`: API key (alternative to config file)

## Comparison with Jira

| Feature | Linear | Jira |
|---------|--------|------|
| Sprints | Cycles | Sprints |
| Issue Types | Single type | Multiple types |
| API | GraphQL | REST |
| Boards | Views | Boards |
| Story Points | Estimates | Story Points |

## Troubleshooting

### "Team not found"

Make sure the `team_key` matches exactly (case-sensitive). Run `rg linear teams` to see available teams.

### "API key invalid"

1. Generate a new key at Linear Settings > API
2. Make sure it's a Personal API key, not an OAuth token
3. Check the key has access to your workspace

### Rate Limiting

Linear has API rate limits. If you hit them:
- Wait a few minutes
- Reduce batch operations
- Use pagination for large queries