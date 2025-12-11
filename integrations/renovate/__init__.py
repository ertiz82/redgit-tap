"""
Renovate integration for RedGit.

Automated dependency updates across multiple platforms.
"""

import os
import json
import subprocess
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from redgit.integrations.base import (
        CodeQualityBase, IntegrationType,
        QualityReport
    )
except ImportError:
    from enum import Enum
    from dataclasses import dataclass

    class IntegrationType(Enum):
        CODE_QUALITY = "code_quality"

    @dataclass
    class QualityReport:
        id: str
        status: str
        branch: str = None
        commit_sha: str = None
        url: str = None
        analyzed_at: str = None
        bugs: int = None
        vulnerabilities: int = None
        code_smells: int = None
        coverage: float = None
        duplications: float = None
        technical_debt: str = None
        quality_gate_status: str = None
        quality_gate_details: Dict = None

    class CodeQualityBase:
        integration_type = IntegrationType.CODE_QUALITY
        def __init__(self):
            self.enabled = False
        def setup(self, config): pass
        def get_quality_status(self, branch=None, commit_sha=None): pass
        def get_project_metrics(self): pass


class RenovateIntegration(CodeQualityBase):
    """Renovate dependency update integration"""

    name = "renovate"
    integration_type = IntegrationType.CODE_QUALITY

    # Custom notification events
    notification_events = {
        "pr_created": {
            "description": "Renovate PR created",
            "default": True
        },
        "pr_merged": {
            "description": "Renovate PR merged",
            "default": False
        },
        "major_update": {
            "description": "Major version update available",
            "default": True
        },
        "security_update": {
            "description": "Security update available",
            "default": True
        },
        "config_error": {
            "description": "Renovate configuration error",
            "default": True
        },
    }

    API_URL = "https://api.github.com"

    def __init__(self):
        super().__init__()
        self.token = ""
        self.platform = "github"  # github, gitlab, bitbucket
        self.owner = ""
        self.repo = ""
        self.renovate_bot = "renovate[bot]"

    def setup(self, config: dict):
        """Setup Renovate integration."""
        self.token = config.get("token") or os.getenv("GITHUB_TOKEN", "")
        self.platform = config.get("platform") or os.getenv("RENOVATE_PLATFORM", "github")
        self.owner = config.get("owner") or os.getenv("GITHUB_OWNER", "")
        self.repo = config.get("repo") or os.getenv("GITHUB_REPO", "")
        self.renovate_bot = config.get("renovate_bot", "renovate[bot]")

        if not self.token or not self.owner or not self.repo:
            self.enabled = False
            return

        self.enabled = True

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[Any]:
        """Make GitHub API request."""
        try:
            url = f"{self.API_URL}{endpoint}"

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

    def get_quality_status(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[QualityReport]:
        """Get Renovate status based on open PRs."""
        if not self.enabled:
            return None

        prs = self._get_renovate_prs()

        # Categorize PRs
        security_prs = [p for p in prs if "security" in p.get("title", "").lower()]
        major_prs = [p for p in prs if "major" in [l.get("name", "").lower() for l in p.get("labels", [])]]

        status = "passed"
        if security_prs:
            status = "warning"
        if len(prs) > 10:
            status = "warning"

        return QualityReport(
            id=f"{self.owner}/{self.repo}",
            status=status,
            url=f"https://github.com/{self.owner}/{self.repo}/pulls?q=author%3A{self.renovate_bot}",
            quality_gate_status=status,
            quality_gate_details={
                "open_prs": len(prs),
                "security_prs": len(security_prs),
                "major_updates": len(major_prs)
            }
        )

    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """Get Renovate metrics."""
        if not self.enabled:
            return None

        prs = self._get_renovate_prs()

        # Check for config file
        config_exists = self._check_config_exists()

        # Categorize by update type
        by_type = {"major": 0, "minor": 0, "patch": 0, "other": 0}
        for pr in prs:
            labels = [l.get("name", "").lower() for l in pr.get("labels", [])]
            if "major" in labels:
                by_type["major"] += 1
            elif "minor" in labels:
                by_type["minor"] += 1
            elif "patch" in labels:
                by_type["patch"] += 1
            else:
                by_type["other"] += 1

        return {
            "config_exists": config_exists,
            "open_prs": len(prs),
            "by_type": by_type,
            "url": f"https://github.com/{self.owner}/{self.repo}/pulls?q=author%3A{self.renovate_bot}"
        }

    def _get_renovate_prs(self, state: str = "open") -> List[Dict[str, Any]]:
        """Get Renovate PRs."""
        prs = self._api_request(
            f"/repos/{self.owner}/{self.repo}/pulls?state={state}&per_page=100"
        ) or []
        return [p for p in prs if p.get("user", {}).get("login") == self.renovate_bot]

    def _check_config_exists(self) -> bool:
        """Check if Renovate config exists."""
        config_files = [
            "renovate.json",
            "renovate.json5",
            ".renovaterc",
            ".renovaterc.json",
            ".github/renovate.json",
            ".github/renovate.json5"
        ]
        for config_file in config_files:
            result = self._api_request(
                f"/repos/{self.owner}/{self.repo}/contents/{config_file}"
            )
            if result:
                return True
        return False

    def get_outdated_dependencies(self) -> List[Dict[str, Any]]:
        """Get outdated dependencies from Renovate PRs."""
        if not self.enabled:
            return []

        prs = self._get_renovate_prs()

        outdated = []
        for pr in prs:
            labels = [l.get("name") for l in pr.get("labels", [])]
            outdated.append({
                "pr_number": pr.get("number"),
                "title": pr.get("title"),
                "url": pr.get("html_url"),
                "created_at": pr.get("created_at"),
                "labels": labels,
                "is_security": "security" in pr.get("title", "").lower(),
                "is_major": "major" in [l.lower() for l in labels]
            })

        return outdated

    def get_dashboard_issue(self) -> Optional[Dict[str, Any]]:
        """Get Renovate dashboard issue."""
        if not self.enabled:
            return None

        issues = self._api_request(
            f"/repos/{self.owner}/{self.repo}/issues?creator={self.renovate_bot}&state=open"
        ) or []

        for issue in issues:
            if "dependency dashboard" in issue.get("title", "").lower():
                return {
                    "number": issue.get("number"),
                    "title": issue.get("title"),
                    "url": issue.get("html_url"),
                    "body": issue.get("body")
                }
        return None

    def get_dependency_graph(self) -> Optional[Dict[str, Any]]:
        """Get dependency graph from package files."""
        if not self.enabled:
            return None

        # Check common package files
        package_files = {
            "package.json": "npm",
            "requirements.txt": "pip",
            "Gemfile": "bundler",
            "go.mod": "gomod",
            "pom.xml": "maven",
            "build.gradle": "gradle",
            "Cargo.toml": "cargo"
        }

        found_managers = []
        for file, manager in package_files.items():
            result = self._api_request(
                f"/repos/{self.owner}/{self.repo}/contents/{file}"
            )
            if result:
                found_managers.append(manager)

        return {
            "package_managers": found_managers,
            "count": len(found_managers)
        }

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        owner = config_values.get("owner", "")
        repo = config_values.get("repo", "")
        if token and owner and repo:
            typer.echo("\n   Checking Renovate status...")
            temp = RenovateIntegration()
            temp.token = token
            temp.owner = owner
            temp.repo = repo
            temp.enabled = True
            metrics = temp.get_project_metrics()
            if metrics:
                config_status = "configured" if metrics.get("config_exists") else "not configured"
                typer.secho(f"   Renovate {config_status}", fg=typer.colors.GREEN if metrics.get("config_exists") else typer.colors.YELLOW)
                typer.echo(f"   Open PRs: {metrics.get('open_prs', 0)}")
            else:
                typer.secho("   Failed to check status", fg=typer.colors.RED)
        return config_values