"""
Azure Repos integration for RedGit.

Code hosting with PRs, branches, and repository management on Azure DevOps.
"""

import os
import json
import subprocess
import base64
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


class AzureReposIntegration(CodeHostingBase):
    """Azure Repos code hosting integration"""

    name = "azure-repos"
    integration_type = IntegrationType.CODE_HOSTING

    def __init__(self):
        super().__init__()
        self.pat = ""
        self.organization = ""
        self.project = ""
        self.repository = ""
        self.default_branch = "main"
        self._api_version = "7.0"

    def setup(self, config: dict):
        """Setup Azure Repos integration."""
        self.pat = config.get("pat") or os.getenv("AZURE_DEVOPS_PAT", "")
        self.organization = config.get("organization") or os.getenv("AZURE_DEVOPS_ORG", "")
        self.project = config.get("project") or os.getenv("AZURE_DEVOPS_PROJECT", "")
        self.repository = config.get("repository") or os.getenv("AZURE_DEVOPS_REPO", "")
        self.default_branch = config.get("default_branch", "main")

        # Auto-detect from git remote if not set
        if not self.organization or not self.project or not self.repository:
            self._detect_from_remote()

        if not self.pat or not self.organization:
            self.enabled = False
            return

        self.enabled = True

    def _detect_from_remote(self):
        """Detect org/project/repo from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Parse Azure DevOps URL formats:
                # https://dev.azure.com/org/project/_git/repo
                # https://org@dev.azure.com/org/project/_git/repo
                # https://org.visualstudio.com/project/_git/repo
                if "dev.azure.com" in url or "visualstudio.com" in url:
                    if "_git/" in url:
                        parts = url.split("_git/")
                        self.repository = self.repository or parts[-1].replace(".git", "")

                        path_part = parts[0]
                        if "dev.azure.com" in path_part:
                            # https://dev.azure.com/org/project/
                            segments = path_part.split("dev.azure.com/")[-1].strip("/").split("/")
                            if len(segments) >= 2:
                                self.organization = self.organization or segments[0]
                                self.project = self.project or segments[1]
                        elif "visualstudio.com" in path_part:
                            # https://org.visualstudio.com/project/
                            org_part = path_part.split(".visualstudio.com")[0].split("/")[-1]
                            self.organization = self.organization or org_part
                            project_part = path_part.split(".visualstudio.com/")[-1].strip("/")
                            self.project = self.project or project_part
        except Exception:
            pass

    def _get_auth_header(self) -> str:
        """Get Basic auth header value."""
        credentials = f":{self.pat}"
        return base64.b64encode(credentials.encode()).decode()

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Azure DevOps API request."""
        try:
            url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis{endpoint}"
            if "?" in url:
                url += f"&api-version={self._api_version}"
            else:
                url += f"?api-version={self._api_version}"

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

        # Azure DevOps requires refs/heads/ prefix
        source_ref = f"refs/heads/{head_branch}" if not head_branch.startswith("refs/") else head_branch
        target_ref = f"refs/heads/{base}" if not base.startswith("refs/") else base

        data = {
            "sourceRefName": source_ref,
            "targetRefName": target_ref,
            "title": title,
            "description": body
        }

        result = self._api_request(
            f"/git/repositories/{self.repository}/pullrequests",
            method="POST",
            data=data
        )

        if result:
            pr_id = result.get("pullRequestId")
            return f"https://dev.azure.com/{self.organization}/{self.project}/_git/{self.repository}/pullrequest/{pr_id}"
        return None

    def push_branch(self, branch_name: str) -> bool:
        """Push branch to Azure Repos."""
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

        result = self._api_request(f"/git/repositories/{self.repository}")
        if result:
            default_ref = result.get("defaultBranch", "")
            return default_ref.replace("refs/heads/", "") if default_ref else self.default_branch
        return self.default_branch

    def get_repo_info(self) -> Optional[dict]:
        """Get repository information."""
        if not self.enabled:
            return None
        return self._api_request(f"/git/repositories/{self.repository}")

    def list_branches(self) -> List[dict]:
        """List repository branches."""
        if not self.enabled:
            return []

        result = self._api_request(f"/git/repositories/{self.repository}/refs?filter=heads/")
        if result:
            return result.get("value", [])
        return []

    def list_pull_requests(self, status: str = "active") -> List[dict]:
        """List pull requests."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/git/repositories/{self.repository}/pullrequests?searchCriteria.status={status}"
        )
        if result:
            return result.get("value", [])
        return []

    def get_pull_request(self, pr_id: int) -> Optional[dict]:
        """Get a specific pull request."""
        if not self.enabled:
            return None

        return self._api_request(
            f"/git/repositories/{self.repository}/pullrequests/{pr_id}"
        )

    def complete_pull_request(
        self,
        pr_id: int,
        delete_source: bool = False,
        squash: bool = False
    ) -> bool:
        """Complete (merge) a pull request."""
        if not self.enabled:
            return False

        # Get PR to get the last merge source commit
        pr = self.get_pull_request(pr_id)
        if not pr:
            return False

        data = {
            "status": "completed",
            "lastMergeSourceCommit": pr.get("lastMergeSourceCommit"),
            "completionOptions": {
                "deleteSourceBranch": delete_source,
                "squashMerge": squash
            }
        }

        result = self._api_request(
            f"/git/repositories/{self.repository}/pullrequests/{pr_id}",
            method="PATCH",
            data=data
        )
        return result is not None and result.get("status") == "completed"

    def abandon_pull_request(self, pr_id: int) -> bool:
        """Abandon a pull request."""
        if not self.enabled:
            return False

        result = self._api_request(
            f"/git/repositories/{self.repository}/pullrequests/{pr_id}",
            method="PATCH",
            data={"status": "abandoned"}
        )
        return result is not None

    def get_user(self) -> Optional[dict]:
        """Get authenticated user info."""
        if not self.enabled:
            return None

        try:
            url = f"https://dev.azure.com/{self.organization}/_apis/connectionData?api-version={self._api_version}"
            headers = {
                "Authorization": f"Basic {self._get_auth_header()}",
                "Accept": "application/json"
            }
            req = Request(url, headers=headers)
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("authenticatedUser")
        except Exception:
            return None

    def list_repositories(self) -> List[dict]:
        """List project repositories."""
        if not self.enabled:
            return []

        result = self._api_request("/git/repositories")
        if result:
            return result.get("value", [])
        return []

    def list_projects(self) -> List[dict]:
        """List organization projects."""
        if not self.enabled:
            return []

        try:
            url = f"https://dev.azure.com/{self.organization}/_apis/projects?api-version={self._api_version}"
            headers = {
                "Authorization": f"Basic {self._get_auth_header()}",
                "Accept": "application/json"
            }
            req = Request(url, headers=headers)
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("value", [])
        except Exception:
            return []

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        pat = config_values.get("pat", "")
        organization = config_values.get("organization", "")

        if pat and organization:
            typer.echo("\n   Verifying Azure DevOps access...")
            temp = AzureReposIntegration()
            temp.pat = pat
            temp.organization = organization
            temp.project = config_values.get("project", "")
            temp.repository = config_values.get("repository", "")
            temp.enabled = True
            user = temp.get_user()
            if user:
                typer.secho(f"   Authenticated as: {user.get('providerDisplayName', user.get('id'))}", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to authenticate", fg=typer.colors.RED)

        return config_values