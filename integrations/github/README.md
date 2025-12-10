# GitHub Integration for RedGit

Code hosting with PRs, branches, and repository management.

## Features

- **Pull Requests**: Create, list, merge PRs
- **Branches**: Create, list, delete branches
- **Repository Info**: View repo details and settings
- **Auto-detection**: Automatically detects repo from git remote

## Installation

```bash
rg install github
```

## Setup

### Create Personal Access Token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Generate new token (classic) with `repo` scope
3. Copy the token

### Configuration

```yaml
integrations:
  github:
    token: "ghp_xxx"    # Or GITHUB_TOKEN env var
    owner: "username"   # Auto-detected from git remote
    repo: "myrepo"      # Auto-detected from git remote
    default_branch: "main"

active:
  code_hosting: github
```

## Commands

### Repository

```bash
# Show connection status
rg github status

# List your repositories
rg github repos

# Show repo info
rg github info
```

### Pull Requests

```bash
# List open PRs
rg github prs

# List all PRs
rg github prs --state all

# Create PR from current branch
rg github pr "Add new feature"

# Create PR with body
rg github pr "Add feature" --body "Description here"

# Merge PR
rg github merge 123
```

### Branches

```bash
# List branches
rg github branches

# Create branch
rg github branch feature/new-feature

# Delete branch
rg github delete-branch feature/old-branch
```

## Auto-Detection

The integration automatically detects `owner` and `repo` from your git remote:

```bash
# These are equivalent:
git@github.com:owner/repo.git
https://github.com/owner/repo.git
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | Personal access token |
| `GITHUB_OWNER` | Repository owner |
| `GITHUB_REPO` | Repository name |

## Token Scopes

Required scopes for full functionality:
- `repo` - Full repository access
- `read:user` - Read user profile (optional)

## Troubleshooting

### "Bad credentials"
- Verify token is correct
- Check token hasn't expired
- Regenerate token if needed

### "Not found"
- Check owner/repo are correct
- Verify you have access to the repository
- Ensure token has `repo` scope

### Auto-detection not working
- Make sure you have a git remote named "origin"
- Set owner/repo manually in config