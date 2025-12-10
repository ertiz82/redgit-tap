# Azure Repos Integration for RedGit

Code hosting with PRs, branches, and repository management on Azure DevOps.

## Features

- **Pull Requests**: Create, list, complete, abandon PRs
- **Branches**: List repository branches
- **Repository Info**: View repo details
- **Projects**: List organization projects
- **Auto-detection**: Automatically detects repo from git remote

## Installation

```bash
rg install azure-repos
```

## Setup

### Create Personal Access Token

1. Go to Azure DevOps > User Settings > Personal Access Tokens
2. Create new token with scopes:
   - Code: Read & Write
   - Pull Request Threads: Read & Write
3. Copy the token

### Configuration

```yaml
integrations:
  azure-repos:
    pat: "xxx"                    # Or AZURE_DEVOPS_PAT env var
    organization: "myorg"         # Or AZURE_DEVOPS_ORG env var
    project: "MyProject"          # Auto-detected from git remote
    repository: "my-repo"         # Auto-detected from git remote
    default_branch: "main"

active:
  code_hosting: azure-repos
```

## Commands

### Repository

```bash
# Show connection status
rg azure-repos status

# List projects
rg azure-repos projects

# List repositories
rg azure-repos repos

# Show repo info
rg azure-repos info
```

### Pull Requests

```bash
# List active PRs
rg azure-repos prs

# List all PRs
rg azure-repos prs --status all

# Create PR from current branch
rg azure-repos pr "Add new feature"

# Complete (merge) PR
rg azure-repos complete 123

# Complete with squash
rg azure-repos complete 123 --squash

# Abandon PR
rg azure-repos abandon 123
```

### Branches

```bash
# List branches
rg azure-repos branches
```

## Auto-Detection

The integration automatically detects settings from your git remote:

```bash
# These formats are supported:
https://dev.azure.com/org/project/_git/repo
https://org@dev.azure.com/org/project/_git/repo
https://org.visualstudio.com/project/_git/repo
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AZURE_DEVOPS_PAT` | Personal access token |
| `AZURE_DEVOPS_ORG` | Organization name |
| `AZURE_DEVOPS_PROJECT` | Project name |
| `AZURE_DEVOPS_REPO` | Repository name |

## Token Scopes

Required scopes:
- **Code**: Read & Write
- **Pull Request Threads**: Read & Write (for PR comments)
- **Project and Team**: Read (for listing projects)

## PR Status Values

| Status | Description |
|--------|-------------|
| `active` | Open PRs |
| `completed` | Merged PRs |
| `abandoned` | Closed without merge |
| `all` | All PRs |

## Troubleshooting

### "401 Unauthorized"
- Verify PAT is correct
- Check PAT hasn't expired
- Ensure PAT has required scopes

### "404 Not Found"
- Check organization/project/repository names
- Verify you have access to the project
- Ensure URLs are correct

### Auto-detection not working
- Make sure git remote uses Azure DevOps URL
- Set values manually in config

### Branch names
- Azure DevOps uses `refs/heads/` prefix internally
- RedGit handles this automatically