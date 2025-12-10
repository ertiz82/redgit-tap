"""
AWS CodeCommit integration for RedGit.

Code hosting with PRs, branches, and repository management.
"""

import os
import json
import subprocess
from typing import Optional, Dict, List
from datetime import datetime

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


class CodeCommitIntegration(CodeHostingBase):
    """AWS CodeCommit code hosting integration"""

    name = "codecommit"
    integration_type = IntegrationType.CODE_HOSTING

    # Custom notification events
    notification_events = {
        "pr_created": {
            "description": "CodeCommit PR created",
            "default": True
        },
        "pr_merged": {
            "description": "CodeCommit PR merged",
            "default": True
        },
        "branch_pushed": {
            "description": "Branch pushed to CodeCommit",
            "default": False
        },
        "branch_created": {
            "description": "Branch created on CodeCommit",
            "default": False
        },
    }

    def __init__(self):
        super().__init__()
        self.region = ""
        self.repository_name = ""
        self.default_branch = "main"
        self._client = None

    def setup(self, config: dict):
        """Setup CodeCommit integration."""
        self.region = config.get("region") or os.getenv("AWS_REGION", "us-east-1")
        self.repository_name = config.get("repository_name") or os.getenv("CODECOMMIT_REPO", "")
        self.default_branch = config.get("default_branch", "main")

        # Auto-detect from git remote if not set
        if not self.repository_name:
            self._detect_from_remote()

        # Check if boto3 is available and AWS credentials are configured
        try:
            import boto3
            self._client = boto3.client("codecommit", region_name=self.region)
            # Test connection
            self._client.get_repository(repositoryName=self.repository_name)
            self.enabled = True
        except ImportError:
            self.enabled = False
        except Exception:
            self.enabled = False

    def _detect_from_remote(self):
        """Detect repository from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Parse codecommit URL
                # https://git-codecommit.us-east-1.amazonaws.com/v1/repos/MyRepo
                # codecommit::us-east-1://MyRepo
                if "codecommit" in url.lower():
                    if "/v1/repos/" in url:
                        self.repository_name = url.split("/v1/repos/")[-1]
                    elif "://" in url and url.startswith("codecommit"):
                        self.repository_name = url.split("://")[-1]
        except Exception:
            pass

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = None
    ) -> Optional[str]:
        """Create a pull request."""
        if not self.enabled or not self._client:
            return None

        base = base_branch or self.default_branch

        try:
            response = self._client.create_pull_request(
                title=title,
                description=body,
                targets=[{
                    "repositoryName": self.repository_name,
                    "sourceReference": head_branch,
                    "destinationReference": base
                }]
            )
            pr = response.get("pullRequest", {})
            pr_id = pr.get("pullRequestId")
            if pr_id:
                return f"https://{self.region}.console.aws.amazon.com/codesuite/codecommit/repositories/{self.repository_name}/pull-requests/{pr_id}"
            return None
        except Exception:
            return None

    def push_branch(self, branch_name: str) -> bool:
        """Push branch to CodeCommit."""
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
        if not self.enabled or not self._client:
            return self.default_branch

        try:
            response = self._client.get_repository(
                repositoryName=self.repository_name
            )
            return response.get("repositoryMetadata", {}).get(
                "defaultBranch", self.default_branch
            )
        except Exception:
            return self.default_branch

    def get_repo_info(self) -> Optional[dict]:
        """Get repository information."""
        if not self.enabled or not self._client:
            return None

        try:
            response = self._client.get_repository(
                repositoryName=self.repository_name
            )
            return response.get("repositoryMetadata")
        except Exception:
            return None

    def list_branches(self) -> List[str]:
        """List repository branches."""
        if not self.enabled or not self._client:
            return []

        try:
            response = self._client.list_branches(
                repositoryName=self.repository_name
            )
            return response.get("branches", [])
        except Exception:
            return []

    def list_pull_requests(self, status: str = "OPEN") -> List[dict]:
        """List pull requests."""
        if not self.enabled or not self._client:
            return []

        try:
            response = self._client.list_pull_requests(
                repositoryName=self.repository_name,
                pullRequestStatus=status
            )
            pr_ids = response.get("pullRequestIds", [])

            prs = []
            for pr_id in pr_ids[:20]:  # Limit to 20
                try:
                    pr_response = self._client.get_pull_request(
                        pullRequestId=pr_id
                    )
                    prs.append(pr_response.get("pullRequest", {}))
                except Exception:
                    pass
            return prs
        except Exception:
            return []

    def get_pull_request(self, pr_id: str) -> Optional[dict]:
        """Get a specific pull request."""
        if not self.enabled or not self._client:
            return None

        try:
            response = self._client.get_pull_request(pullRequestId=pr_id)
            return response.get("pullRequest")
        except Exception:
            return None

    def merge_pull_request(
        self,
        pr_id: str,
        merge_option: str = "SQUASH_MERGE"
    ) -> bool:
        """Merge a pull request."""
        if not self.enabled or not self._client:
            return False

        try:
            # Get PR details first
            pr = self.get_pull_request(pr_id)
            if not pr:
                return False

            target = pr.get("pullRequestTargets", [{}])[0]

            self._client.merge_pull_request_by_squash(
                pullRequestId=pr_id,
                repositoryName=self.repository_name,
                sourceCommitId=target.get("sourceCommit")
            ) if merge_option == "SQUASH_MERGE" else \
            self._client.merge_pull_request_by_fast_forward(
                pullRequestId=pr_id,
                repositoryName=self.repository_name,
                sourceCommitId=target.get("sourceCommit")
            )
            return True
        except Exception:
            return False

    def create_branch(self, branch_name: str, commit_id: str = None) -> bool:
        """Create a new branch."""
        if not self.enabled or not self._client:
            return False

        try:
            # Get HEAD commit if not specified
            if not commit_id:
                response = self._client.get_branch(
                    repositoryName=self.repository_name,
                    branchName=self.default_branch
                )
                commit_id = response.get("branch", {}).get("commitId")

            self._client.create_branch(
                repositoryName=self.repository_name,
                branchName=branch_name,
                commitId=commit_id
            )
            return True
        except Exception:
            return False

    def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch."""
        if not self.enabled or not self._client:
            return False

        try:
            self._client.delete_branch(
                repositoryName=self.repository_name,
                branchName=branch_name
            )
            return True
        except Exception:
            return False

    def list_repositories(self) -> List[dict]:
        """List repositories."""
        if not self._client:
            return []

        try:
            response = self._client.list_repositories()
            return response.get("repositories", [])
        except Exception:
            return []

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        repo_name = config_values.get("repository_name", "")
        region = config_values.get("region", "us-east-1")

        if repo_name:
            typer.echo("\n   Verifying AWS CodeCommit access...")
            try:
                import boto3
                client = boto3.client("codecommit", region_name=region)
                response = client.get_repository(repositoryName=repo_name)
                repo = response.get("repositoryMetadata", {})
                typer.secho(f"   Connected to: {repo.get('repositoryName')}", fg=typer.colors.GREEN)
            except ImportError:
                typer.secho("   boto3 not installed. Run: pip install boto3", fg=typer.colors.RED)
            except Exception as e:
                typer.secho(f"   Failed to connect: {e}", fg=typer.colors.RED)

        return config_values