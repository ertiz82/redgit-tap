# Changelog Plugin for RedGit

Automatic changelog generation from git commits.

## Features

- Groups commits by type (feat, fix, chore, etc.)
- Creates version-specific files in `changelogs/` directory
- Updates main `CHANGELOG.md` file
- Parses conventional commit format
- Supports custom output directory

## Installation

```bash
rg plugin install changelog
```

## Commands

```bash
# Initialize changelog plugin
rg changelog init

# Generate changelog for a version
rg changelog generate v1.0.0

# Show current changelog
rg changelog show
```

## Commit Types

| Type | Display | Emoji |
|------|---------|-------|
| feat | Features | ✨ |
| fix | Bug Fixes | 🐛 |
| perf | Performance | ⚡ |
| refactor | Refactoring | ♻️ |
| docs | Documentation | 📚 |
| test | Tests | 🧪 |
| chore | Chores | 🔧 |
| style | Styles | 💄 |
| ci | CI/CD | 👷 |
| build | Build | 📦 |

## Configuration

```yaml
plugins:
  changelog:
    enabled: true
    output_dir: changelogs
    group_by_type: true
```

## Output Example

```markdown
# v1.0.0

**Release Date:** 2024-01-15
**Commits:** 12

---

## ✨ Features

- **auth:** Add user authentication (`abc1234`)
- Add dashboard view (`def5678`)

## 🐛 Bug Fixes

- Fix login redirect issue (`ghi9012`)
```

## License

MIT