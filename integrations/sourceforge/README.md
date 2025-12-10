# SourceForge Integration for RedGit

Code hosting and repository management on SourceForge.

## Features

- **Git Operations**: Push, fetch, branch management
- **Repository Info**: View project and repository URLs
- **SSH Support**: Authenticate via SSH keys
- **Auto-detection**: Detects project from git remote

## Limitations

SourceForge has limited API support compared to GitHub/GitLab. This integration focuses on:
- Git push/pull operations
- Branch listing
- Repository URL generation

Pull requests must be created through the web interface.

## Installation

```bash
rg install sourceforge
```

## Setup

### Add SSH Key

1. Generate SSH key if needed: `ssh-keygen -t ed25519`
2. Go to [SourceForge Shell Services](https://sourceforge.net/auth/shell_services)
3. Add your public key

### Configuration

```yaml
integrations:
  sourceforge:
    username: "your-username"     # Or SOURCEFORGE_USERNAME env var
    project: "project-name"       # Auto-detected from git remote
    repo_path: "code"             # Repository path (default: code)
    default_branch: "master"

active:
  code_hosting: sourceforge
```

## Commands

### Repository

```bash
# Show connection status
rg sourceforge status

# Show repository info
rg sourceforge info

# List branches
rg sourceforge branches
```

### Git Operations

```bash
# Push current branch
rg sourceforge push

# Fetch from remote
rg sourceforge fetch
```

### Pull Requests

```bash
# Open merge request page (web browser)
rg sourceforge pr "Feature title"
```

Note: SourceForge merge requests are created through the web interface.

## URL Formats

SourceForge supports multiple URL formats:

```bash
# SSH (read-write)
ssh://username@git.code.sf.net/p/project/code

# HTTPS (read-only)
https://git.code.sf.net/p/project/code

# Git protocol (read-only)
git://git.code.sf.net/p/project/code
```

## Repository Structure

SourceForge projects can have multiple repositories:

```
project/
├── code/      # Main source code (default)
├── docs/      # Documentation
└── website/   # Project website
```

Specify the repository with `repo_path` in config.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SOURCEFORGE_USERNAME` | SourceForge username |
| `SOURCEFORGE_PROJECT` | Project name |

## Troubleshooting

### "Permission denied (publickey)"
- Verify SSH key is added to SourceForge
- Check key permissions: `chmod 600 ~/.ssh/id_ed25519`
- Test connection: `ssh -T git.code.sf.net`

### "Repository not found"
- Check project name is correct
- Verify repo_path (code, git, etc.)
- Ensure repository exists in project

### Push rejected
- Make sure you have write access
- Check branch protection settings
- Verify SSH authentication works