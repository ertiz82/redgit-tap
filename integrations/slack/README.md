# Slack Integration for RedGit

Send commit notifications, PR updates, and task status changes to Slack channels.

## Features

- 🔨 **Commit notifications** - Get notified when commits are made
- 🌿 **Branch notifications** - Track new branch creation
- 🔀 **PR notifications** - Know when PRs are created
- 🎨 **Rich formatting** - Beautiful Slack message blocks
- 📢 **Multiple channels** - Send to different channels per event
- ⚙️ **Customizable** - Configure bot name, icon, and events

## Installation

```bash
rg install slack
```

Or from the default tap:
```bash
rg install slack
```

## Configuration

### 1. Create a Slack Webhook

1. Go to [Slack API](https://api.slack.com/messaging/webhooks)
2. Create a new app or use existing
3. Enable "Incoming Webhooks"
4. Create a webhook for your channel
5. Copy the webhook URL

### 2. Configure RedGit

Run the installation wizard:
```bash
rg integration install slack
```

Or manually edit `.redgit/config.yaml`:
```yaml
integrations:
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/T.../B.../..."
    channel: "#dev-commits"
    username: "RedGit"
    icon_emoji: ":git:"
    notify_on:
      - commit
      - branch
      - pr
```

### Environment Variable

You can also set the webhook URL via environment variable:
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

## Usage

### CLI Commands

```bash
# Check status
rg slack status

# Send test message
rg slack test
rg slack test -m "Custom test message"

# Send custom message
rg slack send "Deployment complete! 🚀"
rg slack send "Alert!" --mention "@here"
rg slack send "Check this" --channel "#alerts"

# Manually trigger notifications
rg slack notify commit --branch main --message "feat: new feature"
rg slack notify branch --branch feature/login
rg slack notify pr --title "Add login" --url "https://github.com/..."
```

### Automatic Notifications

Once configured, RedGit will automatically send notifications when:

1. **Commits are made** via `rg propose` or `rg push`
2. **Branches are created** for tasks
3. **PRs are created** (when GitHub integration is active)

## Message Examples

### Commit Notification
```
🔨 New Commit
━━━━━━━━━━━━━━━━
Branch: feature/login
Author: developer

Message:
feat: add user authentication

Files (3):
• src/auth/login.py
• src/auth/utils.py
• tests/test_auth.py
```

### Branch Notification
```
🌿 New Branch Created
━━━━━━━━━━━━━━━━
Branch: feature/PROJ-123-user-login
Linked Issue: PROJ-123
```

### PR Notification
```
🔀 Pull Request Created
━━━━━━━━━━━━━━━━
Add user authentication

From: feature/login
To: main
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `webhook_url` | string | - | Slack webhook URL (required) |
| `channel` | string | - | Default channel (uses webhook default if empty) |
| `username` | string | "RedGit" | Bot display name |
| `icon_emoji` | string | ":git:" | Bot icon emoji |
| `notify_on` | list | ["commit", "branch"] | Events to notify on |

### Event Types

- `commit` - New commits
- `branch` - Branch creation
- `pr` - Pull request creation

## Troubleshooting

### Webhook not working

1. Verify the webhook URL is correct
2. Check if the webhook is enabled in Slack
3. Ensure network connectivity

```bash
# Test with curl
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test"}' \
  YOUR_WEBHOOK_URL
```

### Messages not appearing

1. Check the channel permissions
2. Verify the bot has access to the channel
3. Check `notify_on` configuration

### Rate limiting

Slack has rate limits. If you're making many commits quickly, some notifications may be dropped.

## License

MIT License - Part of the RedGit ecosystem.
