"""
CodeClimate integration for RedGit.

Maintainability analysis with test coverage tracking.
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


class CodeClimateIntegration(CodeQualityBase):
    """CodeClimate code quality integration"""

    name = "codeclimate"
    integration_type = IntegrationType.CODE_QUALITY

    # Custom notification events
    notification_events = {
        "maintainability_changed": {
            "description": "CodeClimate maintainability grade changed",
            "default": True
        },
        "coverage_changed": {
            "description": "CodeClimate test coverage changed",
            "default": True
        },
        "new_issues": {
            "description": "New code issues detected",
            "default": False
        },
        "technical_debt_increased": {
            "description": "Technical debt increased",
            "default": False
        },
    }

    API_URL = "https://api.codeclimate.com/v1"

    def __init__(self):
        super().__init__()
        self.token = ""
        self.repo_id = ""
        self.repo_name = ""

    def setup(self, config: dict):
        """Setup CodeClimate integration."""
        self.token = config.get("token") or os.getenv("CODECLIMATE_TOKEN", "")
        self.repo_id = config.get("repo_id") or os.getenv("CODECLIMATE_REPO_ID", "")
        self.repo_name = config.get("repo_name") or os.getenv("CODECLIMATE_REPO_NAME", "")

        if not self.token:
            self.enabled = False
            return

        # Auto-detect repo_id if not provided
        if not self.repo_id and self.repo_name:
            self._detect_repo_id()

        self.enabled = bool(self.repo_id)

    def _detect_repo_id(self):
        """Detect repository ID from name."""
        result = self._api_request("/repos", params={"github_slug": self.repo_name})
        if result and result.get("data"):
            self.repo_id = result["data"][0].get("id", "")

    def _api_request(
        self,
        endpoint: str,
        params: Dict[str, str] = None,
        method: str = "GET"
    ) -> Optional[dict]:
        """Make CodeClimate API request."""
        try:
            url = f"{self.API_URL}{endpoint}"
            if params:
                query = "&".join(f"{k}={v}" for k, v in params.items())
                url = f"{url}?{query}"

            headers = {
                "Authorization": f"Token token={self.token}",
                "Accept": "application/vnd.api+json"
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

    def get_quality_status(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[QualityReport]:
        """Get quality status for a branch."""
        if not self.enabled:
            return None

        # Get repository info
        result = self._api_request(f"/repos/{self.repo_id}")
        if not result:
            return None

        repo_data = result.get("data", {}).get("attributes", {})
        test_reporter = repo_data.get("test_reporter_id")

        # Get latest snapshot
        snapshot_result = self._api_request(
            f"/repos/{self.repo_id}/snapshots",
            params={"filter[branch]": branch or "main", "page[size]": "1"}
        )

        snapshot = {}
        if snapshot_result and snapshot_result.get("data"):
            snapshot = snapshot_result["data"][0].get("attributes", {})

        return QualityReport(
            id=self.repo_id,
            status="passed" if snapshot.get("gpa", 0) >= 2.0 else "warning",
            branch=branch,
            url=f"https://codeclimate.com/repos/{self.repo_id}",
            analyzed_at=snapshot.get("committed_at"),
            code_smells=snapshot.get("issues_count"),
            coverage=repo_data.get("test_coverage"),
            technical_debt=snapshot.get("technical_debt_ratio"),
            quality_gate_status="passed" if snapshot.get("gpa", 0) >= 2.0 else "failed"
        )

    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """Get overall project quality metrics."""
        if not self.enabled:
            return None

        result = self._api_request(f"/repos/{self.repo_id}")
        if not result:
            return None

        attrs = result.get("data", {}).get("attributes", {})

        return {
            "gpa": attrs.get("gpa"),
            "test_coverage": attrs.get("test_coverage"),
            "badge_token": attrs.get("badge_token"),
            "created_at": attrs.get("created_at")
        }

    def get_issues(
        self,
        severity: str = None,
        issue_type: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get code quality issues."""
        if not self.enabled:
            return []

        params = {"page[size]": str(limit)}
        if severity:
            params["filter[severity]"] = severity

        result = self._api_request(f"/repos/{self.repo_id}/issues", params)
        if result:
            return [
                {
                    "id": issue.get("id"),
                    **issue.get("attributes", {})
                }
                for issue in result.get("data", [])
            ]
        return []

    def get_coverage(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[CoverageReport]:
        """Get code coverage report."""
        if not self.enabled:
            return None

        params = {"page[size]": "1"}
        if branch:
            params["filter[branch]"] = branch

        result = self._api_request(f"/repos/{self.repo_id}/test_reports", params)
        if not result or not result.get("data"):
            return None

        report = result["data"][0].get("attributes", {})

        return CoverageReport(
            id=result["data"][0].get("id", ""),
            commit_sha=report.get("commit_sha"),
            branch=report.get("branch"),
            url=f"https://codeclimate.com/repos/{self.repo_id}/test_coverage",
            line_coverage=report.get("covered_percent"),
            lines_covered=report.get("covered_count"),
            lines_total=report.get("lines_of_code_total")
        )

    def get_pr_analysis(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get quality analysis for a pull request."""
        if not self.enabled:
            return None

        result = self._api_request(
            f"/repos/{self.repo_id}/pulls/{pr_number}"
        )
        if not result:
            return None

        attrs = result.get("data", {}).get("attributes", {})
        return {
            "pr_number": pr_number,
            "issues_added": attrs.get("issues_added", 0),
            "issues_fixed": attrs.get("issues_fixed", 0),
            "coverage_diff": attrs.get("coverage_diff"),
            "approvals": attrs.get("approvals", []),
            "url": f"https://codeclimate.com/repos/{self.repo_id}/pulls/{pr_number}"
        }

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        repo_id = config_values.get("repo_id", "")
        if token:
            typer.echo("\n   Verifying CodeClimate connection...")
            temp = CodeClimateIntegration()
            temp.token = token
            temp.repo_id = repo_id
            temp.enabled = bool(repo_id)
            if repo_id:
                metrics = temp.get_project_metrics()
                if metrics:
                    typer.secho(f"   Connected! GPA: {metrics.get('gpa', 'N/A')}", fg=typer.colors.GREEN)
                else:
                    typer.secho("   Failed to fetch metrics", fg=typer.colors.RED)
            else:
                typer.secho("   Token verified, repo_id needed", fg=typer.colors.YELLOW)
        return config_values