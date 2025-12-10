# WhatsApp Integration for RedGit

Send notifications via WhatsApp Business Cloud API.

## Features

- **Direct Messages**: Send notifications to WhatsApp numbers
- **Rich Text**: Basic formatting with bold and italic
- **Link Previews**: URLs are automatically previewed
- **Event Types**: Different emojis for commits, PRs, deploys, etc.

## Installation

```bash
rg install whatsapp
```

## Setup

### Prerequisites

1. Meta Business Account
2. WhatsApp Business Account
3. Registered phone number on WhatsApp Business

### Get Credentials

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create or select an app with WhatsApp product
3. In WhatsApp > API Setup:
   - Copy Phone Number ID
   - Generate a permanent access token

### Configuration

```yaml
integrations:
  whatsapp:
    access_token: "xxx"      # Or WHATSAPP_ACCESS_TOKEN env var
    phone_number_id: "xxx"   # Or WHATSAPP_PHONE_NUMBER_ID env var
    recipient_number: "1234567890"  # Or WHATSAPP_RECIPIENT_NUMBER env var

active:
  notification: whatsapp
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

Messages use WhatsApp formatting:

```
:rocket: *Production Deployment*

Version 1.2.3 deployed

*Branch:* main
*Commit:* abc123

https://github.com/...

:white_check_mark: _via RedGit_
```

## Phone Number Format

Use international format without + or spaces:
- US: `14155551234`
- UK: `447911123456`
- India: `919876543210`

## Important Notes

### 24-Hour Window
WhatsApp requires recipients to message your business first. After that, you have a 24-hour window to send messages.

### Template Messages
For messages outside the 24-hour window, you'd need pre-approved templates (not currently supported by this integration).

### Rate Limits
The Cloud API has rate limits based on your business tier:
- Unverified: 250 messages/day
- Verified: 1,000+ messages/day

## Troubleshooting

### "Failed to send message"
- Verify access token is valid
- Check phone number ID is correct
- Ensure recipient has messaged your business first

### Token expired
- Generate a new permanent token in Meta Business Suite
- System user tokens don't expire

### Recipient not receiving
- Confirm phone number format (no + or spaces)
- Check recipient hasn't blocked your business
- Verify 24-hour messaging window

### API errors
- Check Meta Business Suite for error details
- Ensure your app has WhatsApp product enabled
- Verify phone number is properly registered