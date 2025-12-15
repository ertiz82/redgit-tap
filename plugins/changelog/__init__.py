"""
Changelog Plugin - Automatic changelog generation from git commits.

Commands:
    rg changelog init       - Initialize changelog plugin
    rg changelog generate   - Generate changelog for current version
    rg changelog show       - Show current changelog

Features:
    - Groups commits by type (feat, fix, chore, etc.)
    - Creates version-specific files (changelogs/v1.0.0.md)
    - Updates main CHANGELOG.md
    - Integrates with version plugin for major releases
"""

import re
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime

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
class CommitInfo:
    hash: str
    type: str
    scope: Optional[str]
    message: str
    body: Optional[str]
    date: datetime

    @classmethod
    def parse(cls, hash: str, full_message: str, date: datetime) -> "CommitInfo":
        """Parse a commit message into structured info."""
        lines = full_message.strip().split("\n")
        first_line = lines[0]
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else None

        # Parse conventional commit format: type(scope): message
        match = re.match(r"^(\w+)(?:\(([^)]+)\))?\s*:\s*(.+)$", first_line)
        if match:
            return cls(
                hash=hash[:7],
                type=match.group(1),
                scope=match.group(2),
                message=match.group(3),
                body=body,
                date=date
            )

        # Non-conventional commit
        return cls(
            hash=hash[:7],
            type="other",
            scope=None,
            message=first_line,
            body=body,
            date=date
        )


class ChangelogPlugin(Plugin):
    """Changelog generation plugin."""

    name = "changelog"

    # Commit type display names and order
    TYPE_DISPLAY = {
        "feat": ("Features", "✨"),
        "fix": ("Bug Fixes", "🐛"),
        "perf": ("Performance", "⚡"),
        "refactor": ("Refactoring", "♻️"),
        "docs": ("Documentation", "📚"),
        "test": ("Tests", "🧪"),
        "chore": ("Chores", "🔧"),
        "style": ("Styles", "💄"),
        "ci": ("CI/CD", "👷"),
        "build": ("Build", "📦"),
        "other": ("Other", "📝"),
    }

    TYPE_ORDER = ["feat", "fix", "perf", "refactor", "docs", "test", "chore", "style", "ci", "build", "other"]

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self._config = None

    @property
    def config(self) -> dict:
        if self._config is None:
            full_config = self.config_manager.load()
            self._config = full_config.get("plugins", {}).get("changelog", {})
        return self._config

    def match(self) -> bool:
        """Changelog plugin can always be used if in a git repo."""
        return Path(".git").exists()

    def get_commits_between(self, from_ref: Optional[str], to_ref: str = "HEAD") -> List[CommitInfo]:
        """Get commits between two refs."""
        try:
            from git import Repo
            repo = Repo(".")

            if from_ref:
                # Check if from_ref exists
                try:
                    repo.commit(from_ref)
                    range_spec = f"{from_ref}..{to_ref}"
                except Exception:
                    # Tag doesn't exist, get all commits
                    range_spec = to_ref
            else:
                range_spec = to_ref

            commits = []
            for commit in repo.iter_commits(range_spec):
                commits.append(CommitInfo.parse(
                    hash=commit.hexsha,
                    full_message=commit.message,
                    date=commit.committed_datetime
                ))

            return commits

        except Exception as e:
            return []

    def group_commits_by_type(self, commits: List[CommitInfo]) -> Dict[str, List[CommitInfo]]:
        """Group commits by their type."""
        grouped = {}
        for commit in commits:
            if commit.type not in grouped:
                grouped[commit.type] = []
            grouped[commit.type].append(commit)
        return grouped

    def generate_markdown(self, version: str, commits: List[CommitInfo],
                          from_version: Optional[str] = None) -> str:
        """Generate markdown changelog content."""
        grouped = self.group_commits_by_type(commits)
        date_str = datetime.now().strftime("%Y-%m-%d")

        lines = [
            f"# {version}",
            "",
            f"**Release Date:** {date_str}",
            "",
        ]

        if from_version:
            lines.append(f"**Previous Version:** {from_version}")
            lines.append("")

        lines.append(f"**Commits:** {len(commits)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Add commits by type in order
        for commit_type in self.TYPE_ORDER:
            if commit_type not in grouped:
                continue

            type_commits = grouped[commit_type]
            display_name, emoji = self.TYPE_DISPLAY.get(commit_type, (commit_type.title(), "📝"))

            lines.append(f"## {emoji} {display_name}")
            lines.append("")

            for commit in type_commits:
                scope_str = f"**{commit.scope}:** " if commit.scope else ""
                lines.append(f"- {scope_str}{commit.message} (`{commit.hash}`)")

            lines.append("")

        return "\n".join(lines)

    def save_version_changelog(self, version: str, content: str) -> Path:
        """Save changelog to version-specific file."""
        output_dir = Path(self.config.get("output_dir", "changelogs"))
        output_dir.mkdir(parents=True, exist_ok=True)

        # Ensure version has 'v' prefix for filename
        version_name = version if version.startswith("v") else f"v{version}"
        filepath = output_dir / f"{version_name}.md"
        filepath.write_text(content)

        return filepath

    def update_main_changelog(self, version: str, content: str) -> Path:
        """Prepend to main CHANGELOG.md file."""
        changelog_path = Path("CHANGELOG.md")

        # Prepare version section (without the header since main file has its own)
        # Skip first line (version header) as we'll format differently
        lines = content.split("\n")
        version_content = "\n".join(lines)

        if changelog_path.exists():
            existing = changelog_path.read_text()
            # Check if main header exists
            if existing.startswith("# Changelog"):
                # Insert after header
                parts = existing.split("\n", 2)
                if len(parts) >= 2:
                    new_content = f"{parts[0]}\n{parts[1]}\n\n{version_content}\n\n---\n\n"
                    if len(parts) > 2:
                        new_content += parts[2]
                else:
                    new_content = f"{parts[0]}\n\n{version_content}\n"
            else:
                # Prepend
                new_content = f"# Changelog\n\n{version_content}\n\n---\n\n{existing}"
        else:
            new_content = f"# Changelog\n\n{version_content}\n"

        changelog_path.write_text(new_content)
        return changelog_path

    def enable_plugin(self):
        """Enable changelog plugin in config."""
        config = self.config_manager.load()
        if "plugins" not in config:
            config["plugins"] = {}

        config["plugins"]["changelog"] = {
            "enabled": True,
            "format": "markdown",
            "output_dir": "changelogs",
            "group_by_type": True,
        }

        self.config_manager.save(config)