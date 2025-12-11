"""
Coveralls integration for RedGit.

Code coverage tracking and reporting.
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


class CoverallsIntegration(CodeQualityBase):
    """Coveralls coverage tracking integration"""

    name = "coveralls"
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
        "build_passed": {
            "description": "Coverage build passed",
            "default": False
        },
        "build_failed": {
            "description": "Coverage build failed",
            "default": True
        },
    }

    API_URL = "https://coveralls.io"

    def __init__(self):
        super().__init__()
        self.token = ""
        self.service = "github"
        self.owner = ""
        self.repo = ""

    def setup(self, config: dict):
        """Setup Coveralls integration."""
        self.token = config.get("token") or os.getenv("COVERALLS_REPO_TOKEN", "")
        self.service = config.get("service") or os.getenv("COVERALLS_SERVICE", "github")
        self.owner = config.get("owner") or os.getenv("GITHUB_OWNER", "")
        self.repo = config.get("repo") or os.getenv("GITHUB_REPO", "")

        if not self.owner or not self.repo:
            self.enabled = False
            return

        self.enabled = True

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET"
    ) -> Optional[dict]:
        """Make Coveralls API request."""
        try:
            url = f"{self.API_URL}{endpoint}"

            headers = {
                "Accept": "application/json"
            }

            if self.token:
                headers["Authorization"] = f"token {self.token}"

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
        """Get repository path for API."""
        return f"github/{self.owner}/{self.repo}"

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
            url=f"https://coveralls.io/{self._get_repo_path()}",
            coverage=cov,
            quality_gate_status=status
        )

    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """Get overall project coverage metrics."""
        if not self.enabled:
            return None

        result = self._api_request(f"/api/repos/{self._get_repo_path()}")
        if not result:
            # Try public endpoint
            result = self._api_request(f"/{self._get_repo_path()}.json")

        if not result:
            return None

        return {
            "name": result.get("name") or f"{self.owner}/{self.repo}",
            "coverage": result.get("covered_percent") or result.get("coverage_change"),
            "badge_url": result.get("badge_url"),
            "created_at": result.get("created_at"),
            "url": f"https://coveralls.io/{self._get_repo_path()}"
        }

    def get_coverage(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[CoverageReport]:
        """Get code coverage report."""
        if not self.enabled:
            return None

        # Get latest build
        endpoint = f"/{self._get_repo_path()}.json"
        if branch:
            endpoint = f"{endpoint}?branch={branch}"

        result = self._api_request(endpoint)
        if not result:
            return None

        return CoverageReport(
            id=f"{self.owner}/{self.repo}",
            commit_sha=result.get("commit_sha") or commit_sha,
            branch=result.get("branch") or branch,
            url=f"https://coveralls.io/{self._get_repo_path()}",
            line_coverage=result.get("covered_percent"),
            lines_covered=result.get("relevant_lines"),
            coverage_change=result.get("coverage_change")
        )

    def get_pr_analysis(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get coverage analysis for a pull request."""
        if not self.enabled:
            return None

        # Coveralls doesn't have a direct PR endpoint, but we can get builds
        result = self._api_request(f"/{self._get_repo_path()}.json")
        if not result:
            return None

        return {
            "pr_number": pr_number,
            "coverage": result.get("covered_percent"),
            "coverage_change": result.get("coverage_change"),
            "url": f"https://coveralls.io/{self._get_repo_path()}"
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

    def list_builds(self, branch: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent builds with coverage."""
        if not self.enabled:
            return []

        endpoint = f"/api/repos/{self._get_repo_path()}/builds"
        if branch:
            endpoint = f"{endpoint}?branch={branch}"

        result = self._api_request(endpoint)
        if not result:
            return []

        builds = result.get("builds", [])[:limit]
        return [
            {
                "id": b.get("id"),
                "commit_sha": b.get("commit_sha"),
                "branch": b.get("branch"),
                "coverage": b.get("covered_percent"),
                "created_at": b.get("created_at")
            }
            for b in builds
        ]

    def get_source_files(self, build_id: int = None) -> List[Dict[str, Any]]:
        """Get source files with coverage info."""
        if not self.enabled:
            return []

        endpoint = f"/api/repos/{self._get_repo_path()}/source_files"
        if build_id:
            endpoint = f"{endpoint}?build_id={build_id}"

        result = self._api_request(endpoint)
        if not result:
            return []

        return result.get("source_files", [])

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        owner = config_values.get("owner", "")
        repo = config_values.get("repo", "")
        if owner and repo:
            typer.echo("\n   Checking Coveralls status...")
            temp = CoverallsIntegration()
            temp.owner = owner
            temp.repo = repo
            temp.token = config_values.get("token", "")
            temp.enabled = True
            metrics = temp.get_project_metrics()
            if metrics:
                cov = metrics.get("coverage")
                cov_str = f"{cov:.1f}%" if cov else "N/A"
                typer.secho(f"   Connected! Coverage: {cov_str}", fg=typer.colors.GREEN)
            else:
                typer.secho("   Repo not found on Coveralls", fg=typer.colors.YELLOW)
        return config_values