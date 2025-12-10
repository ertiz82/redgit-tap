"""
Apache Allura integration for RedGit.

Code hosting with tickets, wiki, and repository management.
Apache Allura powers SourceForge and other forge platforms.
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
        def get_default_branch(self): return "master"


class AlluraIntegration(CodeHostingBase):
    """Apache Allura code hosting integration

    Apache Allura is the open source forge software that powers SourceForge,
    DARPA's VehicleForge, and many other project hosting platforms.
    """

    name = "allura"
    integration_type = IntegrationType.CODE_HOSTING

    # Custom notification events
    notification_events = {
        "mr_created": {
            "description": "Allura merge request created",
            "default": True
        },
        "mr_merged": {
            "description": "Allura merge request merged",
            "default": True
        },
        "branch_pushed": {
            "description": "Branch pushed to Allura",
            "default": False
        },
        "ticket_created": {
            "description": "Allura ticket created",
            "default": False
        },
    }

    def __init__(self):
        super().__init__()
        self.base_url = ""
        self.bearer_token = ""
        self.project = ""
        self.mount_point = ""
        self.default_branch = "master"

    def setup(self, config: dict):
        """Setup Allura integration."""
        self.base_url = config.get("base_url") or os.getenv("ALLURA_BASE_URL", "")
        self.bearer_token = config.get("bearer_token") or os.getenv("ALLURA_BEARER_TOKEN", "")
        self.project = config.get("project") or os.getenv("ALLURA_PROJECT", "")
        self.mount_point = config.get("mount_point", "git")
        self.default_branch = config.get("default_branch", "master")

        # Remove trailing slash
        self.base_url = self.base_url.rstrip("/")

        # Auto-detect from git remote if not set
        if not self.project:
            self._detect_from_remote()

        if not self.base_url or not self.project:
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
                # Parse Allura-style URLs
                # https://forge.example.com/git/p/project/repo
                if "/p/" in url:
                    parts = url.split("/p/")[-1].split("/")
                    if len(parts) >= 1:
                        self.project = self.project or parts[0]
                    if len(parts) >= 2:
                        self.mount_point = parts[1].replace(".git", "")
        except Exception:
            pass

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Allura API request."""
        try:
            url = f"{self.base_url}/rest{endpoint}"
            headers = {
                "Accept": "application/json"
            }

            if self.bearer_token:
                headers["Authorization"] = f"Bearer {self.bearer_token}"

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
        """Create a merge request.

        Note: Allura merge request API varies by installation.
        """
        if not self.enabled:
            return None

        base = base_branch or self.default_branch

        # Try to create via API
        data = {
            "source_branch": head_branch,
            "target_branch": base,
            "summary": title,
            "description": body
        }

        result = self._api_request(
            f"/p/{self.project}/{self.mount_point}/merge-requests/",
            method="POST",
            data=data
        )

        if result:
            mr_id = result.get("_id") or result.get("request_number")
            if mr_id:
                return f"{self.base_url}/p/{self.project}/{self.mount_point}/merge-requests/{mr_id}/"

        # Return URL for manual creation
        return f"{self.base_url}/p/{self.project}/{self.mount_point}/merge-requests/new"

    def push_branch(self, branch_name: str) -> bool:
        """Push branch to Allura."""
        try:
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_default_branch(self) -> str:
        """Get default branch."""
        return self.default_branch

    def get_project_info(self) -> Optional[dict]:
        """Get project information."""
        if not self.enabled:
            return None
        return self._api_request(f"/p/{self.project}/")

    def get_repo_info(self) -> Optional[dict]:
        """Get repository information."""
        if not self.enabled:
            return None
        return self._api_request(f"/p/{self.project}/{self.mount_point}/")

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

    def list_merge_requests(self, status: str = "open") -> List[dict]:
        """List merge requests."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/p/{self.project}/{self.mount_point}/merge-requests/?status={status}"
        )
        if result:
            return result.get("merge_requests", [])
        return []

    def get_merge_request(self, mr_id: str) -> Optional[dict]:
        """Get a specific merge request."""
        if not self.enabled:
            return None

        return self._api_request(
            f"/p/{self.project}/{self.mount_point}/merge-requests/{mr_id}/"
        )

    def list_tickets(self, status: str = "open") -> List[dict]:
        """List project tickets."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/p/{self.project}/tickets/search/?q=status:{status}"
        )
        if result:
            return result.get("tickets", [])
        return []

    def create_ticket(
        self,
        summary: str,
        description: str = "",
        labels: List[str] = None
    ) -> Optional[dict]:
        """Create a ticket."""
        if not self.enabled:
            return None

        data = {
            "ticket_form.summary": summary,
            "ticket_form.description": description
        }
        if labels:
            data["ticket_form.labels"] = ",".join(labels)

        return self._api_request(
            f"/p/{self.project}/tickets/new",
            method="POST",
            data=data
        )

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

    def get_project_url(self) -> str:
        """Get project URL."""
        return f"{self.base_url}/p/{self.project}/"

    def get_repo_url(self) -> str:
        """Get repository URL."""
        return f"{self.base_url}/p/{self.project}/{self.mount_point}/"

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        base_url = config_values.get("base_url", "")
        project = config_values.get("project", "")

        if base_url and project:
            typer.echo(f"\n   Allura instance: {base_url}")
            typer.echo(f"   Project: {project}")

            temp = AlluraIntegration()
            temp.base_url = base_url.rstrip("/")
            temp.project = project
            temp.mount_point = config_values.get("mount_point", "git")
            temp.bearer_token = config_values.get("bearer_token", "")
            temp.enabled = True

            project_info = temp.get_project_info()
            if project_info:
                typer.secho(f"   Connected to: {project_info.get('name', project)}", fg=typer.colors.GREEN)
            else:
                typer.secho("   Could not verify project (may still work)", fg=typer.colors.YELLOW)

        return config_values