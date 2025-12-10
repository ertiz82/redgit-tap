# Drone CI Integration for RedGit

Manage builds, trigger pipelines, view status and logs.

## Features

- **Build Management**: List, trigger, cancel builds
- **Stage Details**: View build stages and their status
- **Logs Access**: View step logs
- **Promotions**: Promote builds to different environments
- **Approvals**: Approve/decline blocked stages
- **Auto-detection**: Detects owner/repo from git remote

## Installation

```bash
rg install drone-ci
```

## Setup

### Get API Token

1. Log into your Drone server
2. Click your profile icon → Token
3. Copy the token

### Configuration

```yaml
integrations:
  drone-ci:
    server: "https://drone.company.com"
    token: "your-token"       # Or DRONE_TOKEN env var
    owner: "myorg"            # Auto-detected
    repo: "myrepo"            # Auto-detected

active:
  ci_cd: drone-ci
```

## Commands

### Builds

```bash
# List recent builds
rg drone-ci builds

# List builds for branch
rg drone-ci builds --branch main

# Show build details
rg drone-ci build 123
```

### Stages

```bash
# List stages for a build
rg drone-ci stages 123
```

### Trigger

```bash
# Trigger build on current branch
rg drone-ci trigger

# Trigger on specific branch
rg drone-ci trigger --branch main

# Trigger with parameters
rg drone-ci trigger --param DEPLOY=true
```

### Logs

```bash
# View build logs (stage 1, step 1)
rg drone-ci logs 123

# View specific stage/step logs
rg drone-ci logs 123 --stage 2 --step 1
```

### Restart

```bash
# Restart a build
rg drone-ci restart 123
```

### Cancel

```bash
# Cancel a running build
rg drone-ci cancel 123
```

### Promote

```bash
# Promote build to environment
rg drone-ci promote 123 --target production

# Promote with parameters
rg drone-ci promote 123 --target staging --param VERSION=1.0
```

### Approvals

```bash
# Approve a blocked stage
rg drone-ci approve 123 --stage 2

# Decline a blocked stage
rg drone-ci decline 123 --stage 2
```

## Status Icons

| Status | Meaning |
|--------|---------|
| `pending` | Queued, waiting to run |
| `running` | Currently executing |
| `success` | Completed successfully |
| `failed` | Completed with failures |
| `cancelled` | Killed or declined |
| `blocked` | Waiting for approval |

## Build Promotion

Drone supports promoting builds to different environments:

```yaml
# .drone.yml
kind: pipeline
name: deploy

trigger:
  event:
    - promote

steps:
  - name: deploy
    image: alpine
    commands:
      - echo "Deploying to $DRONE_DEPLOY_TO"
```

Promote:
```bash
rg drone-ci promote 123 --target production
```

## Approval Gates

For builds requiring manual approval:

```yaml
# .drone.yml
kind: pipeline
name: deploy

steps:
  - name: approval
    image: drone/cli
    commands:
      - echo "Waiting for approval"
    when:
      event: promote

---
kind: approval
name: approve-deploy
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DRONE_SERVER` | Drone server URL |
| `DRONE_TOKEN` | Personal API token |
| `DRONE_OWNER` | Repository owner |
| `DRONE_REPO` | Repository name |

## Troubleshooting

### "401 Unauthorized"
- Check token is valid
- Token may have expired

### "404 Not Found"
- Check owner and repo names
- Verify repository is activated in Drone

### Cannot trigger build
- Ensure `.drone.yml` exists in repository
- Check branch exists
- Verify repo is active in Drone dashboard