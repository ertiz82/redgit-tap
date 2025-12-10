# Mattermost Integration for RedGit

Send notifications to Mattermost channels via Incoming Webhooks.

## Features

- **Webhook Notifications**: Send messages to any Mattermost channel
- **Rich Attachments**: Formatted messages with colors and fields
- **Event Types**: Different icons for commits, PRs, deploys, etc.
- **Channel Override**: Send to different channels per notification

## Installation

```bash
rg install mattermost
```

## Setup

### Create Incoming Webhook

1. Go to Main Menu > Integrations > Incoming Webhooks
2. Click "Add Incoming Webhook"
3. Select a channel and give it a name
4. Copy the webhook URL

### Configuration

```yaml
integrations:
  mattermost:
    webhook_url: "https://mattermost.example.com/hooks/xxx"  # Or MATTERMOST_WEBHOOK_URL env var
    username: "RedGit"
    channel: ""        # Optional: override default channel
    icon_url: ""       # Optional: custom icon

active:
  notification: mattermost
```

## Usage

### Send Messages

```bash
# Simple message
rg notify "Build completed successfully"

# With title
rg notify "Deployment finished" --title "Production Deploy"

# With level (changes attachment color)
rg notify "Tests failed" --level error
rg notify "Warning: disk space low" --level warning
rg notify "Feature deployed" --level success
```

## Notification Levels

| Level | Color | Use Case |
|-------|-------|----------|
| info | Blue | General notifications |
| success | Green | Successful operations |
| warning | Yellow | Warnings |
| error | Red | Failures |

## Attachment Format

Notifications are sent as message attachments:

```
+----------------------------------+
| :rocket: Production Deployment   |
|----------------------------------|
| Version 1.2.3 deployed           |
|                                  |
| Branch: main    Commit: abc123   |
|                                  |
| via RedGit | deploy              |
+----------------------------------+
```

## Channel Override

You can send to different channels:

```yaml
# In config, override default
channel: "dev-notifications"
```

Or programmatically send to any channel the webhook has access to.

## Self-Hosted Setup

For self-hosted Mattermost:

1. Enable incoming webhooks in System Console
2. Allow webhook overrides if needed (username, icon, channel)
3. Create webhook in your team's integrations

## Troubleshooting

### "Failed to send message"
- Verify webhook URL is correct
- Check Mattermost server is reachable
- Ensure webhooks are enabled in System Console

### Messages not appearing
- Check channel permissions
- Verify webhook hasn't been deleted
- Ensure bot username is allowed

### Channel override not working
- Enable "Allow webhook to override channel" in webhook settings
- Or use the webhook's default channel