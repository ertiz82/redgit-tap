# AWS CodeCommit Integration for RedGit

Code hosting with PRs, branches, and repository management on AWS.

## Features

- **Pull Requests**: Create, list, merge PRs
- **Branches**: Create, list, delete branches
- **Repository Info**: View repo details
- **AWS Integration**: Uses AWS credentials automatically
- **Auto-detection**: Detects repo from git remote

## Prerequisites

- AWS CLI installed and configured (`aws configure`)
- boto3 Python package (`pip install boto3`)
- IAM permissions for CodeCommit

## Installation

```bash
pip install boto3  # If not already installed
rg install codecommit
```

## Setup

### Configure AWS Credentials

```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=xxx
export AWS_REGION=us-east-1
```

### Configuration

```yaml
integrations:
  codecommit:
    region: "us-east-1"           # Or AWS_REGION env var
    repository_name: "my-repo"    # Or CODECOMMIT_REPO env var
    default_branch: "main"

active:
  code_hosting: codecommit
```

## Commands

### Repository

```bash
# Show connection status
rg codecommit status

# List repositories
rg codecommit repos

# Show repo info
rg codecommit info
```

### Pull Requests

```bash
# List open PRs
rg codecommit prs

# List closed PRs
rg codecommit prs --status CLOSED

# Create PR from current branch
rg codecommit pr "Add new feature"

# Merge PR
rg codecommit merge pr-123
```

### Branches

```bash
# List branches
rg codecommit branches

# Create branch
rg codecommit branch feature/new-feature

# Delete branch
rg codecommit delete-branch feature/old-branch
```

## Git Remote Setup

```bash
# HTTPS (with credential helper)
git remote add origin https://git-codecommit.us-east-1.amazonaws.com/v1/repos/MyRepo

# SSH
git remote add origin ssh://git-codecommit.us-east-1.amazonaws.com/v1/repos/MyRepo

# GRC (git-remote-codecommit)
git remote add origin codecommit::us-east-1://MyRepo
```

## IAM Permissions

Required IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "codecommit:GetRepository",
        "codecommit:ListBranches",
        "codecommit:GetBranch",
        "codecommit:CreateBranch",
        "codecommit:DeleteBranch",
        "codecommit:ListPullRequests",
        "codecommit:GetPullRequest",
        "codecommit:CreatePullRequest",
        "codecommit:MergePullRequestBySquash",
        "codecommit:MergePullRequestByFastForward",
        "codecommit:ListRepositories"
      ],
      "Resource": "*"
    }
  ]
}
```

Or use the managed policy: `AWSCodeCommitPowerUser`

## Troubleshooting

### "boto3 not installed"
```bash
pip install boto3
```

### "Could not connect to endpoint"
- Check AWS credentials are configured
- Verify region is correct
- Ensure network can reach AWS

### "Repository not found"
- Check repository name is correct
- Verify IAM permissions
- Ensure repository exists in the specified region

### Credential issues
```bash
# Verify credentials
aws sts get-caller-identity

# Configure credential helper for HTTPS
git config --global credential.helper '!aws codecommit credential-helper $@'
git config --global credential.UseHttpPath true
```