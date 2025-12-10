# Trello Integration for RedGit

Kanban board task management with Trello cards and lists.

## Features

- **Card Management**: Create, view, move, archive cards
- **Lists as Status**: Use board lists as workflow states
- **Labels**: Add colored labels to cards
- **Checklists**: Full checklist support
- **Team Collaboration**: View members, assign cards
- **Search**: Find cards by name

## Installation

```bash
rg install trello
```

## Setup

1. Get API Key from [trello.com/app-key](https://trello.com/app-key)
2. Generate Token (link on the API key page)
3. Get Board ID from your board URL

### Configuration

```yaml
integrations:
  trello:
    api_key: "xxx"  # Or TRELLO_API_KEY env var
    token: "yyy"    # Or TRELLO_TOKEN env var
    board_id: "abc123"
    project_key: "PROJ"

active:
  task_management: trello
```

## Commands

### Boards & Lists

```bash
# List your boards
rg trello boards

# List board columns
rg trello lists

# List labels
rg trello labels
```

### Cards

```bash
# List my cards
rg trello issues

# List all board cards
rg trello issues --all

# Create card
rg trello create "Fix login bug"
rg trello create "Add feature" --desc "Details..." --list "In Progress"

# Move card to list
rg trello move TRELLO-abc123 "Done"

# Archive card
rg trello archive TRELLO-abc123

# Search
rg trello search "login"
```

### Assignment

```bash
# List board members
rg trello team

# List unassigned cards
rg trello unassigned

# Assign card
rg trello assign TRELLO-abc123 "John"

# Unassign
rg trello unassign TRELLO-abc123
```

### Labels & Checklists

```bash
# Add label
rg trello add-label TRELLO-abc123 "urgent"

# Show checklists
rg trello checklists TRELLO-abc123

# Create checklist
rg trello add-checklist TRELLO-abc123 "Tasks" --items "Item 1,Item 2,Item 3"
```

### Status

```bash
rg trello status
```

## How Lists Work

Trello uses lists as columns (status):

```
Board
├── Backlog
├── To Do
├── In Progress
├── Review
└── Done
```

Use `rg trello move` to change card status by moving to a list.

## ID Format

Card IDs are formatted as `{project_key}-{trello_id}`:
- `TRELLO-abc123def456`
- `PROJ-xyz789`

## Checklists

Trello checklists are great for breaking down tasks:

```bash
# Create checklist with items
rg trello add-checklist TRELLO-abc "Deploy Steps" \
  --items "Build,Test,Deploy,Verify"

# View checklists
rg trello checklists TRELLO-abc
```

## Limitations

- No native sprint support (use lists or labels)
- Story points not native (use Power-Ups or description)
- Issue types not supported (all items are cards)

## Troubleshooting

### "Board not found"
- Verify board_id from your board URL
- Check you have access to the board

### "Invalid token"
- Regenerate token from the API key page
- Make sure token has full permissions