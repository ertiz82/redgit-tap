# GitLab CI Integration for RedGit

Manage pipelines, trigger jobs, view status and logs.

## Features

- **Pipeline Management**: List, trigger, cancel pipelines
- **Job Control**: View jobs, retry failed, play manual jobs
- **Logs Access**: View job logs directly
- **Schedules**: List pipeline schedules
- **Self-hosted Support**: Works with GitLab.com and self-hosted

## Installation

```bash
rg install gitlab-ci
```

## Setup

### Create Token

1. Go to [gitlab.com/-/profile/personal_access_tokens](https://gitlab.com/-/profile/personal_access_tokens)
2. Create token with scope:
   - `api` - Full API access
3. Copy the token

### Configuration

```yaml
integrations:
  gitlab-ci:
    token: "glpat-xxx"       # Or GITLAB_TOKEN env var
    project_id: "user/repo"  # Auto-detected
    base_url: "https://gitlab.com"  # For self-hosted

active:
  ci_cd: gitlab-ci
```

## Commands

### Pipelines

```bash
# List recent pipelines
rg gitlab-ci pipelines

# List pipelines for branch
rg gitlab-ci pipelines --branch main

# List only failed pipelines
rg gitlab-ci pipelines --status failed

# Show pipeline details
rg gitlab-ci pipeline 12345
```

### Trigger

```bash
# Trigger pipeline on current branch
rg gitlab-ci trigger

# Trigger on specific branch
rg gitlab-ci trigger --branch main

# Trigger with variables
rg gitlab-ci trigger --var DEPLOY_ENV=staging
```

### Jobs

```bash
# List jobs for a pipeline
rg gitlab-ci jobs 12345

# Retry a failed job
rg gitlab-ci retry-job 67890

# Play a manual job
rg gitlab-ci play 67890

# View job logs
rg gitlab-ci logs 67890
```

### Re-run

```bash
# Retry entire pipeline
rg gitlab-ci retry 12345
```

### Cancel

```bash
# Cancel running pipeline
rg gitlab-ci cancel 12345
```

### Schedules

```bash
# List pipeline schedules
rg gitlab-ci schedules
```

## Status Icons

| Status | Meaning |
|--------|---------|
| `pending` | Queued, waiting to run |
| `running` | Currently executing |
| `success` | Completed successfully |
| `failed` | Completed with failures |
| `cancelled` | Manually cancelled |
| `skipped` | Skipped |
| `manual` | Waiting for manual action |

## Self-Hosted GitLab

For self-hosted GitLab instances:

```yaml
integrations:
  gitlab-ci:
    base_url: "https://gitlab.mycompany.com"
    token: "glpat-xxx"
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITLAB_TOKEN` | Personal access token |
| `GITLAB_PROJECT_ID` | Project ID or path |
| `GITLAB_URL` | GitLab instance URL |

## Troubleshooting

### "401 Unauthorized"
- Check token has `api` scope
- Token may have expired

### "404 Not Found"
- Check project_id is correct
- Verify you have access to the project

### Cannot trigger pipeline
- Ensure `.gitlab-ci.yml` exists in repo
- Check branch exists