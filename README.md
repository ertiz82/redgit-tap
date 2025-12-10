# RedGit Tap

Official repository of RedGit integrations and plugins.

## Installation

Install integrations and plugins directly from this tap:

```bash
# Install an integration
rg install slack

# Install a plugin
rg install plugin:changelog

# Install specific version
rg install slack@v1.0.0
```

## Available Integrations

| Name | Description | Type |
|------|-------------|------|
| [slack](./integrations/slack) | Send notifications to Slack | Notification |

## Available Plugins

*Coming soon...*

## Creating Your Own

### Integration Structure

```
integrations/my-integration/
├── __init__.py          # Integration class (required)
├── commands.py          # CLI commands (optional)
├── install_schema.json  # Installation wizard (optional)
└── README.md            # Documentation
```

### Plugin Structure

```
plugins/my-plugin/
├── __init__.py          # Plugin class (required)
├── commands.py          # CLI commands (optional)
└── README.md            # Documentation
```

## Contributing

1. Fork this repository
2. Create your integration/plugin
3. Update `index.json`
4. Submit a pull request

## License

MIT License