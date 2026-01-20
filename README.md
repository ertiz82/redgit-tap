# RedGit Tap

Official repository of RedGit integrations and plugins.

---

## Main Repository

> **[RedGit](https://github.com/ertiz82/redgit)** - AI-powered Git workflow assistant with task management integration
>
> For installation, usage, and core documentation, visit the **[main RedGit repository](https://github.com/ertiz82/redgit)**.

### Quick Install

```bash
# Using Homebrew (macOS/Linux)
brew tap ertiz82/tap && brew install redgit

# Using pip
pip install redgit
```

---

## Installation

Install integrations directly from this tap:

```bash
# Install an integration
rg install slack
rg install github
rg install linear

# Install specific version
rg install slack@v1.0.0
```

## Available Integrations

### Code Hosting

| Name | Description |
|------|-------------|
| [github](./integrations/github) | GitHub PRs, branches, and repository management |
| [gitlab](./integrations/gitlab) | GitLab MRs, branches, self-hosted support |
| [bitbucket](./integrations/bitbucket) | Bitbucket PRs, workspaces, and branches |
| [codecommit](./integrations/codecommit) | AWS CodeCommit PRs and repository management |
| [azure-repos](./integrations/azure-repos) | Azure Repos PRs and repository management |
| [sourceforge](./integrations/sourceforge) | SourceForge repository management |
| [allura](./integrations/allura) | Apache Allura forge with tickets and MRs |

### Notifications

| Name | Description |
|------|-------------|
| [slack](./integrations/slack) | Send notifications to Slack channels |
| [discord](./integrations/discord) | Send notifications via Discord webhooks |
| [telegram](./integrations/telegram) | Send notifications via Telegram Bot API |
| [msteams](./integrations/msteams) | Send notifications to Microsoft Teams |
| [mattermost](./integrations/mattermost) | Send notifications to Mattermost channels |
| [rocketchat](./integrations/rocketchat) | Send notifications to Rocket.Chat |
| [zulip](./integrations/zulip) | Send notifications to Zulip streams |
| [whatsapp](./integrations/whatsapp) | Send notifications via WhatsApp Business API |

### Task Management

| Name | Description |
|------|-------------|
| [jira](./integrations/jira) | Full-featured Jira Cloud with Scrum/Kanban support |
| [linear](./integrations/linear) | Modern issue tracking with cycles and projects |
| [notion](./integrations/notion) | Use Notion databases as task boards |
| [asana](./integrations/asana) | Project and task management with Asana |
| [trello](./integrations/trello) | Kanban board task management with Trello |

### CI/CD

| Name | Description |
|------|-------------|
| [github-actions](./integrations/github-actions) | Manage workflows, trigger runs, view status and logs |
| [gitlab-ci](./integrations/gitlab-ci) | Manage pipelines, trigger jobs, view status and logs |
| [jenkins](./integrations/jenkins) | Manage jobs, trigger builds, view status and logs |
| [circleci](./integrations/circleci) | Manage pipelines, trigger workflows, view status |
| [travis-ci](./integrations/travis-ci) | Manage builds, trigger jobs, view status and logs |
| [azure-pipelines](./integrations/azure-pipelines) | Manage Azure DevOps pipelines and builds |
| [bitbucket-pipelines](./integrations/bitbucket-pipelines) | Manage Bitbucket pipelines and builds |
| [drone-ci](./integrations/drone-ci) | Manage Drone builds, promotions, and approvals |

### Tunnel

Expose local ports to the internet for webhooks, Planning Poker, and remote access.

| Name | Description |
|------|-------------|
| [ngrok](./integrations/ngrok) | Expose local ports via ngrok tunnels |
| [cloudflare-tunnel](./integrations/cloudflare-tunnel) | Expose local ports via Cloudflare Tunnels |
| [localtunnel](./integrations/localtunnel) | Expose local ports via localtunnel.me (no signup) |
| [bore](./integrations/bore) | Fast and secure TCP tunnel written in Rust |
| [serveo](./integrations/serveo) | SSH-based tunnel - no installation required |

### Code Quality

| Name | Description |
|------|-------------|
| [sonarqube](./integrations/sonarqube) | SonarQube/SonarCloud code quality with quality gates |
| [codeclimate](./integrations/codeclimate) | CodeClimate maintainability and test coverage |
| [codacy](./integrations/codacy) | Codacy automated code review and security analysis |
| [snyk](./integrations/snyk) | Snyk security vulnerability scanning |
| [dependabot](./integrations/dependabot) | GitHub Dependabot for automated dependency updates |
| [renovate](./integrations/renovate) | Renovate automated dependency updates |
| [codecov](./integrations/codecov) | Codecov code coverage reporting |
| [coveralls](./integrations/coveralls) | Coveralls coverage tracking |

### Error Tracking

Track application errors, link commits to issues, and auto-resolve on deploy.

| Name | Description |
|------|-------------|
| [sentry](./integrations/sentry) | Error tracking with automatic file-error matching and commit linking |

## Available Plugins

| Name | Description |
|------|-------------|
| [changelog](./plugins/changelog) | Automatic changelog generation from git commits |
| [laravel](./plugins/laravel) | Laravel framework-specific file grouping and commit prompts |
| [version](./plugins/version) | Semantic versioning management for projects |

## Quick Start

```bash
# Add GitHub integration
rg install github

# Add Slack notifications
rg install slack

# Add Linear for task management
rg install linear

# Add Sentry for error tracking
rg install sentry

# List installed integrations
rg integrations
```

## Configuration

After installation, integrations are configured in `.redgit/config.yaml`:

```yaml
integrations:
  github:
    token: "ghp_xxx"
  slack:
    webhook_url: "https://hooks.slack.com/..."
  linear:
    api_key: "lin_api_xxx"
  sentry:
    organization: "my-org"
    project_slug: "my-project"

active:
  code_hosting: github
  notification: slack
  task_management: linear
  error_tracking: sentry
```

## Creating Your Own

### Integration Structure

```
integrations/my-integration/
├── __init__.py          # Integration class (required)
├── commands.py          # CLI commands (optional)
├── install_schema.json  # Installation wizard (optional)
└── README.md            # Documentation
```

### Integration Types

| Type | Base Class | Purpose |
|------|------------|---------|
| `code_hosting` | `CodeHostingBase` | Git hosting, PRs, branches |
| `notification` | `NotificationBase` | Send alerts and messages |
| `task_management` | `TaskManagementBase` | Issue tracking, sprints |
| `ci_cd` | `CICDBase` | CI/CD pipelines, builds, deployments |
| `code_quality` | `CodeQualityBase` | Code analysis, security scanning, coverage |
| `tunnel` | `TunnelBase` | Expose local ports to the internet |
| `error_tracking` | `ErrorTrackingBase` | Error monitoring, commit-error linking |

### Example Integration

```python
from redgit.integrations.base import NotificationBase, IntegrationType

class MyNotification(NotificationBase):
    name = "my-notification"
    integration_type = IntegrationType.NOTIFICATION

    def setup(self, config: dict):
        self.webhook = config.get("webhook_url")
        self.enabled = bool(self.webhook)

    def send_message(self, message: str, channel: str = None) -> bool:
        # Send notification
        return True
```

### Install Schema

Define installation wizard fields in `install_schema.json`:

```json
{
  "name": "My Integration",
  "description": "Description here",
  "type": "notification",
  "fields": [
    {
      "name": "webhook_url",
      "label": "Webhook URL",
      "type": "password",
      "required": true,
      "env_var": "MY_WEBHOOK_URL"
    }
  ]
}
```

## Contributing

1. Fork this repository
2. Create your integration/plugin
3. Update `index.json` with your integration
4. Submit a pull request

## Documentation

For complete documentation, usage guides, and core features, visit the **[main RedGit repository](https://github.com/ertiz82/redgit)**.

## License

MIT License