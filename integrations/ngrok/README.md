# Ngrok Integration

Expose local ports to the internet via [ngrok](https://ngrok.com) tunnels.

## Features

- Quick tunnels without account (limited session time)
- Authenticated tunnels with auth token for longer sessions
- Region selection for lower latency
- HTTPS URLs by default

## Installation

```bash
# Install ngrok first
brew install ngrok  # macOS
# or download from https://ngrok.com/download

# Install the integration
rg install ngrok
```

## Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `auth_token` | No | Ngrok auth token for longer sessions |
| `region` | No | Server region (us, eu, ap, au, sa, jp, in) |

Get your auth token from: https://dashboard.ngrok.com/get-started/your-authtoken

## Usage

```bash
# Start a tunnel
rg tunnel start 8080

# Check status
rg tunnel status

# Stop the tunnel
rg tunnel stop

# Get the public URL
rg tunnel url
```

## Notes

- Without auth token: Free tier, 2-hour session limit
- With auth token: Extended sessions, custom domains available
- HTTPS is provided automatically
