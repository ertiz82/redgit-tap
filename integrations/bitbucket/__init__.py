"""
Bitbucket integration for RedGit.

Code hosting with PRs, branches, and repository management.
"""

import os
import json
import subprocess
import base64
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


class BitbucketIntegration(CodeHostingBase):
    """Bitbucket code hosting integration"""

    name = "bitbucket"
    integration_type = IntegrationType.CODE_HOSTING

    def __init__(self):
        super().__init__()
        self.username = ""
        self.app_password = ""
        self.workspace = ""
        self.repo_slug = ""
        self.default_branch = "main"
        self._api_base = "https://api.bitbucket.org/2.0"

    def setup(self, config: dict):
        """Setup Bitbucket integration."""
        self.username = config.get("username") or os.getenv("BITBUCKET_USERNAME", "")
        self.app_password = config.get("app_password") or os.getenv("BITBUCKET_APP_PASSWORD", "")
        self.workspace = config.get("workspace") or os.getenv("BITBUCKET_WORKSPACE", "")
        self.repo_slug = config.get("repo_slug") or os.getenv("BITBUCKET_REPO_SLUG", "")
        self.default_branch = config.get("default_branch", "main")

        # Auto-detect from git remote if not set
        if not self.workspace or not self.repo_slug:
            self._detect_from_remote()

        if not self.username or not self.app_password:
            self.enabled = False
            return

        self.enabled = True

    def _detect_from_remote(self):
        """Detect workspace/repo from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Parse bitbucket.org/workspace/repo from various formats
                if "bitbucket" in url.lower():
                    if url.startswith("git@"):
                        # git@bitbucket.org:workspace/repo.git
                        parts = url.split(":")[-1].replace(".git", "").split("/")
                    else:
                        # https://bitbucket.org/workspace/repo.git
                        parts = url.replace(".git", "").split("/")[-2:]
                    if len(parts) >= 2:
                        self.workspace = self.workspace or parts[-2]
                        self.repo_slug = self.repo_slug or parts[-1]
        except Exception:
            pass

    def _get_auth_header(self) -> str:
        """Get Basic auth header value."""
        credentials = f"{self.username}:{self.app_password}"
        return base64.b64encode(credentials.encode()).decode()

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Bitbucket API request."""
        try:
            url = f"{self._api_base}{endpoint}"
            headers = {
                "Authorization": f"Basic {self._get_auth_header()}",
                "Accept": "application/json"
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
            "description": body,
            "source": {
                "branch": {"name": head_branch}
            },
            "destination": {
                "branch": {"name": base}
            }
        }

        result = self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}/pullrequests",
            method="POST",
            data=data
        )

        if result:
            return result.get("links", {}).get("html", {}).get("href")
        return None

    def push_branch(self, branch_name: str) -> bool:
        """Push branch to Bitbucket."""
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

        result = self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}"
        )
        if result:
            return result.get("mainbranch", {}).get("name", self.default_branch)
        return self.default_branch

    def get_repo_info(self) -> Optional[dict]:
        """Get repository information."""
        if not self.enabled:
            return None
        return self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}"
        )

    def list_branches(self) -> List[dict]:
        """List repository branches."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}/refs/branches"
        )
        if result:
            return result.get("values", [])
        return []

    def list_pull_requests(self, state: str = "OPEN") -> List[dict]:
        """List pull requests."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}/pullrequests?state={state}"
        )
        if result:
            return result.get("values", [])
        return []

    def get_pull_request(self, pr_id: int) -> Optional[dict]:
        """Get a specific pull request."""
        if not self.enabled:
            return None

        return self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}/pullrequests/{pr_id}"
        )

    def merge_pull_request(self, pr_id: int) -> bool:
        """Merge a pull request."""
        if not self.enabled:
            return False

        result = self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}/pullrequests/{pr_id}/merge",
            method="POST"
        )
        return result is not None

    def decline_pull_request(self, pr_id: int) -> bool:
        """Decline a pull request."""
        if not self.enabled:
            return False

        result = self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}/pullrequests/{pr_id}/decline",
            method="POST"
        )
        return result is not None

    def get_user(self) -> Optional[dict]:
        """Get authenticated user info."""
        if not self.enabled:
            return None
        return self._api_request("/user")

    def list_workspaces(self) -> List[dict]:
        """List user's workspaces."""
        if not self.enabled:
            return []

        result = self._api_request("/workspaces")
        if result:
            return result.get("values", [])
        return []

    def list_repos(self) -> List[dict]:
        """List workspace repositories."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repositories/{self.workspace}?sort=-updated_on"
        )
        if result:
            return result.get("values", [])
        return []

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        username = config_values.get("username", "")
        app_password = config_values.get("app_password", "")
        if username and app_password:
            typer.echo("\n   Verifying Bitbucket credentials...")
            temp = BitbucketIntegration()
            temp.username = username
            temp.app_password = app_password
            temp.enabled = True
            user = temp.get_user()
            if user:
                typer.secho(f"   Authenticated as: {user.get('username')}", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to authenticate", fg=typer.colors.RED)
        return config_values