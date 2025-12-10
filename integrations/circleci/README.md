# CircleCI Integration for RedGit

Manage pipelines, trigger workflows, view status and artifacts.

## Features

- **Pipeline Management**: List, trigger pipelines
- **Workflow Control**: View and cancel workflows
- **Job Details**: See job status and artifacts
- **Rerun Support**: Rerun workflows (from failed)
- **Auto-detection**: Detects project from git remote

## Installation

```bash
rg install circleci
```

## Setup

### Create Token

1. Go to [app.circleci.com/settings/user/tokens](https://app.circleci.com/settings/user/tokens)
2. Click "Create New Token"
3. Name it and copy the token

### Configuration

```yaml
integrations:
  circleci:
    token: "CCIPAT_xxx"         # Or CIRCLECI_TOKEN env var
    project_slug: "gh/user/repo" # Auto-detected

active:
  ci_cd: circleci
```

## Commands

### Pipelines

```bash
# List recent pipelines
rg circleci pipelines

# List pipelines for branch
rg circleci pipelines --branch main

# Show pipeline details
rg circleci pipeline <pipeline-id>
```

### Workflows

```bash
# List workflows for a pipeline
rg circleci workflows <pipeline-id>

# Show workflow jobs
rg circleci jobs <workflow-id>
```

### Trigger

```bash
# Trigger pipeline on current branch
rg circleci trigger

# Trigger on specific branch
rg circleci trigger --branch main

# Trigger with parameters
rg circleci trigger --param deploy=true
```

### Rerun

```bash
# Rerun entire workflow
rg circleci rerun <workflow-id>

# Rerun from failed jobs only
rg circleci rerun <workflow-id> --from-failed
```

### Cancel

```bash
# Cancel a workflow
rg circleci cancel <workflow-id>
```

### Artifacts

```bash
# List job artifacts
rg circleci artifacts <job-number>
```

## Project Slug Format

CircleCI uses project slugs in the format:
- GitHub: `gh/owner/repo`
- Bitbucket: `bb/owner/repo`

The integration auto-detects this from your git remote.

## Status Icons

| Status | Meaning |
|--------|---------|
| `pending` | Queued or on hold |
| `running` | Currently executing |
| `success` | Completed successfully |
| `failed` | Completed with failures |
| `cancelled` | Manually cancelled |

## Pipeline Parameters

CircleCI pipelines can accept parameters defined in your config:

```yaml
# .circleci/config.yml
parameters:
  deploy:
    type: boolean
    default: false
```

Trigger with parameters:
```bash
rg circleci trigger --param deploy=true
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CIRCLECI_TOKEN` | Personal API token |
| `CIRCLECI_PROJECT` | Project slug |

## Troubleshooting

### "401 Unauthorized"
- Check token is valid
- Token may have expired

### "404 Not Found"
- Check project slug format
- Verify project exists and you have access

### Cannot trigger pipeline
- Ensure `.circleci/config.yml` exists
- Check branch exists