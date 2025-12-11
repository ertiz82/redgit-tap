"""
Snyk integration for RedGit.

Security vulnerability scanning and dependency management.
"""

import os
import json
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from redgit.integrations.base import (
        CodeQualityBase, IntegrationType,
        QualityReport, SecurityIssue
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

    class CodeQualityBase:
        integration_type = IntegrationType.CODE_QUALITY
        def __init__(self):
            self.enabled = False
        def setup(self, config): pass
        def get_quality_status(self, branch=None, commit_sha=None): pass
        def get_project_metrics(self): pass


class SnykIntegration(CodeQualityBase):
    """Snyk security vulnerability integration"""

    name = "snyk"
    integration_type = IntegrationType.CODE_QUALITY

    # Custom notification events
    notification_events = {
        "critical_vulnerability": {
            "description": "Critical vulnerability detected by Snyk",
            "default": True
        },
        "high_vulnerability": {
            "description": "High severity vulnerability detected",
            "default": True
        },
        "new_vulnerabilities": {
            "description": "New vulnerabilities detected",
            "default": True
        },
        "vulnerability_fixed": {
            "description": "Vulnerability fixed",
            "default": False
        },
        "license_issue": {
            "description": "License compliance issue detected",
            "default": False
        },
    }

    API_URL = "https://api.snyk.io/v1"

    def __init__(self):
        super().__init__()
        self.token = ""
        self.org_id = ""
        self.project_id = ""

    def setup(self, config: dict):
        """Setup Snyk integration."""
        self.token = config.get("token") or os.getenv("SNYK_TOKEN", "")
        self.org_id = config.get("org_id") or os.getenv("SNYK_ORG_ID", "")
        self.project_id = config.get("project_id") or os.getenv("SNYK_PROJECT_ID", "")

        if not self.token:
            self.enabled = False
            return

        # Auto-detect org_id if not provided
        if not self.org_id:
            self._detect_org_id()

        self.enabled = bool(self.org_id)

    def _detect_org_id(self):
        """Detect organization ID."""
        result = self._api_request("/orgs")
        if result and result.get("orgs"):
            self.org_id = result["orgs"][0].get("id", "")

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Snyk API request."""
        try:
            url = f"{self.API_URL}{endpoint}"

            headers = {
                "Authorization": f"token {self.token}",
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

    def get_quality_status(
        self,
        branch: str = None,
        commit_sha: str = None
    ) -> Optional[QualityReport]:
        """Get security status for a project."""
        if not self.enabled or not self.project_id:
            return None

        result = self._api_request(f"/org/{self.org_id}/project/{self.project_id}")
        if not result:
            return None

        issues = result.get("issueCountsBySeverity", {})
        total_vulns = sum(issues.values())

        status = "passed"
        if issues.get("critical", 0) > 0:
            status = "failed"
        elif issues.get("high", 0) > 0:
            status = "warning"

        return QualityReport(
            id=self.project_id,
            status=status,
            branch=result.get("branch"),
            url=f"https://app.snyk.io/org/{self.org_id}/project/{self.project_id}",
            vulnerabilities=total_vulns,
            quality_gate_status=status,
            quality_gate_details={
                "critical": issues.get("critical", 0),
                "high": issues.get("high", 0),
                "medium": issues.get("medium", 0),
                "low": issues.get("low", 0)
            }
        )

    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """Get overall project security metrics."""
        if not self.enabled or not self.project_id:
            return None

        result = self._api_request(f"/org/{self.org_id}/project/{self.project_id}")
        if not result:
            return None

        return {
            "name": result.get("name"),
            "type": result.get("type"),
            "origin": result.get("origin"),
            "issues": result.get("issueCountsBySeverity"),
            "last_tested": result.get("lastTestedDate"),
            "branch": result.get("branch")
        }

    def get_security_issues(
        self,
        severity: str = None,
        limit: int = 50
    ) -> List[SecurityIssue]:
        """Get security vulnerabilities."""
        if not self.enabled or not self.project_id:
            return []

        result = self._api_request(
            f"/org/{self.org_id}/project/{self.project_id}/aggregated-issues",
            method="POST",
            data={"includeDescription": True, "includeIntroducedThrough": True}
        )

        if not result:
            return []

        issues = []
        for issue in result.get("issues", [])[:limit]:
            issue_data = issue.get("issueData", {})
            if severity and issue_data.get("severity", "").lower() != severity.lower():
                continue

            # Get fix info
            fix_info = issue.get("fixInfo", {})
            fixed_in = None
            if fix_info.get("upgradePaths"):
                paths = fix_info["upgradePaths"]
                if paths and paths[0]:
                    fixed_in = paths[0][0] if isinstance(paths[0], list) else str(paths[0])

            issues.append(SecurityIssue(
                id=issue_data.get("id", ""),
                severity=issue_data.get("severity", "").lower(),
                title=issue_data.get("title", ""),
                description=issue_data.get("description"),
                package=issue.get("pkgName"),
                version=issue.get("pkgVersion"),
                fixed_in=fixed_in,
                cve=",".join(issue_data.get("identifiers", {}).get("CVE", [])),
                cwe=",".join(issue_data.get("identifiers", {}).get("CWE", [])),
                url=issue_data.get("url")
            ))

        return issues

    def get_dependencies(self) -> List[Dict[str, Any]]:
        """Get project dependencies with vulnerability info."""
        if not self.enabled or not self.project_id:
            return []

        result = self._api_request(f"/org/{self.org_id}/project/{self.project_id}/dep-graph")
        if not result:
            return []

        graph = result.get("depGraph", {})
        pkgs = graph.get("pkgs", [])

        return [
            {
                "name": pkg.get("id", "").split("@")[0],
                "version": pkg.get("id", "").split("@")[-1] if "@" in pkg.get("id", "") else None,
                "info": pkg.get("info", {})
            }
            for pkg in pkgs
        ]

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects in the organization."""
        if not self.enabled:
            return []

        result = self._api_request(f"/org/{self.org_id}/projects")
        if not result:
            return []

        return result.get("projects", [])

    def trigger_analysis(self, branch: str = None) -> bool:
        """Trigger a new security scan."""
        if not self.enabled or not self.project_id:
            return False

        result = self._api_request(
            f"/org/{self.org_id}/project/{self.project_id}/test",
            method="POST"
        )
        return result is not None

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        if token:
            typer.echo("\n   Verifying Snyk connection...")
            temp = SnykIntegration()
            temp.token = token
            temp.enabled = True
            temp._detect_org_id()
            if temp.org_id:
                typer.secho(f"   Connected to org: {temp.org_id}", fg=typer.colors.GREEN)
                config_values["org_id"] = temp.org_id
                # List projects
                projects = temp.list_projects()
                if projects:
                    typer.echo(f"   Found {len(projects)} projects")
            else:
                typer.secho("   Failed to connect", fg=typer.colors.RED)
        return config_values