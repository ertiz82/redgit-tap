# Telegram Integration for RedGit

Send notifications to Telegram chats via Bot API.

## Features

- **Bot Notifications**: Send messages to any chat, group, or channel
- **Rich Formatting**: HTML formatted messages with links
- **Event Types**: Different emojis for commits, PRs, deploys, etc.
- **Multiple Chats**: Override default chat per notification

## Installation

```bash
rg install telegram
```

## Setup

### 1. Create a Bot

1. Open Telegram and search for @BotFather
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Get Chat ID

For **private chats**: Send a message to your bot, then visit:
```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

For **groups**: Add bot to group, send a message, check getUpdates

For **channels**: Add bot as admin, use `@channelname` as chat_id

### Configuration

```yaml
integrations:
  telegram:
    bot_token: "123456:ABC-DEF..."  # Or TELEGRAM_BOT_TOKEN env var
    chat_id: "123456789"            # Or TELEGRAM_CHAT_ID env var
    parse_mode: "HTML"

active:
  notification: telegram
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

| Level | Icon | Use Case |
|-------|------|----------|
| info | Blue circle | General notifications |
| success | Check mark | Successful operations |
| warning | Warning sign | Warnings |
| error | X mark | Failures |

## Message Format

Messages are sent with HTML formatting:

```
:rocket: Production Deployment

Version 1.2.3 deployed to production

Branch: main
Commit: abc123

View Details

:white_check_mark: via RedGit
```

## Chat Types

| Type | Chat ID Format | Notes |
|------|---------------|-------|
| Private | `123456789` | Numeric user ID |
| Group | `-123456789` | Negative number |
| Supergroup | `-100123456789` | Starts with -100 |
| Channel | `@channelname` | Username with @ |

## Troubleshooting

### "Failed to send message"
- Verify bot token is correct
- Make sure bot is added to the chat
- For channels, bot must be an admin

### Bot not responding
- Check bot token with `/getMe` API call
- Ensure bot hasn't been blocked

### Getting Chat ID
1. Add @userinfobot to your chat
2. It will reply with the chat ID
3. Or use the getUpdates API method