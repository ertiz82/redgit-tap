# Version Plugin for RedGit

Semantic versioning management for projects.

## Features

- Auto-detects version files (package.json, pyproject.toml, etc.)
- Bumps versions following SemVer conventions
- Updates all version files automatically
- Creates git tags
- Integrates with changelog plugin

## Installation

```bash
rg plugin install version
```

## Commands

```bash
# Initialize versioning
rg version init

# Show current version
rg version show

# Bump versions
rg version release patch   # 0.1.0 -> 0.1.1
rg version release minor   # 0.1.1 -> 0.2.0
rg version release major   # 0.2.0 -> 1.0.0

# Shortcut
rg release patch
```

## Supported Version Files

| File | Pattern |
|------|---------|
| `pyproject.toml` | `version = "x.y.z"` |
| `package.json` | `"version": "x.y.z"` |
| `composer.json` | `"version": "x.y.z"` |
| `setup.py` | `version="x.y.z"` |
| `version.txt` | `x.y.z` |
| `VERSION` | `x.y.z` |
| `__init__.py` | `__version__ = "x.y.z"` |

## Configuration

```yaml
plugins:
  version:
    enabled: true
    tag_prefix: "v"
    current: "1.0.0"
```

## Semantic Versioning

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

## Integration with Changelog

When changelog plugin is enabled, version bumps automatically generate changelog entries.

## License

MIT