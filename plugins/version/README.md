# Version Plugin for RedGit

Semantic versioning management for projects with automatic file updates and git tagging.

## Features

- Auto-detects version files (package.json, pyproject.toml, etc.)
- Bumps versions following SemVer conventions
- Updates all version files automatically
- Creates git tags for releases
- Integrates with changelog plugin for automatic changelog generation

## Installation

```bash
rg install version
```

## Commands

### Show Current Version

```bash
rg version show
```

### Initialize Versioning

```bash
# Interactive initialization
rg version init

# Set specific initial version
rg version init -v 1.0.0
```

### Set Version

```bash
# Set a specific version
rg version set 1.2.0

# Set without updating project files
rg version set 1.2.0 --no-update-files
```

### Release New Version

```bash
# Bump patch version (0.1.0 -> 0.1.1)
rg version release patch

# Bump minor version (0.1.1 -> 0.2.0)
rg version release minor

# Bump major version (0.2.0 -> 1.0.0)
rg version release major

# Release without creating git tag
rg version release patch --no-tag

# Release and push tag to remote
rg version release minor --push

# Release without changelog generation
rg version release patch --no-changelog
```

### List Version History

```bash
# List all version tags
rg version list
```

## Supported Version Files

The plugin automatically detects and updates version in these files:

| File | Pattern |
|------|---------|
| `pyproject.toml` | `version = "x.y.z"` |
| `package.json` | `"version": "x.y.z"` |
| `composer.json` | `"version": "x.y.z"` |
| `setup.py` | `version="x.y.z"` |
| `version.txt` | `x.y.z` |
| `VERSION` | `x.y.z` |
| `*/__init__.py` | `__version__ = "x.y.z"` |

## Configuration

```yaml
# .redgit/config.yaml
plugins:
  enabled:
    - version
  version:
    enabled: true
    current: "1.0.0"      # Current version
    tag_prefix: "v"       # Git tag prefix (default: "v")
```

## Semantic Versioning

Follow [SemVer](https://semver.org/) conventions:

- **MAJOR**: Incompatible API changes (breaking changes)
- **MINOR**: New functionality (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

## Integration with Changelog

When the changelog plugin is enabled, version releases automatically generate changelog entries:

```bash
# Enable both plugins
rg install version
rg install changelog

# Release will automatically generate changelog
rg version release minor
```

The release command will:
1. Bump version in all files
2. Generate changelog from commits since last version
3. Create and optionally push git tag

## Release Workflow Example

```bash
# Check current version
rg version show

# Make your changes and commits
git add .
git commit -m "feat: add new feature"

# Release new minor version
rg version release minor --push

# This will:
# - Bump 1.0.0 -> 1.1.0 in all version files
# - Generate changelog for v1.1.0
# - Create git tag v1.1.0
# - Push tag to remote
```

## License

MIT