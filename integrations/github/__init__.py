"""
GitHub integration for RedGit.

Code hosting with PRs, branches, and repository management.
"""

import os
import json
import subprocess
from typing import Optional, Dict, List
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

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
        def get_default_branch(self): return "main"


class GitHubIntegration(CodeHostingBase):
    """GitHub code hosting integration"""

    name = "github"
    integration_type = IntegrationType.CODE_HOSTING

    # Custom notification events
    notification_events = {
        "pr_created": {
            "description": "GitHub PR created",
            "default": True
        },
        "pr_merged": {
            "description": "GitHub PR merged",
            "default": True
        },
        "pr_review_requested": {
            "description": "GitHub PR review requested",
            "default": False
        },
        "branch_pushed": {
            "description": "Branch pushed to GitHub",
            "default": False
        },
    }

    def __init__(self):
        super().__init__()
        self.token = ""
        self.owner = ""
        self.repo = ""
        self.default_branch = "main"
        self._api_base = "https://api.github.com"

    def setup(self, config: dict):
        """Setup GitHub integration."""
        self.token = config.get("token") or os.getenv("GITHUB_TOKEN", "")
        self.owner = config.get("owner") or os.getenv("GITHUB_OWNER", "")
        self.repo = config.get("repo") or os.getenv("GITHUB_REPO", "")
        self.default_branch = config.get("default_branch", "main")

        # Auto-detect from git remote if not set
        if not self.owner or not self.repo:
            self._detect_from_remote()

        if not self.token:
            self.enabled = False
            return

        self.enabled = True

    def _detect_from_remote(self):
        """Detect owner/repo from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Parse github.com/owner/repo from various formats
                if "github.com" in url:
                    if url.startswith("git@"):
                        # git@github.com:owner/repo.git
                        parts = url.split(":")[-1].replace(".git", "").split("/")
                    else:
                        # https://github.com/owner/repo.git
                        parts = url.replace(".git", "").split("/")[-2:]
                    if len(parts) >= 2:
                        self.owner = self.owner or parts[-2]
                        self.repo = self.repo or parts[-1]
        except Exception:
            pass

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make GitHub API request."""
        try:
            url = f"{self._api_base}{endpoint}"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            req_data = None
            if data:
                req_data = json.dumps(data).encode("utf-8")
                headers["Content-Type"] = "application/json"

            req = Request(url, data=req_data, headers=headers, method=method)

            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 404:
                return None
            raise
        except URLError:
            return None

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = None
    ) -> Optional[str]:
        """Create a pull request."""
        if not self.enabled:
            return None

        base = base_branch or self.default_branch

        data = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base
        }

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/pulls",
            method="POST",
            data=data
        )

        if result:
            return result.get("html_url")
        return None

    def push_branch(self, branch_name: str) -> bool:
        """Push branch to GitHub."""
        try:
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_default_branch(self) -> str:
        """Get repository's default branch."""
        if not self.enabled:
            return self.default_branch

        result = self._api_request(f"/repos/{self.owner}/{self.repo}")
        if result:
            return result.get("default_branch", self.default_branch)
        return self.default_branch

    def get_repo_info(self) -> Optional[dict]:
        """Get repository information."""
        if not self.enabled:
            return None
        return self._api_request(f"/repos/{self.owner}/{self.repo}")

    def list_branches(self) -> List[dict]:
        """List repository branches."""
        if not self.enabled:
            return []

        result = self._api_request(f"/repos/{self.owner}/{self.repo}/branches")
        return result or []

    def list_pull_requests(self, state: str = "open") -> List[dict]:
        """List pull requests."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/pulls?state={state}"
        )
        return result or []

    def get_pull_request(self, pr_number: int) -> Optional[dict]:
        """Get a specific pull request."""
        if not self.enabled:
            return None

        return self._api_request(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}"
        )

    def merge_pull_request(
        self,
        pr_number: int,
        merge_method: str = "merge"
    ) -> bool:
        """Merge a pull request."""
        if not self.enabled:
            return False

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/merge",
            method="PUT",
            data={"merge_method": merge_method}
        )
        return result is not None

    def create_branch(self, branch_name: str, from_ref: str = None) -> bool:
        """Create a new branch."""
        if not self.enabled:
            return False

        # Get SHA of base ref
        base_ref = from_ref or self.default_branch
        ref_result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/git/ref/heads/{base_ref}"
        )
        if not ref_result:
            return False

        sha = ref_result["object"]["sha"]

        # Create new ref
        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/git/refs",
            method="POST",
            data={
                "ref": f"refs/heads/{branch_name}",
                "sha": sha
            }
        )
        return result is not None

    def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/repos/{self.owner}/{self.repo}/git/refs/heads/{branch_name}",
                method="DELETE"
            )
            return True
        except Exception:
            return False

    def get_user(self) -> Optional[dict]:
        """Get authenticated user info."""
        if not self.enabled:
            return None
        return self._api_request("/user")

    def list_user_repos(self) -> List[dict]:
        """List user's repositories."""
        if not self.enabled:
            return []

        result = self._api_request("/user/repos?sort=updated&per_page=30")
        return result or []

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        if token:
            typer.echo("\n   Verifying GitHub token...")
            temp = GitHubIntegration()
            temp.token = token
            temp.enabled = True
            user = temp.get_user()
            if user:
                typer.secho(f"   Authenticated as: {user.get('login')}", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to authenticate", fg=typer.colors.RED)
        return config_values