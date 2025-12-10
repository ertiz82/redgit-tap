# Bitbucket Integration for RedGit

Code hosting with PRs, branches, and repository management.

## Features

- **Pull Requests**: Create, list, merge, decline PRs
- **Branches**: List repository branches
- **Repository Info**: View repo details
- **Workspaces**: List workspaces and repos
- **Auto-detection**: Automatically detects repo from git remote

## Installation

```bash
rg install bitbucket
```

## Setup

### Create App Password

1. Go to [Bitbucket Personal Settings > App passwords](https://bitbucket.org/account/settings/app-passwords/)
2. Create app password with permissions:
   - Account: Read
   - Repositories: Read, Write
   - Pull requests: Read, Write
3. Copy the app password

### Configuration

```yaml
integrations:
  bitbucket:
    username: "your-username"      # Or BITBUCKET_USERNAME env var
    app_password: "xxx"            # Or BITBUCKET_APP_PASSWORD env var
    workspace: "workspace-slug"    # Auto-detected from git remote
    repo_slug: "repo-name"         # Auto-detected from git remote
    default_branch: "main"

active:
  code_hosting: bitbucket
```

## Commands

### Repository

```bash
# Show connection status
rg bitbucket status

# List workspaces
rg bitbucket workspaces

# List repos in workspace
rg bitbucket repos

# Show repo info
rg bitbucket info
```

### Pull Requests

```bash
# List open PRs
rg bitbucket prs

# List all PRs
rg bitbucket prs --state all

# Create PR from current branch
rg bitbucket pr "Add new feature"

# Merge PR
rg bitbucket merge 123

# Decline PR
rg bitbucket decline 123
```

### Branches

```bash
# List branches
rg bitbucket branches
```

## Auto-Detection

The integration automatically detects `workspace` and `repo_slug` from your git remote:

```bash
# These are equivalent:
git@bitbucket.org:workspace/repo.git
https://bitbucket.org/workspace/repo.git
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BITBUCKET_USERNAME` | Bitbucket username |
| `BITBUCKET_APP_PASSWORD` | App password |
| `BITBUCKET_WORKSPACE` | Workspace slug |
| `BITBUCKET_REPO_SLUG` | Repository slug |

## App Password Permissions

Required permissions:
- **Account**: Read
- **Repositories**: Read, Write
- **Pull requests**: Read, Write

## Troubleshooting

### "401 Unauthorized"
- Verify username is correct
- Check app password is valid
- Regenerate app password if needed

### "404 Not Found"
- Check workspace/repo_slug are correct
- Verify you have access to the repository
- Ensure app password has required permissions

### Rate limiting
- Bitbucket has API rate limits
- Reduce request frequency if hitting limits