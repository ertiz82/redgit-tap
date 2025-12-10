# GitLab Integration for RedGit

Code hosting with MRs, branches, and repository management.

## Features

- **Merge Requests**: Create, list, merge MRs
- **Branches**: Create, list, delete branches
- **Project Info**: View project details
- **Self-Hosted**: Works with GitLab.com and self-hosted instances
- **Auto-detection**: Automatically detects project from git remote

## Installation

```bash
rg install gitlab
```

## Setup

### Create Personal Access Token

1. Go to User Settings > Access Tokens
2. Create token with `api` scope
3. Copy the token

### Configuration

```yaml
integrations:
  gitlab:
    token: "glpat-xxx"              # Or GITLAB_TOKEN env var
    host: "https://gitlab.com"      # Or your self-hosted URL
    project_id: "namespace/project" # Auto-detected from git remote
    default_branch: "main"

active:
  code_hosting: gitlab
```

## Commands

### Project

```bash
# Show connection status
rg gitlab status

# List your projects
rg gitlab projects

# Show project info
rg gitlab info
```

### Merge Requests

```bash
# List open MRs
rg gitlab mrs

# List all MRs
rg gitlab mrs --state all

# Create MR from current branch
rg gitlab mr "Add new feature"

# Create MR with description
rg gitlab mr "Add feature" --body "Description here"

# Merge MR
rg gitlab merge 123
```

### Branches

```bash
# List branches
rg gitlab branches

# Create branch
rg gitlab branch feature/new-feature

# Delete branch
rg gitlab delete-branch feature/old-branch
```

## Self-Hosted GitLab

For self-hosted instances:

```yaml
integrations:
  gitlab:
    host: "https://gitlab.example.com"
    token: "glpat-xxx"
```

## Auto-Detection

The integration automatically detects `project_id` from your git remote:

```bash
# These are equivalent:
git@gitlab.com:namespace/project.git
https://gitlab.com/namespace/project.git
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITLAB_TOKEN` | Personal access token |
| `GITLAB_HOST` | GitLab instance URL |
| `GITLAB_PROJECT_ID` | Project path (namespace/project) |

## Token Scopes

Required scopes:
- `api` - Full API access
- Or more granular: `read_api`, `read_repository`, `write_repository`

## Troubleshooting

### "401 Unauthorized"
- Verify token is correct
- Check token hasn't expired
- Regenerate token if needed

### "404 Not Found"
- Check project_id is correct
- Verify you have access to the project
- Ensure project path includes namespace

### Self-hosted issues
- Verify host URL is correct
- Check SSL certificate is valid
- Ensure API is accessible from your network