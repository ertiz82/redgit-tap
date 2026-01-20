# Sentry Integration for RedGit

Error tracking and monitoring integration with Sentry.

## Features

- Automatic error-to-file matching during `rg propose`
- Add `Fixes: SENTRY-XXX` references to commit messages
- Link commits to Sentry issues
- Auto-resolve errors on commit (optional)
- CLI commands for error management
- Release tracking and association

## Installation

```bash
rg install sentry
```

## Configuration

```yaml
integrations:
  sentry:
    organization: "my-org"
    project_slug: "my-project"
    # API token: Use SENTRY_AUTH_TOKEN env var or auth_token field

    # Optional settings
    environment: "production"  # Default environment filter
    auto_resolve: false        # Auto-resolve errors when linked to commits
    min_confidence: 0.5        # Minimum match confidence (0.0-1.0)

active:
  error_tracking: sentry
```

## Environment Variables

- `SENTRY_AUTH_TOKEN`: Sentry Auth Token (recommended)
  - Create at: https://sentry.io/settings/account/api/auth-tokens/
  - Required scopes: `project:read`, `event:read`, `issue:write`

## How It Works

### Automatic Error Matching

When you run `rg propose`, the integration:

1. Fetches unresolved errors from Sentry
2. Matches error stacktraces against your changed files
3. Shows potential error fixes with confidence scores
4. Adds `Fixes: SENTRY-XXX` references to commit messages

```
$ rg propose

🐛 Error Tracking
   Found 2 potential error fixes:
   • SENTRY-ABC123: TypeError: Cannot read property 'x' of undefined... (95% match)
   • SENTRY-DEF456: ReferenceError: foo is not defined... (80% match)

Processing matched groups...
(1/2) PROJ-123: Fix auth flow...
   🐛 Fixes: SENTRY-ABC123
   ✓ Committed and merged feature/proj-123-fix-auth-flow
```

### Commit Message Format

Error references are automatically added to commit messages:

```
feat: fix authentication error handling

Implemented proper null checks in auth flow.

Refs: PROJ-123
Fixes: SENTRY-ABC123

🤖 Generated with RedGit
```

### Auto-Resolve

When `auto_resolve: true` is configured, linked errors are automatically marked as resolved after the commit is created.

## Commands

### List Errors

```bash
# List unresolved errors
rg sentry list

# Filter by status
rg sentry list --status resolved
rg sentry list --status ignored

# Filter by environment
rg sentry list --env staging

# Limit results
rg sentry list --limit 50
```

### Show Error Details

```bash
# Basic details
rg sentry show SENTRY-ABC123

# With recent events
rg sentry show SENTRY-ABC123 --events

# With full stacktrace
rg sentry show SENTRY-ABC123 --stacktrace
```

### Link Commit to Error

```bash
# Link current HEAD commit
rg sentry link SENTRY-ABC123

# Link specific commit
rg sentry link SENTRY-ABC123 --commit abc123def
```

### Resolve Errors

```bash
# Mark as resolved
rg sentry resolve SENTRY-ABC123

# Mark as ignored
rg sentry resolve SENTRY-ABC123 --status ignored

# Resolve in specific release
rg sentry resolve SENTRY-ABC123 --release v1.2.3
```

### Project Status

```bash
# Show error statistics
rg sentry status

# Filter by environment
rg sentry status --env production
```

### List Releases

```bash
# Show recent releases
rg sentry releases

# Limit results
rg sentry releases --limit 20
```

## Matching Algorithm

The integration uses a confidence-based matching algorithm:

| Match Type | Confidence | Description |
|------------|------------|-------------|
| Exact file match | 100% | Changed file exactly matches error location |
| Stacktrace exact | 95% | Changed file appears in error stacktrace |
| Stacktrace file | 90% | Changed file path matches stacktrace entry |
| Basename match | 80% | Filename matches (different directories) |
| Stacktrace basename | 60% | Filename in stacktrace matches changed file |

Files are only matched if confidence exceeds `min_confidence` (default: 50%).

## API Features

### Error Management
- Fetch recent errors with filters
- Get detailed error information
- Access individual events
- View stacktraces and affected files

### Commit Linking
- Link commits to error issues
- Add comments with commit info
- Track fix associations

### Status Management
- Resolve errors
- Ignore errors
- Reopen errors
- Resolve in specific releases

### Release Tracking
- List releases
- Create releases
- Associate commits with releases

## Self-Hosted Sentry

For self-hosted Sentry installations, configure a custom base URL:

```yaml
integrations:
  sentry:
    organization: "my-org"
    project_slug: "my-project"
    base_url: "https://sentry.mycompany.com/api/0"
```

## Troubleshooting

### No Errors Found

- Verify `organization` and `project_slug` are correct
- Check that the auth token has required scopes
- Ensure there are unresolved errors in the specified environment

### Low Match Confidence

- The algorithm relies on file paths in stacktraces
- Make sure source maps are configured for JavaScript projects
- Python projects typically have good stacktrace paths

### API Rate Limits

Sentry has API rate limits. If you encounter issues:
- Reduce `--limit` values in commands
- Avoid rapid successive requests

## License

MIT
