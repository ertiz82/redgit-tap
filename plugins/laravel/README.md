# Laravel Plugin for RedGit

Laravel framework-specific file grouping and commit prompts.

## Features

- **Auto-detection**: Automatically activates when a Laravel project is detected
- **Version-aware**: Detects Laravel version and provides version-specific guidance
- **Smart grouping**: Separates framework/scaffold files from custom application code
- **Conventional commits**: Generates appropriate commit messages following best practices

## Installation

```bash
rg plugin install laravel
```

## How It Works

The plugin automatically detects Laravel projects by checking for:
- `artisan` file
- `laravel/framework` in `composer.json`

When activated, it:
1. Identifies framework/default files (e.g., `artisan`, default configs, migrations)
2. Groups them as "chore: add Laravel framework files"
3. Organizes custom application code by feature

## Supported Laravel Versions

- Laravel 10.x
- Laravel 11.x (with simplified structure awareness)

## File Categories

### Framework Files (grouped as "chore")
- Root files: `artisan`, `composer.json`, `package.json`, etc.
- Bootstrap: `bootstrap/app.php`, `bootstrap/providers.php`
- Default configs: `config/*.php`
- Default migrations: users, cache, jobs tables
- Default views: `welcome.blade.php`
- Storage `.gitignore` files

### Custom Application Files (grouped by feature)
- Custom models, controllers, migrations
- Custom views, routes, tests
- API endpoints
- Business logic

## License

MIT