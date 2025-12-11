"""
Codacy integration for RedGit.

Automated code review with quality and security analysis.
"""

import os
import json
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from redgit.integrations.base import (
        CodeQualityBase, IntegrationType,
        QualityReport, SecurityIssue, CoverageReport
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
    class SecurityIssue:
        id: str
        severity: str
        title: str
        description: str = None
        package: str = None
        version: str = None
        fixed_in: str = None
        cve: str = None
        cwe: str = None
        url: str = None
        file_path: str = None
        line_number: int = None

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


class CodacyIntegration(CodeQualityBase):
    """Codacy automated code review integration"""

    name = "codacy"
    integration_type = IntegrationType.CODE_QUALITY

    # Custom notification events
    notification_events = {
        "grade_changed": {
            "description": "Codacy project grade changed",
            "default": True
        },
        "quality_gate_failed": {
            "description": "Codacy quality gate failed",
            "default": True
        },
        "security_issue_found": {
            "description": "Security issue detected by Codacy",
            "default": True
        },
        "new_issues": {
            "description": "New code issues detected",
            "default": False
        },
    }

    API_URL = "https://api.codacy.com"

    def __init__(self):
        super().__init__()
        self.api_token = ""
        self.provider = "gh"  # gh, bb, gl
        self.organization = ""
        self.repository = ""

    def setup(self, config: dict):
        """Setup Codacy integration."""
        self.api_token = config.get("api_token") or os.getenv("CODACY_API_TOKEN", "")
        self.provider = config.get("provider") or os.getenv("CODACY_PROVIDER", "gh")
        self.organization = config.get("organization") or os.getenv("CODACY_ORGANIZATION", "")
        self.repository = config.get("repository") or os.getenv("CODACY_REPOSITORY", "")

        if not self.api_token or not self.organization or not self.repository:
            self.enabled = False
            return

        self.enabled = True

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Codacy API request."""
        try:
            url = f"{self.API_URL}{endpoint}"

            headers = {
                "api-token": self.api_token,
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

    def _get_repo_path(self) -> str:
        """Get repository API path."""
        return f"/api/v3/analysis/organizations/{self.provider}/{self.organization}/repositories/{self.repository}"

    def get_quality_status(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[QualityReport]:
        """Get quality status for a branch."""
        if not self.enabled:
            return None

        endpoint = self._get_repo_path()
        if branch:
            endpoint = f"{endpoint}/branches/{branch}"
        if commit_sha:
            endpoint = f"{endpoint}/commits/{commit_sha}"

        result = self._api_request(endpoint)
        if not result:
            return None

        data = result.get("data", {})

        return QualityReport(
            id=f"{self.organization}/{self.repository}",
            status=data.get("grade", "").lower(),
            branch=branch,
            commit_sha=commit_sha,
            url=f"https://app.codacy.com/{self.provider}/{self.organization}/{self.repository}",
            bugs=data.get("issues", {}).get("bug"),
            vulnerabilities=data.get("issues", {}).get("security"),
            code_smells=data.get("issues", {}).get("codeStyle"),
            coverage=data.get("coverage"),
            duplications=data.get("duplication"),
            quality_gate_status="passed" if data.get("isUpToStandards") else "failed"
        )

    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """Get overall project quality metrics."""
        if not self.enabled:
            return None

        result = self._api_request(self._get_repo_path())
        if not result:
            return None

        data = result.get("data", {})

        return {
            "grade": data.get("grade"),
            "coverage": data.get("coverage"),
            "duplication": data.get("duplication"),
            "issues": data.get("issues"),
            "complexity": data.get("complexity"),
            "is_up_to_standards": data.get("isUpToStandards")
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

        endpoint = f"{self._get_repo_path()}/issues"
        result = self._api_request(endpoint)

        if not result:
            return []

        issues = result.get("data", [])

        # Filter by severity if specified
        if severity:
            issues = [i for i in issues if i.get("level", "").lower() == severity.lower()]

        return issues[:limit]

    def get_security_issues(
        self,
        severity: str = None,
        limit: int = 50
    ) -> List[SecurityIssue]:
        """Get security vulnerabilities."""
        if not self.enabled:
            return []

        endpoint = f"{self._get_repo_path()}/issues?category=Security"
        result = self._api_request(endpoint)

        if not result:
            return []

        issues = []
        for issue in result.get("data", [])[:limit]:
            if severity and issue.get("level", "").lower() != severity.lower():
                continue
            issues.append(SecurityIssue(
                id=issue.get("id", ""),
                severity=issue.get("level", "").lower(),
                title=issue.get("message", ""),
                description=issue.get("suggestion"),
                file_path=issue.get("filePath"),
                line_number=issue.get("lineNumber"),
                url=f"https://app.codacy.com/{self.provider}/{self.organization}/{self.repository}/issues"
            ))

        return issues

    def get_coverage(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[CoverageReport]:
        """Get code coverage report."""
        if not self.enabled:
            return None

        endpoint = f"{self._get_repo_path()}/coverage"
        if branch:
            endpoint = f"{endpoint}?branch={branch}"

        result = self._api_request(endpoint)
        if not result:
            return None

        data = result.get("data", {})

        return CoverageReport(
            id=f"{self.organization}/{self.repository}",
            branch=branch,
            commit_sha=commit_sha,
            url=f"https://app.codacy.com/{self.provider}/{self.organization}/{self.repository}/coverage",
            line_coverage=data.get("coverage"),
            lines_covered=data.get("coveredLines"),
            lines_total=data.get("totalLines")
        )

    def get_pr_analysis(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get quality analysis for a pull request."""
        if not self.enabled:
            return None

        endpoint = f"{self._get_repo_path()}/pull-requests/{pr_number}"
        result = self._api_request(endpoint)

        if not result:
            return None

        data = result.get("data", {})
        return {
            "pr_number": pr_number,
            "is_up_to_standards": data.get("isUpToStandards"),
            "new_issues": data.get("newIssues", 0),
            "fixed_issues": data.get("fixedIssues", 0),
            "coverage_variation": data.get("coverageVariation"),
            "url": f"https://app.codacy.com/{self.provider}/{self.organization}/{self.repository}/pullRequests/{pr_number}"
        }

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        api_token = config_values.get("api_token", "")
        organization = config_values.get("organization", "")
        repository = config_values.get("repository", "")
        if api_token and organization and repository:
            typer.echo("\n   Verifying Codacy connection...")
            temp = CodacyIntegration()
            temp.api_token = api_token
            temp.organization = organization
            temp.repository = repository
            temp.enabled = True
            metrics = temp.get_project_metrics()
            if metrics:
                typer.secho(f"   Connected! Grade: {metrics.get('grade', 'N/A')}", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to connect", fg=typer.colors.RED)
        return config_values