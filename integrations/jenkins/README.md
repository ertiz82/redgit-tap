# Jenkins Integration for RedGit

Manage jobs, trigger builds, view status and logs.

## Features

- **Job Management**: List jobs and their status
- **Build Control**: Trigger, cancel, view builds
- **Logs Access**: View console output
- **Queue Monitoring**: Check build queue
- **Parameterized Builds**: Pass parameters when triggering

## Installation

```bash
rg install jenkins
```

## Setup

### Create API Token

1. Log into Jenkins
2. Click your username (top right) → Configure
3. Under API Token, click "Add new Token"
4. Name it and copy the token

### Configuration

```yaml
integrations:
  jenkins:
    url: "https://jenkins.company.com"
    username: "myuser"
    token: "your-api-token"
    job_name: "my-project"  # Default job

active:
  ci_cd: jenkins
```

## Commands

### Jobs

```bash
# List all jobs
rg jenkins jobs

# Show job details
rg jenkins job my-project
```

### Builds

```bash
# List recent builds
rg jenkins builds

# List builds for specific job
rg jenkins builds --job my-project

# Show build details
rg jenkins build 123

# View build logs
rg jenkins logs 123
```

### Trigger

```bash
# Trigger default job
rg jenkins trigger

# Trigger specific job
rg jenkins trigger --job my-project

# Trigger with parameters
rg jenkins trigger --param BRANCH=main --param DEPLOY=true
```

### Cancel

```bash
# Stop a running build
rg jenkins cancel 123
```

### Queue

```bash
# Show build queue
rg jenkins queue
```

## Status Colors

| Status | Meaning |
|--------|---------|
| `running` | Build in progress |
| `success` | Build passed |
| `failed` | Build failed |
| `unstable` | Tests failed |
| `cancelled` | Build aborted |
| `pending` | Not built yet |

## Parameterized Builds

Jenkins jobs can accept parameters:

```bash
# Single parameter
rg jenkins trigger --param BRANCH=feature/test

# Multiple parameters
rg jenkins trigger --param BRANCH=main --param ENV=staging --param DEPLOY=true
```

## Pipeline Jobs

For multibranch pipeline jobs, specify the branch:

```bash
rg jenkins trigger --job "my-pipeline/main"
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `JENKINS_URL` | Jenkins server URL |
| `JENKINS_USER` | Username |
| `JENKINS_TOKEN` | API token |
| `JENKINS_JOB` | Default job name |

## Troubleshooting

### "401 Unauthorized"
- Check username and token are correct
- Ensure user has appropriate permissions

### "403 Forbidden"
- CSRF protection may be enabled
- Check Jenkins security settings

### "404 Not Found"
- Check job name is correct
- Job may be in a folder: use "folder/job-name"

### Cannot trigger build
- User may not have build permission
- Job may be disabled