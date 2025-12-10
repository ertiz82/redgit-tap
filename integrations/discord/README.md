# Discord Integration for RedGit

Send notifications to Discord channels via webhooks.

## Features

- **Webhook Notifications**: Send messages to any Discord channel
- **Rich Embeds**: Formatted notifications with colors and fields
- **Event Types**: Different icons for commits, PRs, deploys, etc.
- **Custom Branding**: Set bot username and avatar

## Installation

```bash
rg install discord
```

## Setup

1. Open Discord channel settings
2. Go to Integrations > Webhooks
3. Create a new webhook and copy the URL

### Configuration

```yaml
integrations:
  discord:
    webhook_url: "https://discord.com/api/webhooks/..."  # Or DISCORD_WEBHOOK_URL env var
    username: "RedGit"
    avatar_url: ""  # Optional custom avatar

active:
  notification: discord
```

## Usage

### Send Messages

```bash
# Simple message
rg notify "Build completed successfully"

# With title
rg notify "Deployment finished" --title "Production Deploy"

# With level (changes embed color)
rg notify "Tests failed" --level error
rg notify "Warning: disk space low" --level warning
rg notify "Feature deployed" --level success
```

## Notification Levels

| Level | Color | Use Case |
|-------|-------|----------|
| info | Blue | General notifications |
| success | Green | Successful operations |
| warning | Orange | Warnings, attention needed |
| error | Red | Failures, errors |

## Event Types

The integration uses different emojis for event types:

- `:hammer:` - commit
- `:seedling:` - branch
- `:twisted_rightwards_arrows:` - pr (pull request)
- `:clipboard:` - task
- `:rocket:` - deploy
- `:warning:` - alert
- `:speech_balloon:` - message

## Embed Format

Notifications are sent as Discord embeds:

```
+----------------------------------+
| :rocket: Production Deployment   |
|----------------------------------|
| Version 1.2.3 deployed           |
|                                  |
| Branch: main    Commit: abc123   |
|                                  |
| via RedGit * deploy              |
+----------------------------------+
```

## Troubleshooting

### "Failed to send message"
- Verify webhook URL is correct
- Check webhook hasn't been deleted
- Ensure URL starts with `https://discord.com/api/webhooks/`

### Messages not appearing
- Check channel permissions
- Verify webhook is for the correct channel
- Try regenerating the webhook URL