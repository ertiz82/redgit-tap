# Microsoft Teams Integration for RedGit

Send notifications to Teams channels and direct messages.

## Features

### Graph API Mode (Recommended)
- **Full Teams Access**: List teams, channels, and users
- **Channel Messages**: Send to any channel you have access to
- **Direct Messages**: Send DMs to any user in your organization
- **Device Code Flow**: Secure authentication without storing passwords

### Webhook Mode (Simple)
- **Quick Setup**: Just paste a webhook URL
- **Single Channel**: Notifications to one configured channel
- **No Auth Required**: Works immediately after setup

## Installation

```bash
rg install msteams
```

## Setup Options

### Option 1: Graph API (Full Features)

#### Step 1: Create Azure AD App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Configure:
   - **Name**: `RedGit Teams Integration`
   - **Supported account types**: `Accounts in this organizational directory only`
   - **Redirect URI**: Leave empty
5. Click **Register**

#### Step 2: Note Required Values

From the **Overview** page, copy:
- **Application (client) ID**
- **Directory (tenant) ID**

#### Step 3: Configure API Permissions

1. Go to **API permissions** > **Add a permission** > **Microsoft Graph** > **Delegated permissions**
2. Add these permissions:

| Permission | Purpose |
|------------|---------|
| User.Read.All | List users for DM targeting |
| Team.ReadBasic.All | List teams |
| Channel.ReadBasic.All | List channels |
| ChannelMessage.Send | Send to channels |
| ChatMessage.Send | Send direct messages |
| Chat.Create | Create 1:1 chats |
| offline_access | Refresh tokens |

3. Click **Grant admin consent for [Your Org]**

#### Step 4: Enable Public Client Flow

1. Go to **Authentication**
2. Under **Advanced settings**, set **Allow public client flows** to **Yes**
3. Click **Save**

#### Step 5: Configure RedGit

```bash
# Install and configure
rg install msteams
# Enter tenant_id and client_id when prompted

# Authenticate
rg msteams login
# Follow the device code flow in your browser
```

### Option 2: Webhook (Simple Notifications)

1. Open Microsoft Teams
2. Go to the channel you want notifications in
3. Click "..." > "Connectors"
4. Find "Incoming Webhook" and click "Configure"
5. Name your webhook (e.g., "RedGit")
6. Copy the webhook URL

```bash
rg install msteams
# Enter the webhook URL when prompted
```

## CLI Commands

### Authentication

```bash
# Login with Device Code Flow
rg msteams login

# Check status
rg msteams status

# Logout (clear tokens)
rg msteams logout
```

### Discovery

```bash
# List accessible teams
rg msteams list

# List channels in a team
rg msteams channels <team-id>

# List users (for DM targeting)
rg msteams users
rg msteams users --search "ali"
```

### Sending Messages

```bash
# Send to default channel
rg msteams send "Hello Teams!"

# Send to specific channel
rg msteams send "Build complete" --team <team-id> --channel <channel-id>

# Send direct message
rg msteams send "PR ready for review" --email user@company.com

# Set default channel
rg msteams set-default --team <team-id> --channel <channel-id>
```

### Notifications (via rg notify)

```bash
# Simple message
rg notify "Deployment complete"

# With level (changes color)
rg notify "Tests passed" --level success
rg notify "Build failed" --level error

# With title
rg notify "Version 2.0 deployed" --title "Production Deploy"
```

## Configuration

```yaml
# .redgit/config.yaml
integrations:
  msteams:
    enabled: true
    # Graph API (full features)
    tenant_id: "your-tenant-id"
    client_id: "your-client-id"
    access_token: "..."      # Set by rg msteams login
    refresh_token: "..."     # Set by rg msteams login
    default_team_id: "..."   # Set by rg msteams set-default
    default_channel_id: "..."
    # Webhook (simple mode)
    webhook_url: "https://outlook.office.com/webhook/..."

active:
  notification: msteams
```

## Notification Levels

| Level | Color | Use Case |
|-------|-------|----------|
| info | Blue | General notifications |
| success | Green | Successful operations |
| warning | Yellow | Warnings |
| error | Red | Failures |

## Troubleshooting

### "AADSTS50076: Application requires MFA"
- Complete MFA in the browser during Device Code Flow login

### "AADSTS65001: User has not consented"
- Admin consent not granted. Ask your Azure AD admin to grant consent.

### "Insufficient privileges"
- API permissions not granted. Check Step 3 in Graph API setup.

### "Not authenticated"
- Run `rg msteams login` to authenticate

### Webhook messages not appearing
- Verify webhook URL is correct
- Check channel permissions
- Try recreating the webhook connector

## Security Notes

- Access tokens expire after 1 hour (auto-refreshed)
- Refresh tokens expire after 90 days (re-login required)
- Tokens stored in `.redgit/config.yaml` (add to .gitignore)
- Graph API permissions are delegated (user context)