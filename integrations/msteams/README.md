# Microsoft Teams Integration for RedGit

Send notifications to Teams channels via Incoming Webhooks.

## Features

- **Webhook Notifications**: Send messages to any Teams channel
- **Message Cards**: Rich formatted cards with colors and actions
- **Event Types**: Different icons for commits, PRs, deploys, etc.
- **Action Buttons**: Link to view details

## Installation

```bash
rg install msteams
```

## Setup

### Create Incoming Webhook

1. Open Microsoft Teams
2. Go to the channel you want notifications in
3. Click "..." > "Connectors"
4. Find "Incoming Webhook" and click "Configure"
5. Name your webhook (e.g., "RedGit")
6. Copy the webhook URL

### Configuration

```yaml
integrations:
  msteams:
    webhook_url: "https://outlook.office.com/webhook/..."  # Or MSTEAMS_WEBHOOK_URL env var

active:
  notification: msteams
```

## Usage

### Send Messages

```bash
# Simple message
rg notify "Build completed successfully"

# With title
rg notify "Deployment finished" --title "Production Deploy"

# With level (changes card color)
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

## Message Card Format

Notifications are sent as MessageCards:

```
+----------------------------------+
| :rocket: Production Deployment   |
| via RedGit | deploy              |
|----------------------------------|
| Version 1.2.3 deployed           |
|                                  |
| Branch     | main                |
| Commit     | abc123              |
|                                  |
| [View Details]                   |
+----------------------------------+
```

## Teams Connector Types

| Connector | Use Case |
|-----------|----------|
| Incoming Webhook | Simple notifications (used by RedGit) |
| Bot | Interactive conversations |
| Office 365 Connector | Complex integrations |

## Troubleshooting

### "Failed to send message"
- Verify webhook URL is correct
- Check webhook hasn't been deleted
- Ensure URL is from Teams (outlook.office.com/webhook)

### Messages not appearing
- Check channel permissions
- Verify connector is still configured
- Try recreating the webhook

### Webhook URL expired
- Teams webhooks don't expire, but can be deleted
- Recreate the connector if needed