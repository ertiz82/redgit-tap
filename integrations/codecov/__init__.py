"""
Codecov integration for RedGit.

Code coverage reporting and tracking.
"""

import os
import json
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from redgit.integrations.base import (
        CodeQualityBase, IntegrationType,
        QualityReport, CoverageReport
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

    @dataclass
    class CoverageReport:
        id: str
        commit_sha: str = None
        branch: str = None
        url: str = None
        line_coverage: float = None
        branch_coverage: float = None
        function_coverage: float = None
        lines_covered: int = None
        lines_total: int = None
        coverage_change: float = None
        base_coverage: float = None

    class CodeQualityBase:
        integration_type = IntegrationType.CODE_QUALITY
        def __init__(self):
            self.enabled = False
        def setup(self, config): pass
        def get_quality_status(self, branch=None, commit_sha=None): pass
        def get_project_metrics(self): pass


class CodecovIntegration(CodeQualityBase):
    """Codecov coverage reporting integration"""

    name = "codecov"
    integration_type = IntegrationType.CODE_QUALITY

    # Custom notification events
    notification_events = {
        "coverage_decreased": {
            "description": "Code coverage decreased",
            "default": True
        },
        "coverage_increased": {
            "description": "Code coverage increased",
            "default": False
        },
        "target_missed": {
            "description": "Coverage target missed",
            "default": True
        },
        "new_uncovered_lines": {
            "description": "New uncovered lines detected",
            "default": False
        },
    }

    API_URL = "https://api.codecov.io/api/v2"

    def __init__(self):
        super().__init__()
        self.token = ""
        self.service = "github"  # github, gitlab, bitbucket
        self.owner = ""
        self.repo = ""

    def setup(self, config: dict):
        """Setup Codecov integration."""
        self.token = config.get("token") or os.getenv("CODECOV_TOKEN", "")
        self.service = config.get("service") or os.getenv("CODECOV_SERVICE", "github")
        self.owner = config.get("owner") or os.getenv("GITHUB_OWNER", "")
        self.repo = config.get("repo") or os.getenv("GITHUB_REPO", "")

        if not self.token or not self.owner or not self.repo:
            self.enabled = False
            return

        self.enabled = True

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET"
    ) -> Optional[dict]:
        """Make Codecov API request."""
        try:
            url = f"{self.API_URL}{endpoint}"

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json"
            }

            req = Request(url, headers=headers, method=method)

            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 404:
                return None
            raise
        except URLError:
            return None

    def _get_repo_path(self) -> str:
        """Get repository API path."""
        return f"/{self.service}/{self.owner}/repos/{self.repo}"

    def get_quality_status(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[QualityReport]:
        """Get coverage status."""
        if not self.enabled:
            return None

        coverage = self.get_coverage(branch=branch, commit_sha=commit_sha)
        if not coverage:
            return None

        # Determine status based on coverage
        cov = coverage.line_coverage or 0
        status = "passed"
        if cov < 50:
            status = "failed"
        elif cov < 70:
            status = "warning"

        return QualityReport(
            id=f"{self.owner}/{self.repo}",
            status=status,
            branch=branch,
            commit_sha=commit_sha,
            url=f"https://codecov.io/{self.service}/{self.owner}/{self.repo}",
            coverage=cov,
            quality_gate_status=status
        )

    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """Get overall project coverage metrics."""
        if not self.enabled:
            return None

        result = self._api_request(self._get_repo_path())
        if not result:
            return None

        return {
            "name": result.get("name"),
            "language": result.get("language"),
            "activated": result.get("activated"),
            "private": result.get("private"),
            "coverage": result.get("totals", {}).get("coverage"),
            "files": result.get("totals", {}).get("files"),
            "lines": result.get("totals", {}).get("lines"),
            "url": f"https://codecov.io/{self.service}/{self.owner}/{self.repo}"
        }

    def get_coverage(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[CoverageReport]:
        """Get code coverage report."""
        if not self.enabled:
            return None

        endpoint = self._get_repo_path()
        if commit_sha:
            endpoint = f"{endpoint}/commits/{commit_sha}"
        elif branch:
            endpoint = f"{endpoint}/branches/{branch}"

        result = self._api_request(endpoint)
        if not result:
            return None

        totals = result.get("totals", {})

        return CoverageReport(
            id=f"{self.owner}/{self.repo}",
            commit_sha=result.get("commitid") or commit_sha,
            branch=result.get("branch") or branch,
            url=f"https://codecov.io/{self.service}/{self.owner}/{self.repo}",
            line_coverage=totals.get("coverage"),
            branch_coverage=totals.get("branches"),
            lines_covered=totals.get("hits"),
            lines_total=totals.get("lines"),
            coverage_change=totals.get("diff")
        )

    def get_pr_analysis(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get coverage analysis for a pull request."""
        if not self.enabled:
            return None

        result = self._api_request(f"{self._get_repo_path()}/pulls/{pr_number}")
        if not result:
            return None

        return {
            "pr_number": pr_number,
            "head_coverage": result.get("head", {}).get("totals", {}).get("coverage"),
            "base_coverage": result.get("base", {}).get("totals", {}).get("coverage"),
            "coverage_diff": result.get("diff", {}).get("coverage"),
            "state": result.get("state"),
            "url": f"https://codecov.io/{self.service}/{self.owner}/{self.repo}/pull/{pr_number}"
        }

    def compare_branches(
        self,
        head: str,
        base: str = None
    ) -> Optional[Dict[str, Any]]:
        """Compare coverage between branches."""
        if not self.enabled:
            return None

        base = base or "main"

        head_cov = self.get_coverage(branch=head)
        base_cov = self.get_coverage(branch=base)

        if not head_cov or not base_cov:
            return None

        return {
            "head": head,
            "base": base,
            "head_coverage": head_cov.line_coverage,
            "base_coverage": base_cov.line_coverage,
            "diff": (head_cov.line_coverage or 0) - (base_cov.line_coverage or 0)
        }

    def list_commits(self, branch: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent commits with coverage."""
        if not self.enabled:
            return []

        endpoint = f"{self._get_repo_path()}/commits"
        if branch:
            endpoint = f"{endpoint}?branch={branch}"

        result = self._api_request(endpoint)
        if not result:
            return []

        commits = result.get("results", [])[:limit]
        return [
            {
                "sha": c.get("commitid"),
                "coverage": c.get("totals", {}).get("coverage"),
                "timestamp": c.get("timestamp"),
                "author": c.get("author", {}).get("username")
            }
            for c in commits
        ]

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        owner = config_values.get("owner", "")
        repo = config_values.get("repo", "")
        if token and owner and repo:
            typer.echo("\n   Verifying Codecov connection...")
            temp = CodecovIntegration()
            temp.token = token
            temp.owner = owner
            temp.repo = repo
            temp.enabled = True
            metrics = temp.get_project_metrics()
            if metrics:
                cov = metrics.get("coverage")
                cov_str = f"{cov:.1f}%" if cov else "N/A"
                typer.secho(f"   Connected! Coverage: {cov_str}", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to connect or repo not found", fg=typer.colors.RED)
        return config_values