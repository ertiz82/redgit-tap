# GitHub Actions Integration for RedGit

Manage workflows, trigger runs, view status and logs.

## Features

- **Workflow Management**: List and trigger workflows
- **Run Status**: View workflow run status and history
- **Job Details**: See individual job status and logs
- **Re-runs**: Retry failed workflows or jobs
- **Auto-detection**: Automatically detects repo from git remote

## Installation

```bash
rg install github-actions
```

## Setup

### Create Token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Generate token with scopes:
   - `repo` - Full repository access
   - `workflow` - Workflow access
3. Copy the token

### Configuration

```yaml
integrations:
  github-actions:
    token: "ghp_xxx"    # Or GITHUB_TOKEN env var
    owner: "username"   # Auto-detected
    repo: "myrepo"      # Auto-detected

active:
  ci_cd: github-actions
```

## Commands

### Workflows

```bash
# List workflows
rg github-actions workflows

# Show workflow details
rg github-actions workflow ci.yml
```

### Runs

```bash
# List recent runs
rg github-actions runs

# List runs for branch
rg github-actions runs --branch main

# List only failed runs
rg github-actions runs --status failed

# Show run details
rg github-actions run 12345678

# Show run jobs
rg github-actions jobs 12345678
```

### Trigger

```bash
# Trigger workflow
rg github-actions trigger ci.yml

# Trigger on specific branch
rg github-actions trigger ci.yml --branch feature/test

# Trigger with inputs
rg github-actions trigger deploy.yml --input environment=staging
```

### Re-run

```bash
# Re-run entire workflow
rg github-actions rerun 12345678

# Re-run only failed jobs
rg github-actions rerun 12345678 --failed-only
```

### Cancel

```bash
# Cancel running workflow
rg github-actions cancel 12345678
```

## Status Icons

| Status | Meaning |
|--------|---------|
| `pending` | Queued, waiting to run |
| `running` | Currently executing |
| `success` | Completed successfully |
| `failed` | Completed with failures |
| `cancelled` | Manually cancelled |

## Workflow Dispatch

To trigger workflows manually, they must have `workflow_dispatch` trigger:

```yaml
# .github/workflows/deploy.yml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy'
        required: true
        default: 'staging'
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | Personal access token |
| `GITHUB_OWNER` | Repository owner |
| `GITHUB_REPO` | Repository name |

## Troubleshooting

### "Resource not accessible"
- Check token has `workflow` scope
- Verify repository access

### "Workflow not found"
- Check workflow file exists in `.github/workflows/`
- Use workflow filename (e.g., `ci.yml`)

### Cannot trigger workflow
- Ensure workflow has `workflow_dispatch` trigger
- Check branch exists