# Zulip Integration for RedGit

Send notifications to Zulip streams via Bot API.

## Features

- **Stream Messages**: Send to any stream your bot can access
- **Topic Support**: Organize messages by topic (Zulip's threading)
- **Rich Formatting**: Markdown formatted messages
- **Event Types**: Different emojis for commits, PRs, deploys, etc.

## Installation

```bash
rg install zulip
```

## Setup

### Create a Bot

1. Go to Settings > Your bots
2. Click "Add a new bot"
3. Select "Generic bot" type
4. Give it a name like "RedGit"
5. Copy the bot email and API key

### Configuration

```yaml
integrations:
  zulip:
    server_url: "https://yourorg.zulipchat.com"  # Or ZULIP_SERVER_URL env var
    bot_email: "redgit-bot@yourorg.zulipchat.com"  # Or ZULIP_BOT_EMAIL env var
    api_key: "xxx"  # Or ZULIP_API_KEY env var
    stream: "dev"   # Or ZULIP_STREAM env var
    topic: "RedGit"

active:
  notification: zulip
```

## Usage

### Send Messages

```bash
# Simple message
rg notify "Build completed successfully"

# With title
rg notify "Deployment finished" --title "Production Deploy"

# With level
rg notify "Tests failed" --level error
rg notify "Feature deployed" --level success
```

## Notification Levels

| Level | Emoji | Use Case |
|-------|-------|----------|
| info | :information_source: | General notifications |
| success | :check: | Successful operations |
| warning | :warning: | Warnings |
| error | :cross_mark: | Failures |

## Message Format

Messages use Zulip's Markdown:

```
## :rocket: Production Deployment

Version 1.2.3 deployed

**Branch:** main
**Commit:** abc123

[View Details](https://github.com/...)

:check: *via RedGit*
```

## Zulip Concepts

| Concept | Description |
|---------|-------------|
| Stream | Like a channel, groups related messages |
| Topic | Thread within a stream |
| Bot | Automated account for integrations |

## Topic Behavior

- Simple messages use the default topic ("RedGit")
- Rich notifications create topics from event type and title
- e.g., "deploy: Production Deployment"

## Self-Hosted Setup

For self-hosted Zulip:

1. Use your server's URL (e.g., https://chat.example.com)
2. Create bot in Settings > Your bots
3. Subscribe bot to the target stream

## Troubleshooting

### "Failed to send message"
- Verify server URL is correct
- Check bot email and API key
- Ensure bot is subscribed to the stream

### Bot not posting
- Subscribe bot to the stream manually
- Check stream permissions
- Verify bot type is "Generic bot"

### Authentication errors
- Regenerate API key in bot settings
- Ensure email matches exactly (case-sensitive)