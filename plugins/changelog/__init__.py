"""
Changelog Plugin - Automatic changelog generation from git commits.

Commands:
    rg changelog generate   - Generate changelog for current version
    rg changelog show       - Show current changelog
    rg changelog list       - List all changelogs

Features:
    - Groups commits by type (feat, fix, chore, etc.)
    - Deduplicates similar commits (merge commits, cherry-picks)
    - LLM-powered summary generation
    - Author contribution statistics
    - Creates version-specific files (changelogs/v1.0.0.md)
    - Updates main CHANGELOG.md
"""

import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

try:
    from redgit.plugins.base import Plugin
    from redgit.core.config import ConfigManager, RETGIT_DIR
except ImportError:
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
    author: str = ""
    email: str = ""
    additions: int = 0
    deletions: int = 0
    files_changed: int = 0

    @classmethod
    def parse(cls, hash: str, full_message: str, date: datetime,
              author: str = "", email: str = "") -> "CommitInfo":
        """Parse a commit message into structured info."""
        lines = full_message.strip().split("\n")
        first_line = lines[0].strip()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else None

        # Parse conventional commit format: type(scope): message
        match = re.match(r"^(\w+)(?:\(([^)]+)\))?\s*:\s*(.+)$", first_line)
        if match:
            return cls(
                hash=hash[:7],
                type=match.group(1).lower(),
                scope=match.group(2),
                message=match.group(3).strip(),
                body=body,
                date=date,
                author=author,
                email=email
            )

        # Non-conventional commit
        return cls(
            hash=hash[:7],
            type="other",
            scope=None,
            message=first_line,
            body=body,
            date=date,
            author=author,
            email=email
        )

    def normalized_message(self) -> str:
        """Get normalized message for deduplication."""
        # Remove common variations
        msg = self.message.lower().strip()
        # Remove trailing punctuation
        msg = re.sub(r'[.!?]+$', '', msg)
        # Remove issue references like (#123), [#123], etc.
        msg = re.sub(r'\s*[\(\[](#?\d+[\)\]])', '', msg)
        return msg


@dataclass
class AuthorStats:
    name: str
    email: str
    commits: int = 0
    additions: int = 0
    deletions: int = 0
    percentage: float = 0.0


class ChangelogPlugin(Plugin):
    """Changelog generation plugin with LLM summary support."""

    name = "changelog"

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
        "other": ("Other Changes", "📝"),
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
        return Path(".git").exists()

    def get_latest_tag(self) -> Optional[str]:
        """Get the most recent version tag."""
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            # No tags exist
            return None

    def get_commits_between(self, from_ref: Optional[str], to_ref: str = "HEAD") -> List[CommitInfo]:
        """Get commits between two refs with full metadata."""
        try:
            from git import Repo
            repo = Repo(".")

            if from_ref:
                try:
                    repo.commit(from_ref)
                    range_spec = f"{from_ref}..{to_ref}"
                except Exception:
                    range_spec = to_ref
            else:
                range_spec = to_ref

            commits = []
            for commit in repo.iter_commits(range_spec):
                # Get stats
                stats = commit.stats.total

                commits.append(CommitInfo(
                    hash=commit.hexsha[:7],
                    type="other",
                    scope=None,
                    message=commit.message.split('\n')[0].strip(),
                    body='\n'.join(commit.message.split('\n')[1:]).strip() or None,
                    date=commit.committed_datetime,
                    author=commit.author.name.replace('\\n', '').strip(),
                    email=commit.author.email,
                    additions=stats.get('insertions', 0),
                    deletions=stats.get('deletions', 0),
                    files_changed=stats.get('files', 0)
                ))

                # Re-parse to extract type/scope
                parsed = CommitInfo.parse(
                    commit.hexsha,
                    commit.message,
                    commit.committed_datetime,
                    commit.author.name.replace('\\n', '').strip(),
                    commit.author.email
                )
                commits[-1].type = parsed.type
                commits[-1].scope = parsed.scope
                commits[-1].message = parsed.message

            return commits

        except Exception as e:
            return []

    def deduplicate_commits(self, commits: List[CommitInfo]) -> List[CommitInfo]:
        """Remove duplicate commits based on message similarity."""
        seen_messages = {}
        unique_commits = []

        for commit in commits:
            normalized = commit.normalized_message()

            # Skip merge commits
            if commit.message.lower().startswith('merge'):
                continue

            if normalized not in seen_messages:
                seen_messages[normalized] = commit
                unique_commits.append(commit)

        return unique_commits

    def calculate_author_stats(self, commits: List[CommitInfo]) -> List[AuthorStats]:
        """Calculate contribution statistics per author."""
        author_data = defaultdict(lambda: {
            'commits': 0,
            'additions': 0,
            'deletions': 0,
            'email': ''
        })

        total_commits = len(commits)

        for commit in commits:
            author_data[commit.author]['commits'] += 1
            author_data[commit.author]['additions'] += commit.additions
            author_data[commit.author]['deletions'] += commit.deletions
            author_data[commit.author]['email'] = commit.email

        stats = []
        for name, data in author_data.items():
            percentage = (data['commits'] / total_commits * 100) if total_commits > 0 else 0
            stats.append(AuthorStats(
                name=name,
                email=data['email'],
                commits=data['commits'],
                additions=data['additions'],
                deletions=data['deletions'],
                percentage=round(percentage, 1)
            ))

        # Sort by commits descending
        stats.sort(key=lambda x: x.commits, reverse=True)
        return stats

    def group_commits_by_type(self, commits: List[CommitInfo]) -> Dict[str, List[CommitInfo]]:
        """Group commits by their type."""
        grouped = {}
        for commit in commits:
            if commit.type not in grouped:
                grouped[commit.type] = []
            grouped[commit.type].append(commit)
        return grouped

    def group_commits_by_date(self, commits: List[CommitInfo]) -> Dict[str, List[CommitInfo]]:
        """Group commits by date (YYYY-MM-DD)."""
        grouped = defaultdict(list)
        for commit in commits:
            date_key = commit.date.strftime("%Y-%m-%d")
            grouped[date_key].append(commit)

        # Sort by date descending
        return dict(sorted(grouped.items(), reverse=True))

    def format_commits_for_llm(self, commits: List[CommitInfo]) -> str:
        """Format commits for LLM analysis."""
        lines = []
        for c in commits:
            type_str = f"[{c.type}]" if c.type != "other" else ""
            scope_str = f"({c.scope})" if c.scope else ""
            lines.append(f"- {type_str}{scope_str} {c.message} (by {c.author}, {c.date.strftime('%Y-%m-%d')})")
        return '\n'.join(lines)

    def generate_llm_summary(self, commits: List[CommitInfo],
                            from_version: Optional[str],
                            to_version: str,
                            language: str = "en") -> Optional[str]:
        """Generate an LLM-powered summary of changes."""
        try:
            from redgit.core.llm import LLMClient
            from redgit.core.config import ConfigManager

            config = ConfigManager().load()
            llm_config = config.get("llm", {})
            llm = LLMClient(llm_config)

            commits_text = self.format_commits_for_llm(commits)

            # Group by type for context
            grouped = self.group_commits_by_type(commits)
            type_summary = []
            for t in self.TYPE_ORDER:
                if t in grouped:
                    count = len(grouped[t])
                    name, _ = self.TYPE_DISPLAY.get(t, (t, ""))
                    type_summary.append(f"- {name}: {count}")

            language_name = {
                "en": "English",
                "tr": "Turkish",
                "de": "German",
                "fr": "French",
                "es": "Spanish"
            }.get(language, language)

            prompt = f"""You are a technical writer creating a changelog summary. Analyze these commits and write a professional release notes summary.

## Version: {to_version}
## Previous Version: {from_version or "Initial Release"}
## Total Commits: {len(commits)}

## Commit Statistics:
{chr(10).join(type_summary)}

## Commits:
{commits_text}

## Instructions:
Write a comprehensive changelog summary in {language_name} with these sections:

1. **Overview** (2-3 sentences): What is the main theme or focus of this release?

2. **Highlights**: The most important changes users should know about. Be specific about what changed and why it matters.

3. **Detailed Changes**: Group related changes together logically (not just by commit type). For each group:
   - Give a descriptive heading
   - Write a brief paragraph explaining what was done and why
   - Include specific details where relevant

4. **Technical Notes** (if applicable): Breaking changes, migration notes, or important technical details.

Guidelines:
- Focus on user impact, not implementation details
- Combine related commits into coherent narratives
- Skip trivial changes (typos, minor refactors) unless they're part of a larger effort
- Use professional, clear language
- Be concise but informative

Output as markdown."""

            return llm.chat(prompt)

        except Exception as e:
            return None

    def generate_markdown(self, version: str, commits: List[CommitInfo],
                          from_version: Optional[str] = None,
                          llm_summary: Optional[str] = None,
                          author_stats: Optional[List[AuthorStats]] = None) -> str:
        """Generate markdown changelog content."""
        grouped = self.group_commits_by_type(commits)
        date_str = datetime.now().strftime("%Y-%m-%d")

        lines = [
            f"# {version}",
            "",
            f"**Release Date:** {date_str}",
        ]

        if from_version:
            lines.append(f"**Previous Version:** {from_version}")

        lines.extend([
            f"**Total Commits:** {len(commits)}",
            "",
        ])

        # Add LLM summary if available
        if llm_summary:
            lines.extend([
                "---",
                "",
                llm_summary,
                "",
            ])

        # Add raw commit list
        lines.extend([
            "---",
            "",
            "## Commit Details",
            "",
        ])

        for commit_type in self.TYPE_ORDER:
            if commit_type not in grouped:
                continue

            type_commits = grouped[commit_type]
            display_name, emoji = self.TYPE_DISPLAY.get(commit_type, (commit_type.title(), "📝"))

            lines.append(f"### {emoji} {display_name} ({len(type_commits)})")
            lines.append("")

            for commit in type_commits:
                scope_str = f"**{commit.scope}:** " if commit.scope else ""
                lines.append(f"- {scope_str}{commit.message} (`{commit.hash}`)")

            lines.append("")

        # Add author statistics
        if author_stats:
            lines.extend([
                "---",
                "",
                "## Contributors",
                "",
            ])

            for stat in author_stats:
                bar_length = int(stat.percentage / 5)  # 20 chars max for 100%
                bar = "█" * bar_length + "░" * (20 - bar_length)
                lines.append(f"- **{stat.name}**: {stat.commits} commits ({stat.percentage}%) `{bar}`")
                lines.append(f"  - +{stat.additions} / -{stat.deletions} lines")

            lines.append("")

        return "\n".join(lines)

    def save_version_changelog(self, version: str, content: str) -> Path:
        """Save changelog to version-specific file."""
        output_dir = Path(self.config.get("output_dir", "changelogs"))
        output_dir.mkdir(parents=True, exist_ok=True)

        version_name = version if version.startswith("v") else f"v{version}"
        filepath = output_dir / f"{version_name}.md"
        filepath.write_text(content)

        return filepath

    def update_main_changelog(self, version: str, content: str) -> Path:
        """Prepend to main CHANGELOG.md file."""
        changelog_path = Path("CHANGELOG.md")

        lines = content.split("\n")
        version_content = "\n".join(lines)

        if changelog_path.exists():
            existing = changelog_path.read_text()
            if existing.startswith("# Changelog"):
                parts = existing.split("\n", 2)
                if len(parts) >= 2:
                    new_content = f"{parts[0]}\n{parts[1]}\n\n{version_content}\n\n---\n\n"
                    if len(parts) > 2:
                        new_content += parts[2]
                else:
                    new_content = f"{parts[0]}\n\n{version_content}\n"
            else:
                new_content = f"# Changelog\n\n{version_content}\n\n---\n\n{existing}"
        else:
            new_content = f"# Changelog\n\n{version_content}\n"

        changelog_path.write_text(new_content)
        return changelog_path