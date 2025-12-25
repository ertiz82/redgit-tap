# Changelog Plugin for RedGit

AI-powered changelog generation from git commits with smart deduplication and contributor statistics.

## Features

- **AI-powered summaries**: LLM generates professional release notes from commits
- **Smart deduplication**: Removes duplicate/merge commits automatically
- **Contributor statistics**: Shows contribution percentages per author
- **Multi-language support**: Generate changelogs in any language
- **Conventional commits**: Parses and groups by commit type
- **Version files**: Creates `changelogs/v1.0.0.md` files
- **Main CHANGELOG.md**: Auto-updates project changelog

## Installation

```bash
rg install changelog
```

## Commands

### Generate Changelog

```bash
# Generate for current version (auto-detects latest tag)
rg changelog generate

# Generate for specific version
rg changelog generate -v 1.2.0

# Generate from a specific tag
rg changelog generate -v 1.2.0 -f v1.1.0

# Generate from all commits
rg changelog generate -v 1.0.0 -f ""

# Skip AI summary
rg changelog generate --no-ai

# Don't update main CHANGELOG.md
rg changelog generate --no-update-main
```

### Show Changelog

```bash
# Show latest changelog
rg changelog show

# Show specific version
rg changelog show -v 1.2.0
```

### List Changelogs

```bash
rg changelog list
```

## Configuration

```yaml
# .redgit/config.yaml
plugins:
  enabled:
    - changelog
  changelog:
    enabled: true
    output_dir: changelogs      # Directory for version files
    language: tr                # Summary language (en, tr, de, fr, es)

# Or use daily.language as fallback
daily:
  language: tr
```

## Output Example

```markdown
# 1.2.0

**Release Date:** 2024-01-15
**Previous Version:** v1.1.0
**Total Commits:** 45

---

## Overview
This release focuses on improving user authentication and adding new dashboard features...

## Highlights
- **New Authentication System**: Implemented OAuth2 support...
- **Dashboard Redesign**: Completely revamped the main dashboard...

## Detailed Changes

### Authentication Improvements
The authentication system has been completely rewritten to support...

### UI/UX Enhancements
Multiple improvements to the user interface including...

---

## Commit Details

### ✨ Features (12)
- **auth:** Add OAuth2 support (`abc1234`)
- **dashboard:** New analytics widgets (`def5678`)

### 🐛 Bug Fixes (8)
- Fix login redirect issue (`ghi9012`)

---

## Contributors

- **John Doe**: 25 commits (55.6%) `███████████░░░░░░░░░`
  - +1234 / -567 lines
- **Jane Smith**: 20 commits (44.4%) `████████░░░░░░░░░░░░`
  - +890 / -234 lines
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

## Smart Deduplication

The plugin automatically removes:
- Merge commits (`Merge branch...`, `Merge pull request...`)
- Duplicate commits with same message (different hashes from cherry-picks)
- Normalized message matching (ignores punctuation, issue refs)

## Integration with Version Plugin

Works seamlessly with the version plugin:

```bash
# Release workflow
rg version release minor   # Bumps version and generates changelog
```

## License

MIT