# Bitbucket Pipelines Integration for RedGit

Manage pipelines, trigger builds, view status and logs.

## Features

- **Pipeline Management**: List, trigger, stop pipelines
- **Step Details**: View pipeline steps and their status
- **Logs Access**: View step logs
- **Custom Pipelines**: Trigger custom pipeline configurations
- **Auto-detection**: Detects workspace/repo from git remote

## Installation

```bash
rg install bitbucket-pipelines
```

## Setup

### Create App Password

1. Go to [bitbucket.org/account/settings/app-passwords](https://bitbucket.org/account/settings/app-passwords/)
2. Click "Create app password"
3. Set permissions:
   - Repository: Read
   - Pipelines: Read, Write
4. Copy the password

### Configuration

```yaml
integrations:
  bitbucket-pipelines:
    username: "myuser"          # Bitbucket username
    app_password: "xxx"         # Or BITBUCKET_APP_PASSWORD env var
    workspace: "myworkspace"    # Auto-detected
    repo_slug: "myrepo"         # Auto-detected

active:
  ci_cd: bitbucket-pipelines
```

## Commands

### Pipelines

```bash
# List recent pipelines
rg bitbucket-pipelines pipelines

# List pipelines for branch
rg bitbucket-pipelines pipelines --branch main

# Show pipeline details
rg bitbucket-pipelines pipeline <uuid>
```

### Steps

```bash
# List steps for a pipeline
rg bitbucket-pipelines steps <pipeline-uuid>

# View step logs
rg bitbucket-pipelines logs <pipeline-uuid> <step-uuid>
```

### Trigger

```bash
# Trigger pipeline on current branch
rg bitbucket-pipelines trigger

# Trigger on specific branch
rg bitbucket-pipelines trigger --branch main

# Trigger custom pipeline
rg bitbucket-pipelines trigger --custom deploy-prod

# Trigger with variables
rg bitbucket-pipelines trigger --var ENV=staging
```

### Stop

```bash
# Stop a running pipeline
rg bitbucket-pipelines stop <uuid>
```

## Status Icons

| Status | Meaning |
|--------|---------|
| `pending` | Queued, waiting to run |
| `running` | Currently executing |
| `success` | Completed successfully |
| `failed` | Completed with failures |
| `cancelled` | Manually stopped |

## Custom Pipelines

Define custom pipelines in `bitbucket-pipelines.yml`:

```yaml
pipelines:
  custom:
    deploy-prod:
      - step:
          name: Deploy to Production
          script:
            - ./deploy.sh prod
```

Trigger:
```bash
rg bitbucket-pipelines trigger --custom deploy-prod
```

## Pipeline Variables

Pass variables when triggering:

```bash
rg bitbucket-pipelines trigger --var ENV=staging --var DEBUG=true
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BITBUCKET_USERNAME` | Bitbucket username |
| `BITBUCKET_APP_PASSWORD` | App password |
| `BITBUCKET_WORKSPACE` | Workspace slug |
| `BITBUCKET_REPO` | Repository slug |

## Troubleshooting

### "401 Unauthorized"
- Check username and app password
- Verify app password has correct permissions

### "404 Not Found"
- Check workspace and repo_slug
- Verify pipelines are enabled for repository

### Cannot trigger pipeline
- Ensure `bitbucket-pipelines.yml` exists
- Check branch exists
- Verify pipelines are enabled in repository settings