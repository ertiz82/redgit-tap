# Apache Allura Integration for RedGit

Code hosting with tickets, wiki, and repository management on Allura-powered forges.

## About Apache Allura

Apache Allura is the open source forge software that powers:
- SourceForge
- DARPA's VehicleForge
- Open Source Robotics Foundation
- Many other project hosting platforms

## Features

- **Git Operations**: Push, fetch, branch management
- **Merge Requests**: Create and list merge requests
- **Tickets**: View and create project tickets
- **Project Info**: View project and repository details
- **Multi-Forge**: Works with any Allura-based platform

## Installation

```bash
rg install allura
```

## Setup

### Get Bearer Token (Optional)

For write operations (creating tickets, merge requests):
1. Go to your Allura profile settings
2. Generate an API bearer token
3. Copy the token

### Configuration

```yaml
integrations:
  allura:
    base_url: "https://forge.example.com"  # Or ALLURA_BASE_URL env var
    project: "my-project"                   # Or ALLURA_PROJECT env var
    mount_point: "git"                      # Repository tool (default: git)
    bearer_token: "xxx"                     # Optional, for write access
    default_branch: "master"

active:
  code_hosting: allura
```

## Commands

### Repository

```bash
# Show connection status
rg allura status

# Show project info
rg allura project

# Show repository info
rg allura info

# List branches
rg allura branches
```

### Merge Requests

```bash
# List open merge requests
rg allura mrs

# Create merge request
rg allura mr "Add new feature"
```

### Tickets

```bash
# List open tickets
rg allura tickets

# Create ticket
rg allura ticket "Bug: Something broken"
```

### Git Operations

```bash
# Push current branch
rg allura push

# Fetch from remote
rg allura fetch
```

## URL Formats

Allura repositories typically use:

```bash
# HTTPS
https://forge.example.com/git/p/project/repo

# SSH
ssh://user@forge.example.com/git/p/project/repo
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ALLURA_BASE_URL` | Forge instance URL |
| `ALLURA_PROJECT` | Project name/slug |
| `ALLURA_BEARER_TOKEN` | API authentication token |

## API Notes

Allura API capabilities vary by installation:
- Read operations usually work without authentication
- Write operations require bearer token
- Some features may be disabled by administrators

## SourceForge Users

For SourceForge specifically, you can use either:
- This Allura integration with `base_url: https://sourceforge.net`
- The dedicated SourceForge integration

The SourceForge integration is simpler but has fewer API features.

## Troubleshooting

### "401 Unauthorized"
- Verify bearer token is correct
- Check token hasn't expired
- Some operations require authentication

### "404 Not Found"
- Check project name is correct
- Verify mount_point matches your repository tool
- Ensure base_url is correct

### API not available
- Some Allura installations disable API
- Contact your forge administrator
- Use git operations directly instead