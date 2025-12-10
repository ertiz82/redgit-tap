# Azure Pipelines Integration for RedGit

Manage pipelines, trigger builds, view status and logs.

## Features

- **Pipeline Management**: List, trigger, cancel pipelines
- **Build Control**: View builds and their stages
- **Timeline View**: See stages, jobs, and tasks
- **Logs Access**: View build logs
- **Retry Support**: Rebuild failed pipelines

## Installation

```bash
rg install azure-pipelines
```

## Setup

### Create Personal Access Token

1. Go to Azure DevOps → User Settings → Personal Access Tokens
2. Click "New Token"
3. Set scopes:
   - Build: Read & Execute
   - Pipeline Resources: Read
4. Copy the token

### Configuration

```yaml
integrations:
  azure-pipelines:
    token: "your-pat"           # Or AZURE_DEVOPS_TOKEN env var
    organization: "myorg"       # Azure DevOps org
    project: "myproject"        # Project name

active:
  ci_cd: azure-pipelines
```

## Commands

### Pipelines

```bash
# List pipeline definitions
rg azure-pipelines pipelines

# List recent builds
rg azure-pipelines builds

# List builds for branch
rg azure-pipelines builds --branch main

# Show build details
rg azure-pipelines build 12345
```

### Trigger

```bash
# Trigger default pipeline
rg azure-pipelines trigger

# Trigger specific pipeline
rg azure-pipelines trigger --pipeline 123

# Trigger on specific branch
rg azure-pipelines trigger --branch feature/test

# Trigger with parameters
rg azure-pipelines trigger --param environment=staging
```

### Timeline

```bash
# Show stages/jobs for a build
rg azure-pipelines timeline 12345
```

### Logs

```bash
# View build logs
rg azure-pipelines logs 12345
```

### Retry

```bash
# Rebuild a pipeline
rg azure-pipelines retry 12345
```

### Cancel

```bash
# Cancel a running build
rg azure-pipelines cancel 12345
```

## Status Icons

| Status | Meaning |
|--------|---------|
| `pending` | Not started |
| `running` | In progress |
| `success` | Succeeded |
| `failed` | Failed |
| `cancelled` | Cancelled |

## Pipeline Parameters

Azure Pipelines can accept template parameters:

```yaml
# azure-pipelines.yml
parameters:
  - name: environment
    type: string
    default: 'dev'
```

Trigger with parameters:
```bash
rg azure-pipelines trigger --param environment=prod
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AZURE_DEVOPS_TOKEN` | Personal access token |
| `AZURE_DEVOPS_ORG` | Organization name |
| `AZURE_DEVOPS_PROJECT` | Project name |

## Troubleshooting

### "401 Unauthorized"
- Check PAT is valid and not expired
- Verify PAT has correct scopes

### "404 Not Found"
- Check organization and project names
- Verify you have access to the project

### Cannot trigger pipeline
- Ensure `azure-pipelines.yml` exists
- Check pipeline is enabled
- Verify branch exists