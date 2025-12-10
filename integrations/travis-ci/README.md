# Travis CI Integration for RedGit

Manage builds, trigger jobs, view status and logs.

## Features

- **Build Management**: List, trigger, cancel builds
- **Job Details**: View job status and logs
- **Restart Support**: Restart failed builds
- **Auto-detection**: Detects repository from git remote

## Installation

```bash
rg install travis-ci
```

## Setup

### Get API Token

1. Go to [app.travis-ci.com/account/preferences](https://app.travis-ci.com/account/preferences)
2. Copy your API authentication token

### Configuration

```yaml
integrations:
  travis-ci:
    token: "your-token"        # Or TRAVIS_TOKEN env var
    repo_slug: "owner/repo"    # Auto-detected
    endpoint: "com"            # 'com' or 'org'

active:
  ci_cd: travis-ci
```

## Commands

### Builds

```bash
# List recent builds
rg travis-ci builds

# List builds for branch
rg travis-ci builds --branch main

# Show build details
rg travis-ci build 12345
```

### Trigger

```bash
# Trigger build on current branch
rg travis-ci trigger

# Trigger on specific branch
rg travis-ci trigger --branch main
```

### Jobs

```bash
# List jobs for a build
rg travis-ci jobs 12345

# View job logs
rg travis-ci logs 67890
```

### Restart

```bash
# Restart a build
rg travis-ci restart 12345
```

### Cancel

```bash
# Cancel a running build
rg travis-ci cancel 12345
```

## Status Icons

| Status | Meaning |
|--------|---------|
| `pending` | Queued, waiting to run |
| `running` | Currently executing |
| `success` | Completed successfully |
| `failed` | Completed with failures |
| `cancelled` | Manually cancelled |

## travis-ci.com vs travis-ci.org

- **travis-ci.com**: For all repositories (default)
- **travis-ci.org**: Legacy, for open source projects

Set `endpoint: "org"` if using travis-ci.org.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TRAVIS_TOKEN` | API authentication token |
| `TRAVIS_REPO` | Repository slug |
| `TRAVIS_ENDPOINT` | 'com' or 'org' |

## Troubleshooting

### "403 Forbidden"
- Check token is valid
- Ensure repository is activated on Travis CI

### "404 Not Found"
- Check repo_slug format (owner/repo)
- Repository may not be synced with Travis CI

### Cannot trigger build
- Ensure `.travis.yml` exists in repository
- Check branch exists