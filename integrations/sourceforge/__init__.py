"""
SourceForge integration for RedGit.

Code hosting with repository management on SourceForge.
"""

import os
import subprocess
from typing import Optional, Dict, List

try:
    from redgit.integrations.base import CodeHostingBase, IntegrationType
except ImportError:
    from enum import Enum
    class IntegrationType(Enum):
        CODE_HOSTING = "code_hosting"
    class CodeHostingBase:
        integration_type = IntegrationType.CODE_HOSTING
        def __init__(self):
            self.enabled = False
        def setup(self, config): pass
        def create_pull_request(self, title, body, head_branch, base_branch): pass
        def push_branch(self, branch_name): pass
        def get_default_branch(self): return "master"


class SourceForgeIntegration(CodeHostingBase):
    """SourceForge code hosting integration

    Note: SourceForge has limited API support. This integration primarily
    supports Git operations and basic repository info. Full API requires
    Allura API which is more complex.
    """

    name = "sourceforge"
    integration_type = IntegrationType.CODE_HOSTING

    # Custom notification events
    notification_events = {
        "mr_created": {
            "description": "SourceForge merge request created",
            "default": True
        },
        "branch_pushed": {
            "description": "Branch pushed to SourceForge",
            "default": False
        },
    }

    def __init__(self):
        super().__init__()
        self.username = ""
        self.project = ""
        self.repo_path = ""
        self.default_branch = "master"

    def setup(self, config: dict):
        """Setup SourceForge integration."""
        self.username = config.get("username") or os.getenv("SOURCEFORGE_USERNAME", "")
        self.project = config.get("project") or os.getenv("SOURCEFORGE_PROJECT", "")
        self.repo_path = config.get("repo_path", "code")
        self.default_branch = config.get("default_branch", "master")

        # Auto-detect from git remote if not set
        if not self.project:
            self._detect_from_remote()

        if not self.username or not self.project:
            self.enabled = False
            return

        self.enabled = True

    def _detect_from_remote(self):
        """Detect project from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Parse SourceForge URL formats:
                # ssh://username@git.code.sf.net/p/project/code
                # https://git.code.sf.net/p/project/code
                # git://git.code.sf.net/p/project/code
                if "sf.net" in url or "sourceforge" in url.lower():
                    if "/p/" in url:
                        parts = url.split("/p/")[-1].split("/")
                        if len(parts) >= 1:
                            self.project = self.project or parts[0]
                        if len(parts) >= 2:
                            self.repo_path = parts[1].replace(".git", "")
        except Exception:
            pass

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = None
    ) -> Optional[str]:
        """SourceForge doesn't have traditional PR API.

        Users should use the web interface for merge requests.
        """
        if not self.enabled:
            return None

        # Return URL to create merge request manually
        return f"https://sourceforge.net/p/{self.project}/{self.repo_path}/merge-requests/new"

    def push_branch(self, branch_name: str) -> bool:
        """Push branch to SourceForge."""
        try:
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_default_branch(self) -> str:
        """Get default branch (typically master for SourceForge)."""
        return self.default_branch

    def get_project_url(self) -> str:
        """Get project URL."""
        return f"https://sourceforge.net/projects/{self.project}/"

    def get_repo_url(self) -> str:
        """Get repository URL."""
        return f"https://sourceforge.net/p/{self.project}/{self.repo_path}/"

    def get_clone_url_ssh(self) -> str:
        """Get SSH clone URL."""
        return f"ssh://{self.username}@git.code.sf.net/p/{self.project}/{self.repo_path}"

    def get_clone_url_https(self) -> str:
        """Get HTTPS clone URL (read-only)."""
        return f"https://git.code.sf.net/p/{self.project}/{self.repo_path}"

    def list_branches(self) -> List[str]:
        """List branches using git."""
        try:
            result = subprocess.run(
                ["git", "branch", "-r"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                branches = []
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("origin/") and "HEAD" not in line:
                        branches.append(line.replace("origin/", ""))
                return branches
        except Exception:
            pass
        return []

    def fetch_remote(self) -> bool:
        """Fetch from remote."""
        try:
            result = subprocess.run(
                ["git", "fetch", "origin"],
                capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_remote_info(self) -> Dict[str, str]:
        """Get remote repository info."""
        return {
            "project": self.project,
            "repo_path": self.repo_path,
            "project_url": self.get_project_url(),
            "repo_url": self.get_repo_url(),
            "clone_ssh": self.get_clone_url_ssh(),
            "clone_https": self.get_clone_url_https()
        }

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        project = config_values.get("project", "")
        username = config_values.get("username", "")

        if project and username:
            typer.echo(f"\n   SourceForge project: {project}")
            typer.echo(f"   Username: {username}")
            typer.secho("   Configuration saved!", fg=typer.colors.GREEN)
            typer.echo("\n   Note: SourceForge uses SSH keys for authentication.")
            typer.echo("   Make sure your SSH key is added to your SourceForge account.")

        return config_values