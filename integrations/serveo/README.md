# Serveo Integration

Expose local ports to the internet via [serveo.net](https://serveo.net).

## Features

- **No installation required** - uses SSH
- Free to use
- Optional custom subdomain
- Works anywhere SSH is available

## Installation

```bash
# No external tool installation needed!
# Just install the integration
rg install serveo
```

## Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `subdomain` | No | Request a specific subdomain (e.g., `myapp` for `myapp.serveo.net`) |

## Usage

```bash
# Start a tunnel
rg tunnel start 8080

# Check status
rg tunnel status

# Stop the tunnel
rg tunnel stop
```

## Manual Usage

You can also use serveo directly with SSH:

```bash
# Random subdomain
ssh -R 80:localhost:8080 serveo.net

# Custom subdomain
ssh -R myapp:80:localhost:8080 serveo.net
```

## How It Works

Serveo uses SSH remote port forwarding to expose your local port. When you connect, it provides a public URL like `https://xxx.serveo.net`.

## Notes

- No signup or account required
- Uses your existing SSH client
- HTTPS provided automatically
- Custom subdomains are first-come-first-served

## Links

- [Website](https://serveo.net)
