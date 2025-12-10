# Rocket.Chat Integration for RedGit

Send notifications to Rocket.Chat channels via Incoming Webhooks.

## Features

- **Webhook Notifications**: Send messages to any channel
- **Rich Attachments**: Formatted messages with colors and fields
- **Event Types**: Different icons for commits, PRs, deploys, etc.
- **Channel Override**: Send to different channels per notification
- **Emoji Icons**: Customizable bot icon

## Installation

```bash
rg install rocketchat
```

## Setup

### Create Incoming Webhook

1. Go to Administration > Integrations
2. Click "New Integration" > "Incoming WebHook"
3. Enable the integration and configure:
   - Name: RedGit
   - Post to Channel: #your-channel
   - Post as: redgit (or any username)
4. Save and copy the webhook URL

### Configuration

```yaml
integrations:
  rocketchat:
    webhook_url: "https://chat.example.com/hooks/xxx"  # Or ROCKETCHAT_WEBHOOK_URL env var
    username: "RedGit"
    channel: ""           # Optional: override default channel
    icon_emoji: ":robot:" # Optional: custom emoji icon

active:
  notification: rocketchat
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

## Channel Format

Channels can be specified as:
- `#channel-name` - Public channel
- `@username` - Direct message
- Channel ID

## Self-Hosted Setup

For self-hosted Rocket.Chat:

1. Go to Administration > Integrations
2. Create new Incoming WebHook
3. Configure script (optional) or use default
4. Enable and save

## Troubleshooting

### "Failed to send message"
- Verify webhook URL is correct
- Check Rocket.Chat server is reachable
- Ensure integration is enabled

### Messages not appearing
- Check channel exists and is accessible
- Verify webhook post permissions
- Check integration logs in Administration

### Script errors
- Use simple JSON payload format
- Check script syntax if using custom script