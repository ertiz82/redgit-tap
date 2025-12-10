# RedGit Tap

Official repository of RedGit integrations and plugins.

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
| [linear](./integrations/linear) | Modern issue tracking with cycles and projects |
| [notion](./integrations/notion) | Use Notion databases as task boards |
| [asana](./integrations/asana) | Project and task management with Asana |
| [trello](./integrations/trello) | Kanban board task management with Trello |

## Quick Start

```bash
# Add GitHub integration
rg install github

# Add Slack notifications
rg install slack

# Add Linear for task management
rg install linear

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

active:
  code_hosting: github
  notification: slack
  task_management: linear
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

## License

MIT License