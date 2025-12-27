# Bore Integration

Expose local ports to the internet via [bore](https://github.com/ekzhang/bore).

## Features

- Fast and secure TCP tunnel
- Written in Rust
- Minimal resource usage
- Optional authentication with secrets
- Self-hostable server

## Installation

```bash
# Install bore
cargo install bore-cli

# Or download from GitHub releases
# https://github.com/ekzhang/bore/releases

# Install the integration
rg install bore
```

## Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `server` | No | Bore server address (default: `bore.pub`) |
| `secret` | No | Secret for authenticated tunnels |

## Usage

```bash
# Start a tunnel
rg tunnel start 8080

# Check status
rg tunnel status

# Stop the tunnel
rg tunnel stop
```

## Self-Hosted Server

You can run your own bore server:

```bash
bore server --secret <your-secret>
```

Then configure the integration to use your server.

## Notes

- bore uses TCP tunneling (not HTTP)
- Public server: `bore.pub`
- Provides a random port on the public server
- URL format: `http://bore.pub:<port>`

## Links

- [GitHub](https://github.com/ekzhang/bore)
- [Releases](https://github.com/ekzhang/bore/releases)
