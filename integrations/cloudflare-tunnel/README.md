# Cloudflare Tunnel Integration

Expose local ports to the internet via [Cloudflare Tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).

## Features

- Quick tunnels without Cloudflare account
- Fast, global network
- Free to use
- HTTPS by default
- Optional: Named tunnels for persistent URLs

## Installation

```bash
# Install cloudflared first
brew install cloudflared  # macOS

# Linux
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Install the integration
rg install cloudflare-tunnel
```

## Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `tunnel_id` | No | Named tunnel ID for persistent URLs |

## Usage

```bash
# Start a tunnel (quick tunnel - random URL)
rg tunnel start 8080

# Check status
rg tunnel status

# Stop the tunnel
rg tunnel stop
```

## Quick Tunnels vs Named Tunnels

**Quick Tunnels:**
- No account needed
- Random `*.trycloudflare.com` URL
- Perfect for temporary access

**Named Tunnels:**
- Requires Cloudflare account
- Persistent URLs
- Better for production use

Create a named tunnel:
```bash
cloudflared tunnel login
cloudflared tunnel create my-tunnel
# Use the tunnel ID in configuration
```

## Links

- [Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)