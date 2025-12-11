"""
SonarQube/SonarCloud integration for RedGit.

Code quality analysis with quality gates, coverage, and technical debt tracking.
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


class SonarQubeIntegration(CodeQualityBase):
    """SonarQube/SonarCloud code quality integration"""

    name = "sonarqube"
    integration_type = IntegrationType.CODE_QUALITY

    # Custom notification events
    notification_events = {
        "quality_gate_passed": {
            "description": "SonarQube quality gate passed",
            "default": True
        },
        "quality_gate_failed": {
            "description": "SonarQube quality gate failed",
            "default": True
        },
        "new_bugs": {
            "description": "New bugs detected by SonarQube",
            "default": True
        },
        "new_vulnerabilities": {
            "description": "New vulnerabilities detected",
            "default": True
        },
        "coverage_decreased": {
            "description": "Code coverage decreased",
            "default": False
        },
    }

    def __init__(self):
        super().__init__()
        self.host = ""
        self.token = ""
        self.project_key = ""
        self.organization = ""  # For SonarCloud

    def setup(self, config: dict):
        """Setup SonarQube integration."""
        self.host = config.get("host") or os.getenv("SONAR_HOST_URL", "https://sonarcloud.io")
        self.token = config.get("token") or os.getenv("SONAR_TOKEN", "")
        self.project_key = config.get("project_key") or os.getenv("SONAR_PROJECT_KEY", "")
        self.organization = config.get("organization") or os.getenv("SONAR_ORGANIZATION", "")

        # Remove trailing slash
        self.host = self.host.rstrip("/")

        if not self.token or not self.project_key:
            self.enabled = False
            return

        self.enabled = True

    def _api_request(
        self,
        endpoint: str,
        params: Dict[str, str] = None,
        method: str = "GET"
    ) -> Optional[dict]:
        """Make SonarQube API request."""
        try:
            url = f"{self.host}/api{endpoint}"
            if params:
                query = "&".join(f"{k}={v}" for k, v in params.items())
                url = f"{url}?{query}"

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

    def get_quality_status(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[QualityReport]:
        """Get quality status for a branch."""
        if not self.enabled:
            return None

        params = {"project": self.project_key}
        if branch:
            params["branch"] = branch

        # Get quality gate status
        gate_result = self._api_request("/qualitygates/project_status", params)
        if not gate_result:
            return None

        gate_status = gate_result.get("projectStatus", {})

        # Get metrics
        metrics_params = {
            "component": self.project_key,
            "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,sqale_index"
        }
        if branch:
            metrics_params["branch"] = branch

        metrics_result = self._api_request("/measures/component", metrics_params)
        metrics = {}
        if metrics_result:
            for measure in metrics_result.get("component", {}).get("measures", []):
                metrics[measure["metric"]] = measure.get("value")

        return QualityReport(
            id=self.project_key,
            status=gate_status.get("status", "NONE").lower(),
            branch=branch,
            url=f"{self.host}/dashboard?id={self.project_key}",
            bugs=int(metrics.get("bugs", 0)) if metrics.get("bugs") else None,
            vulnerabilities=int(metrics.get("vulnerabilities", 0)) if metrics.get("vulnerabilities") else None,
            code_smells=int(metrics.get("code_smells", 0)) if metrics.get("code_smells") else None,
            coverage=float(metrics.get("coverage", 0)) if metrics.get("coverage") else None,
            duplications=float(metrics.get("duplicated_lines_density", 0)) if metrics.get("duplicated_lines_density") else None,
            technical_debt=metrics.get("sqale_index"),
            quality_gate_status=gate_status.get("status", "").lower(),
            quality_gate_details=gate_status.get("conditions")
        )

    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """Get overall project quality metrics."""
        if not self.enabled:
            return None

        result = self._api_request("/measures/component", {
            "component": self.project_key,
            "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,sqale_index,sqale_rating,reliability_rating,security_rating,ncloc"
        })

        if not result:
            return None

        metrics = {}
        for measure in result.get("component", {}).get("measures", []):
            metrics[measure["metric"]] = measure.get("value")

        return metrics

    def get_issues(
        self,
        severity: str = None,
        issue_type: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get code quality issues."""
        if not self.enabled:
            return []

        params = {
            "componentKeys": self.project_key,
            "ps": str(limit),
            "resolved": "false"
        }
        if severity:
            params["severities"] = severity.upper()
        if issue_type:
            params["types"] = issue_type.upper()

        result = self._api_request("/issues/search", params)
        if result:
            return result.get("issues", [])
        return []

    def get_security_issues(
        self,
        severity: str = None,
        limit: int = 50
    ) -> List[SecurityIssue]:
        """Get security vulnerabilities."""
        if not self.enabled:
            return []

        params = {
            "componentKeys": self.project_key,
            "types": "VULNERABILITY",
            "ps": str(limit),
            "resolved": "false"
        }
        if severity:
            params["severities"] = severity.upper()

        result = self._api_request("/issues/search", params)
        if not result:
            return []

        issues = []
        for issue in result.get("issues", []):
            issues.append(SecurityIssue(
                id=issue.get("key", ""),
                severity=issue.get("severity", "").lower(),
                title=issue.get("message", ""),
                description=issue.get("message"),
                cwe=issue.get("cwe"),
                file_path=issue.get("component", "").split(":")[-1],
                line_number=issue.get("line"),
                url=f"{self.host}/project/issues?id={self.project_key}&issues={issue.get('key')}"
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

        params = {
            "component": self.project_key,
            "metricKeys": "coverage,line_coverage,branch_coverage,lines_to_cover,uncovered_lines"
        }
        if branch:
            params["branch"] = branch

        result = self._api_request("/measures/component", params)
        if not result:
            return None

        metrics = {}
        for measure in result.get("component", {}).get("measures", []):
            metrics[measure["metric"]] = measure.get("value")

        lines_total = int(metrics.get("lines_to_cover", 0)) if metrics.get("lines_to_cover") else None
        uncovered = int(metrics.get("uncovered_lines", 0)) if metrics.get("uncovered_lines") else 0
        lines_covered = (lines_total - uncovered) if lines_total else None

        return CoverageReport(
            id=self.project_key,
            branch=branch,
            url=f"{self.host}/component_measures?id={self.project_key}&metric=coverage",
            line_coverage=float(metrics.get("line_coverage", 0)) if metrics.get("line_coverage") else None,
            branch_coverage=float(metrics.get("branch_coverage", 0)) if metrics.get("branch_coverage") else None,
            lines_covered=lines_covered,
            lines_total=lines_total
        )

    def get_quality_gate_status(self) -> Optional[str]:
        """Get quality gate status."""
        if not self.enabled:
            return None

        result = self._api_request("/qualitygates/project_status", {
            "projectKey": self.project_key
        })
        if result:
            return result.get("projectStatus", {}).get("status", "").lower()
        return None

    def get_pr_analysis(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get quality analysis for a pull request."""
        if not self.enabled:
            return None

        result = self._api_request("/measures/component", {
            "component": self.project_key,
            "pullRequest": str(pr_number),
            "metricKeys": "new_bugs,new_vulnerabilities,new_code_smells,new_coverage,new_duplicated_lines_density"
        })

        if not result:
            return None

        metrics = {}
        for measure in result.get("component", {}).get("measures", []):
            metrics[measure["metric"]] = measure.get("value")

        return {
            "pr_number": pr_number,
            "new_bugs": int(metrics.get("new_bugs", 0)) if metrics.get("new_bugs") else 0,
            "new_vulnerabilities": int(metrics.get("new_vulnerabilities", 0)) if metrics.get("new_vulnerabilities") else 0,
            "new_code_smells": int(metrics.get("new_code_smells", 0)) if metrics.get("new_code_smells") else 0,
            "new_coverage": float(metrics.get("new_coverage", 0)) if metrics.get("new_coverage") else None,
            "url": f"{self.host}/dashboard?id={self.project_key}&pullRequest={pr_number}"
        }

    def compare_branches(
        self,
        head: str,
        base: str = None
    ) -> Optional[Dict[str, Any]]:
        """Compare quality metrics between branches."""
        if not self.enabled:
            return None

        base = base or "main"
        head_status = self.get_quality_status(branch=head)
        base_status = self.get_quality_status(branch=base)

        if not head_status or not base_status:
            return None

        return {
            "head": head,
            "base": base,
            "bugs_diff": (head_status.bugs or 0) - (base_status.bugs or 0),
            "vulnerabilities_diff": (head_status.vulnerabilities or 0) - (base_status.vulnerabilities or 0),
            "code_smells_diff": (head_status.code_smells or 0) - (base_status.code_smells or 0),
            "coverage_diff": (head_status.coverage or 0) - (base_status.coverage or 0),
            "head_quality_gate": head_status.quality_gate_status,
            "base_quality_gate": base_status.quality_gate_status
        }

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        host = config_values.get("host", "https://sonarcloud.io")
        project_key = config_values.get("project_key", "")
        if token and project_key:
            typer.echo("\n   Verifying SonarQube connection...")
            temp = SonarQubeIntegration()
            temp.host = host.rstrip("/")
            temp.token = token
            temp.project_key = project_key
            temp.enabled = True
            metrics = temp.get_project_metrics()
            if metrics:
                typer.secho(f"   Connected to project: {project_key}", fg=typer.colors.GREEN)
                if "ncloc" in metrics:
                    typer.echo(f"   Lines of code: {metrics['ncloc']}")
            else:
                typer.secho("   Failed to connect or project not found", fg=typer.colors.RED)
        return config_values