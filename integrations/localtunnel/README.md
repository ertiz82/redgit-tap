# Localtunnel Integration

Expose local ports to the internet via [localtunnel.me](https://theboroer.github.io/localtunnel-www/).

## Features

- No signup required
- Free to use
- Optional custom subdomain
- Simple npm package

## Installation

```bash
# Install localtunnel
npm install -g localtunnel

# Install the integration
rg install localtunnel
```

## Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `subdomain` | No | Request a specific subdomain (e.g., `myapp` for `myapp.loca.lt`) |
| `host` | No | Custom localtunnel server URL |

## Usage

```bash
# Start a tunnel
rg tunnel start 8080

# Check status
rg tunnel status

# Stop the tunnel
rg tunnel stop
```

## Without Installing

You can also use localtunnel without global installation:

```bash
npx localtunnel --port 8080
```

## Custom Subdomain

Request a specific subdomain:
```bash
# In config:
subdomain: myapp
# Results in: https://myapp.loca.lt
```

Note: Subdomains are first-come-first-served and may not be available.

## Links

- [Website](https://theboroer.github.io/localtunnel-www/)
- [GitHub](https://github.com/localtunnel/localtunnel)
