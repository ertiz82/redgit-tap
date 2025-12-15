"""
Laravel plugin for RedGit.

Laravel framework-specific file grouping and commit prompts.
"""

import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple

try:
    from redgit.plugins.base import Plugin
except ImportError:
    # Fallback for standalone usage
    class Plugin:
        name = ""
        def match(self) -> bool: return False
        def get_prompt(self) -> Optional[str]: return None
        def get_groups(self, changes: list) -> list: return []


class LaravelPlugin(Plugin):
    """Laravel framework plugin - Laravel-specific file grouping and prompts"""
    name = "laravel"

    # Laravel default/framework files by version
    # These files come with fresh Laravel installation
    LARAVEL_FRAMEWORK_FILES = {
        # Common across all versions
        "common": [
            # Root files
            "artisan",
            ".editorconfig",
            ".gitattributes",
            ".gitignore",
            "composer.json",
            "composer.lock",
            "package.json",
            "package-lock.json",
            "phpunit.xml",
            "vite.config.js",
            "webpack.mix.js",
            "tailwind.config.js",
            "postcss.config.js",

            # Bootstrap
            "bootstrap/app.php",
            "bootstrap/cache/.gitignore",
            "bootstrap/providers.php",

            # Config files
            "config/app.php",
            "config/auth.php",
            "config/broadcasting.php",
            "config/cache.php",
            "config/cors.php",
            "config/database.php",
            "config/filesystems.php",
            "config/hashing.php",
            "config/logging.php",
            "config/mail.php",
            "config/queue.php",
            "config/sanctum.php",
            "config/services.php",
            "config/session.php",
            "config/view.php",

            # Database
            "database/.gitignore",
            "database/database.sqlite",
            "database/seeders/DatabaseSeeder.php",
            "database/factories/UserFactory.php",

            # Default migrations
            "database/migrations/0001_01_01_000000_create_users_table.php",
            "database/migrations/0001_01_01_000001_create_cache_table.php",
            "database/migrations/0001_01_01_000002_create_jobs_table.php",
            "database/migrations/2014_10_12_000000_create_users_table.php",
            "database/migrations/2014_10_12_100000_create_password_resets_table.php",
            "database/migrations/2014_10_12_100000_create_password_reset_tokens_table.php",
            "database/migrations/2019_08_19_000000_create_failed_jobs_table.php",
            "database/migrations/2019_12_14_000001_create_personal_access_tokens_table.php",

            # Public
            "public/.htaccess",
            "public/index.php",
            "public/robots.txt",
            "public/favicon.ico",

            # Resources
            "resources/css/app.css",
            "resources/js/app.js",
            "resources/js/bootstrap.js",
            "resources/views/welcome.blade.php",

            # Routes
            "routes/api.php",
            "routes/channels.php",
            "routes/console.php",
            "routes/web.php",

            # Storage
            "storage/app/.gitignore",
            "storage/app/public/.gitignore",
            "storage/framework/.gitignore",
            "storage/framework/cache/.gitignore",
            "storage/framework/cache/data/.gitignore",
            "storage/framework/sessions/.gitignore",
            "storage/framework/testing/.gitignore",
            "storage/framework/views/.gitignore",
            "storage/logs/.gitignore",

            # Tests
            "tests/CreatesApplication.php",
            "tests/TestCase.php",
            "tests/Feature/ExampleTest.php",
            "tests/Unit/ExampleTest.php",

            # App - Core
            "app/Models/User.php",
            "app/Providers/AppServiceProvider.php",
            "app/Http/Kernel.php",
            "app/Console/Kernel.php",
            "app/Exceptions/Handler.php",

            # Laravel 11+ structure
            "app/Providers/RouteServiceProvider.php",
            "app/Http/Controllers/Controller.php",
            "app/Http/Middleware/Authenticate.php",
            "app/Http/Middleware/EncryptCookies.php",
            "app/Http/Middleware/PreventRequestsDuringMaintenance.php",
            "app/Http/Middleware/RedirectIfAuthenticated.php",
            "app/Http/Middleware/TrimStrings.php",
            "app/Http/Middleware/TrustHosts.php",
            "app/Http/Middleware/TrustProxies.php",
            "app/Http/Middleware/ValidateSignature.php",
            "app/Http/Middleware/VerifyCsrfToken.php",
        ],
    }

    # Patterns for framework files (regex)
    FRAMEWORK_PATTERNS = [
        r"^storage/.*\.gitignore$",
        r"^bootstrap/cache/.*",
        r"^public/\.(htaccess|gitignore)$",
    ]

    def __init__(self):
        super().__init__()
        self._version = None
        self._framework_files = None

    def match(self) -> bool:
        """Check if this is a Laravel project"""
        if not Path("artisan").exists():
            return False
        if not Path("composer.json").exists():
            return False
        try:
            content = Path("composer.json").read_text()
            return "laravel/framework" in content.lower()
        except Exception:
            return False

    def get_laravel_version(self) -> Optional[str]:
        """Detect Laravel version from composer.json or composer.lock"""
        if self._version:
            return self._version

        # Try composer.lock first (more accurate)
        if Path("composer.lock").exists():
            try:
                lock = json.loads(Path("composer.lock").read_text())
                for pkg in lock.get("packages", []):
                    if pkg.get("name") == "laravel/framework":
                        self._version = pkg.get("version", "").lstrip("v")
                        return self._version
            except Exception:
                pass

        # Fallback to composer.json
        if Path("composer.json").exists():
            try:
                composer = json.loads(Path("composer.json").read_text())
                req = composer.get("require", {}).get("laravel/framework", "")
                # Extract version from constraint like "^11.0" or "~10.0"
                match = re.search(r"[\d]+\.[\d]+", req)
                if match:
                    self._version = match.group()
                    return self._version
            except Exception:
                pass

        return None

    def get_major_version(self) -> Optional[int]:
        """Get Laravel major version number"""
        version = self.get_laravel_version()
        if version:
            try:
                return int(version.split(".")[0])
            except (ValueError, IndexError):
                pass
        return None

    def is_framework_file(self, file_path: str) -> bool:
        """Check if a file is a Laravel framework/default file"""
        # Normalize path
        file_path = file_path.replace("\\", "/")

        # Check exact matches
        framework_files = self.LARAVEL_FRAMEWORK_FILES.get("common", [])
        if file_path in framework_files:
            return True

        # Check patterns
        for pattern in self.FRAMEWORK_PATTERNS:
            if re.match(pattern, file_path):
                return True

        return False

    def categorize_files(self, changes: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Separate framework files from custom project files.

        Returns:
            (framework_files, project_files)
        """
        framework = []
        project = []

        for change in changes:
            file_path = change.get("file", "")
            if self.is_framework_file(file_path):
                framework.append(change)
            else:
                project.append(change)

        return framework, project

    def get_prompt(self) -> Optional[str]:
        """Return Laravel-specific prompt"""
        version = self.get_laravel_version() or "unknown"
        major = self.get_major_version()

        version_note = ""
        if major and major >= 11:
            version_note = """
## Laravel 11+ Notes
- Laravel 11 has a simplified structure
- No more app/Http/Kernel.php (middleware in bootstrap/app.php)
- Fewer default service providers
- Config files may be published on demand
"""
        elif major and major >= 10:
            version_note = """
## Laravel 10 Notes
- Uses traditional app structure
- Service providers in app/Providers/
- Middleware in app/Http/Middleware/
"""

        return f"""# Laravel {version} Project Commit Grouping

You are a senior Laravel developer. Analyze the following file changes and group them into logical commits.

{version_note}

## CRITICAL RULES

1. **YOU MUST INCLUDE EVERY FILE** - Do not skip any files. Every file in the list below MUST appear in exactly one group.
2. **Framework/default files should be grouped together** as "chore: add Laravel framework files" or "chore: initial Laravel setup"
3. **Custom application code should be grouped by feature**

## File Categories

### Framework/Default Files (group together as "chore"):
- `artisan`, `composer.json`, `package.json`, `vite.config.js`
- `bootstrap/app.php`, `bootstrap/providers.php`
- `config/*.php` (default configs)
- `public/index.php`, `public/.htaccess`
- `routes/web.php`, `routes/api.php`, `routes/console.php`, `routes/channels.php`
- `storage/**/.gitignore`
- `database/migrations/*_create_users_table.php`, `*_create_cache_table.php`, `*_create_jobs_table.php`
- `database/seeders/DatabaseSeeder.php`, `database/factories/UserFactory.php`
- `resources/views/welcome.blade.php`
- `resources/css/app.css`, `resources/js/app.js`, `resources/js/bootstrap.js`
- `tests/TestCase.php`, `tests/CreatesApplication.php`, `tests/Feature/ExampleTest.php`, `tests/Unit/ExampleTest.php`
- `app/Models/User.php`, `app/Providers/AppServiceProvider.php`
- `app/Http/Controllers/Controller.php` (base controller)
- Default middleware files

### Custom Application Files (group by feature):
- Custom models in `app/Models/`
- Custom controllers in `app/Http/Controllers/`
- Custom migrations (not users/cache/jobs)
- Custom views, routes, tests
- API endpoints
- Business logic

## File Changes

{{FILES}}

## Output Instructions

1. **First group**: All framework/default Laravel files as "chore: add Laravel framework/scaffold files"
2. **Remaining groups**: Custom application code grouped by feature
3. **Every file MUST be in exactly one group** - count the files!
4. Use conventional commits: feat, fix, chore, refactor, test, docs
5. If unsure about a file, put it in the "chore" framework group
"""

    def pre_process_changes(self, changes: List[Dict]) -> Dict:
        """
        Pre-process changes to identify framework vs custom files.
        This info can be passed to the prompt.
        """
        framework, project = self.categorize_files(changes)
        return {
            "framework_files": framework,
            "project_files": project,
            "framework_count": len(framework),
            "project_count": len(project),
            "laravel_version": self.get_laravel_version(),
        }

    def get_groups(self, changes: list) -> list:
        """
        Pre-group framework files, let AI handle the rest.
        """
        # For now, let AI handle all grouping with enhanced prompt
        # Could implement pre-grouping here in the future
        return []