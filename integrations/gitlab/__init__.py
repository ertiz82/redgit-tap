"""
GitLab integration for RedGit.

Code hosting with MRs, branches, and repository management.
"""

import os
import json
import subprocess
from typing import Optional, Dict, List
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import quote

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


class GitLabIntegration(CodeHostingBase):
    """GitLab code hosting integration"""

    name = "gitlab"
    integration_type = IntegrationType.CODE_HOSTING

    # Custom notification events
    notification_events = {
        "mr_created": {
            "description": "GitLab MR created",
            "default": True
        },
        "mr_merged": {
            "description": "GitLab MR merged",
            "default": True
        },
        "mr_approved": {
            "description": "GitLab MR approved",
            "default": False
        },
        "branch_pushed": {
            "description": "Branch pushed to GitLab",
            "default": False
        },
    }

    def __init__(self):
        super().__init__()
        self.token = ""
        self.host = "https://gitlab.com"
        self.project_id = ""
        self.default_branch = "main"

    def setup(self, config: dict):
        """Setup GitLab integration."""
        self.token = config.get("token") or os.getenv("GITLAB_TOKEN", "")
        self.host = config.get("host") or os.getenv("GITLAB_HOST", "https://gitlab.com")
        self.project_id = config.get("project_id") or os.getenv("GITLAB_PROJECT_ID", "")
        self.default_branch = config.get("default_branch", "main")

        # Remove trailing slash
        self.host = self.host.rstrip("/")

        # Auto-detect from git remote if not set
        if not self.project_id:
            self._detect_from_remote()

        if not self.token:
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
                # Parse gitlab.com/namespace/project from various formats
                if "gitlab" in url.lower():
                    if url.startswith("git@"):
                        # git@gitlab.com:namespace/project.git
                        path = url.split(":")[-1].replace(".git", "")
                    else:
                        # https://gitlab.com/namespace/project.git
                        parts = url.replace(".git", "").split("/")
                        # Get everything after the host
                        try:
                            idx = next(i for i, p in enumerate(parts) if "gitlab" in p.lower())
                            path = "/".join(parts[idx+1:])
                        except StopIteration:
                            path = ""
                    if path:
                        self.project_id = self.project_id or path
        except Exception:
            pass

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make GitLab API request."""
        try:
            url = f"{self.host}/api/v4{endpoint}"
            headers = {
                "PRIVATE-TOKEN": self.token,
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

    def _encode_project_id(self) -> str:
        """URL encode project ID for API calls."""
        return quote(self.project_id, safe="")

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = None
    ) -> Optional[str]:
        """Create a merge request."""
        if not self.enabled:
            return None

        base = base_branch or self.default_branch
        project = self._encode_project_id()

        data = {
            "title": title,
            "description": body,
            "source_branch": head_branch,
            "target_branch": base
        }

        result = self._api_request(
            f"/projects/{project}/merge_requests",
            method="POST",
            data=data
        )

        if result:
            return result.get("web_url")
        return None

    def push_branch(self, branch_name: str) -> bool:
        """Push branch to GitLab."""
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

        project = self._encode_project_id()
        result = self._api_request(f"/projects/{project}")
        if result:
            return result.get("default_branch", self.default_branch)
        return self.default_branch

    def get_project_info(self) -> Optional[dict]:
        """Get project information."""
        if not self.enabled:
            return None
        project = self._encode_project_id()
        return self._api_request(f"/projects/{project}")

    def list_branches(self) -> List[dict]:
        """List repository branches."""
        if not self.enabled:
            return []

        project = self._encode_project_id()
        result = self._api_request(f"/projects/{project}/repository/branches")
        return result or []

    def list_merge_requests(self, state: str = "opened") -> List[dict]:
        """List merge requests."""
        if not self.enabled:
            return []

        project = self._encode_project_id()
        result = self._api_request(
            f"/projects/{project}/merge_requests?state={state}"
        )
        return result or []

    def get_merge_request(self, mr_iid: int) -> Optional[dict]:
        """Get a specific merge request."""
        if not self.enabled:
            return None

        project = self._encode_project_id()
        return self._api_request(
            f"/projects/{project}/merge_requests/{mr_iid}"
        )

    def merge_merge_request(self, mr_iid: int, squash: bool = False) -> bool:
        """Merge a merge request."""
        if not self.enabled:
            return False

        project = self._encode_project_id()
        data = {"squash": squash}

        result = self._api_request(
            f"/projects/{project}/merge_requests/{mr_iid}/merge",
            method="PUT",
            data=data
        )
        return result is not None

    def create_branch(self, branch_name: str, from_ref: str = None) -> bool:
        """Create a new branch."""
        if not self.enabled:
            return False

        project = self._encode_project_id()
        base_ref = from_ref or self.default_branch

        result = self._api_request(
            f"/projects/{project}/repository/branches",
            method="POST",
            data={
                "branch": branch_name,
                "ref": base_ref
            }
        )
        return result is not None

    def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch."""
        if not self.enabled:
            return False

        project = self._encode_project_id()
        branch = quote(branch_name, safe="")

        try:
            self._api_request(
                f"/projects/{project}/repository/branches/{branch}",
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

    def list_projects(self) -> List[dict]:
        """List user's projects."""
        if not self.enabled:
            return []

        result = self._api_request("/projects?membership=true&order_by=updated_at&per_page=30")
        return result or []

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        host = config_values.get("host", "https://gitlab.com")
        if token:
            typer.echo("\n   Verifying GitLab token...")
            temp = GitLabIntegration()
            temp.token = token
            temp.host = host.rstrip("/")
            temp.enabled = True
            user = temp.get_user()
            if user:
                typer.secho(f"   Authenticated as: {user.get('username')}", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to authenticate", fg=typer.colors.RED)
        return config_values