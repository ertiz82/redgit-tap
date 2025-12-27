"""
Version Plugin - Semantic versioning management for projects.

Commands:
    rg version init          - Initialize versioning, ask for starting version
    rg version show          - Show current version
    rg version release patch - Bump patch version (0.1.0 -> 0.1.1)
    rg version release minor - Bump minor version (0.1.1 -> 0.2.0)
    rg version release major - Bump major version (0.2.0 -> 1.0.0)

Also available as shortcuts:
    rg release patch/minor/major
"""

import re
import json
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass

try:
    from redgit.plugins.base import Plugin
    from redgit.core.config import ConfigManager, RETGIT_DIR
except ImportError:
    # Fallback for standalone usage
    class Plugin:
        name = ""
        def match(self) -> bool: return False
        def get_prompt(self) -> Optional[str]: return None
        def get_groups(self, changes: list) -> list: return []

    class ConfigManager:
        def load(self): return {}
        def save(self, config): pass

    RETGIT_DIR = Path(".redgit")


@dataclass
class VersionInfo:
    major: int
    minor: int
    patch: int

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def parse(cls, version_str: str) -> "VersionInfo":
        """Parse version string like '1.2.3' or 'v1.2.3'"""
        version_str = version_str.lstrip("v")
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version_str)
        if not match:
            raise ValueError(f"Invalid version format: {version_str}")
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3))
        )

    def bump(self, level: str) -> "VersionInfo":
        """Return new version bumped by level"""
        if level == "major":
            return VersionInfo(self.major + 1, 0, 0)
        elif level == "minor":
            return VersionInfo(self.major, self.minor + 1, 0)
        elif level == "patch":
            return VersionInfo(self.major, self.minor, self.patch + 1)
        else:
            raise ValueError(f"Invalid bump level: {level}")


class VersionPlugin(Plugin):
    """Version management plugin with semantic versioning support."""

    name = "version"

    # Supported version file patterns
    VERSION_FILES = [
        ("pyproject.toml", r'version\s*=\s*["\']([^"\']+)["\']'),
        ("package.json", r'"version"\s*:\s*"([^"]+)"'),
        ("composer.json", r'"version"\s*:\s*"([^"]+)"'),
        ("setup.py", r'version\s*=\s*["\']([^"\']+)["\']'),
        ("version.txt", r'^(\d+\.\d+\.\d+)'),
        ("VERSION", r'^(\d+\.\d+\.\d+)'),
    ]

    # Python __init__.py pattern
    INIT_PATTERN = r'__version__\s*=\s*["\']([^"\']+)["\']'

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self._config = None

    @property
    def config(self) -> dict:
        if self._config is None:
            full_config = self.config_manager.load()
            self._config = full_config.get("plugins", {}).get("version", {})
        return self._config

    def match(self) -> bool:
        """Check if version plugin is enabled or can be used."""
        # Always available if any version file exists
        return self.detect_version_file() is not None

    def detect_version_file(self) -> Optional[Tuple[str, str]]:
        """
        Detect which version file exists in the project.

        Returns:
            Tuple of (filename, regex_pattern) or None
        """
        for filename, pattern in self.VERSION_FILES:
            if Path(filename).exists():
                return (filename, pattern)

        # Check for Python __init__.py files
        for init_file in Path(".").rglob("__init__.py"):
            # Skip venv, node_modules, etc.
            if any(part.startswith(".") or part in ["venv", "node_modules", "vendor"]
                   for part in init_file.parts):
                continue
            content = init_file.read_text()
            if "__version__" in content:
                return (str(init_file), self.INIT_PATTERN)

        return None

    def get_current_version(self) -> Optional[VersionInfo]:
        """Get current version from config or detect from files."""
        # First check config
        config_version = self.config.get("current")
        if config_version:
            try:
                return VersionInfo.parse(config_version)
            except ValueError:
                pass

        # Detect from files
        file_info = self.detect_version_file()
        if not file_info:
            return None

        filename, pattern = file_info
        content = Path(filename).read_text()
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            try:
                return VersionInfo.parse(match.group(1))
            except ValueError:
                pass

        return None

    def get_version_files(self) -> List[Tuple[Path, str]]:
        """Get all version files that should be updated."""
        files = []

        for filename, pattern in self.VERSION_FILES:
            path = Path(filename)
            if path.exists():
                files.append((path, pattern))

        # Check for Python __init__.py files
        for init_file in Path(".").rglob("__init__.py"):
            if any(part.startswith(".") or part in ["venv", "node_modules", "vendor"]
                   for part in init_file.parts):
                continue
            content = init_file.read_text()
            if "__version__" in content:
                files.append((init_file, self.INIT_PATTERN))

        return files

    def update_version_in_file(self, filepath: Path, pattern: str,
                                old_version: str, new_version: str) -> bool:
        """Update version in a single file."""
        try:
            content = filepath.read_text()

            # Special handling for JSON files
            if filepath.suffix == ".json":
                data = json.loads(content)
                if "version" in data:
                    data["version"] = new_version
                    filepath.write_text(json.dumps(data, indent=2) + "\n")
                    return True

            # Regex replacement for other files
            new_content = re.sub(
                pattern,
                lambda m: m.group(0).replace(old_version, new_version),
                content
            )

            if new_content != content:
                filepath.write_text(new_content)
                return True

            return False
        except Exception:
            return False

    def update_all_versions(self, old_version: VersionInfo,
                           new_version: VersionInfo) -> List[str]:
        """Update version in all detected files."""
        updated_files = []

        for filepath, pattern in self.get_version_files():
            if self.update_version_in_file(
                filepath, pattern, str(old_version), str(new_version)
            ):
                updated_files.append(str(filepath))

        return updated_files

    def save_version_to_config(self, version: VersionInfo):
        """Save current version to config."""
        config = self.config_manager.load()
        if "plugins" not in config:
            config["plugins"] = {}
        if "version" not in config["plugins"]:
            config["plugins"]["version"] = {}

        config["plugins"]["version"]["current"] = str(version)
        config["plugins"]["version"]["enabled"] = True
        self.config_manager.save(config)

    def get_tag_prefix(self) -> str:
        """Get git tag prefix from config."""
        return self.config.get("tag_prefix", "v")

    def get_previous_major_version(self, current: VersionInfo) -> Optional[str]:
        """Get the previous major version tag."""
        if current.major == 0:
            return None
        return f"{self.get_tag_prefix()}{current.major - 1}.0.0"

    def is_changelog_enabled(self) -> bool:
        """Check if changelog plugin is enabled."""
        config = self.config_manager.load()
        plugins_config = config.get("plugins", {})
        # Check enabled list first
        enabled_list = plugins_config.get("enabled", [])
        if "changelog" in enabled_list:
            return True
        # Fallback to changelog.enabled flag
        return plugins_config.get("changelog", {}).get("enabled", False)