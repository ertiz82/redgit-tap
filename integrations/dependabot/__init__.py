"""
Dependabot integration for RedGit.

Automated dependency updates via GitHub's Dependabot.
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


class DependabotIntegration(CodeQualityBase):
    """GitHub Dependabot integration for dependency updates"""

    name = "dependabot"
    integration_type = IntegrationType.CODE_QUALITY

    # Custom notification events
    notification_events = {
        "security_alert": {
            "description": "Dependabot security alert created",
            "default": True
        },
        "pr_created": {
            "description": "Dependabot PR created",
            "default": True
        },
        "pr_merged": {
            "description": "Dependabot PR merged",
            "default": False
        },
        "update_available": {
            "description": "Dependency update available",
            "default": False
        },
    }

    API_URL = "https://api.github.com"

    def __init__(self):
        super().__init__()
        self.token = ""
        self.owner = ""
        self.repo = ""

    def setup(self, config: dict):
        """Setup Dependabot integration."""
        self.token = config.get("token") or os.getenv("GITHUB_TOKEN", "")
        self.owner = config.get("owner") or os.getenv("GITHUB_OWNER", "")
        self.repo = config.get("repo") or os.getenv("GITHUB_REPO", "")

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
        """Get Dependabot alert status."""
        if not self.enabled:
            return None

        alerts = self._api_request(
            f"/repos/{self.owner}/{self.repo}/dependabot/alerts?state=open"
        )

        if alerts is None:
            return None

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for alert in alerts:
            sev = alert.get("security_vulnerability", {}).get("severity", "").lower()
            if sev in severity_counts:
                severity_counts[sev] += 1

        total = len(alerts)
        status = "passed"
        if severity_counts["critical"] > 0:
            status = "failed"
        elif severity_counts["high"] > 0:
            status = "warning"
        elif total > 0:
            status = "warning"

        return QualityReport(
            id=f"{self.owner}/{self.repo}",
            status=status,
            url=f"https://github.com/{self.owner}/{self.repo}/security/dependabot",
            vulnerabilities=total,
            quality_gate_status=status,
            quality_gate_details=severity_counts
        )

    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """Get Dependabot metrics."""
        if not self.enabled:
            return None

        # Get open alerts
        alerts = self._api_request(
            f"/repos/{self.owner}/{self.repo}/dependabot/alerts?state=open"
        ) or []

        # Get Dependabot PRs
        prs = self._api_request(
            f"/repos/{self.owner}/{self.repo}/pulls?state=open"
        ) or []
        dependabot_prs = [p for p in prs if p.get("user", {}).get("login") == "dependabot[bot]"]

        return {
            "open_alerts": len(alerts),
            "open_prs": len(dependabot_prs),
            "url": f"https://github.com/{self.owner}/{self.repo}/security/dependabot"
        }

    def get_security_issues(
        self,
        severity: str = None,
        limit: int = 50
    ) -> List[SecurityIssue]:
        """Get Dependabot security alerts."""
        if not self.enabled:
            return []

        params = "state=open"
        if severity:
            params += f"&severity={severity.lower()}"

        alerts = self._api_request(
            f"/repos/{self.owner}/{self.repo}/dependabot/alerts?{params}"
        )

        if not alerts:
            return []

        issues = []
        for alert in alerts[:limit]:
            vuln = alert.get("security_vulnerability", {})
            advisory = alert.get("security_advisory", {})
            pkg = alert.get("dependency", {}).get("package", {})

            issues.append(SecurityIssue(
                id=str(alert.get("number", "")),
                severity=vuln.get("severity", "").lower(),
                title=advisory.get("summary", ""),
                description=advisory.get("description"),
                package=pkg.get("name"),
                version=alert.get("dependency", {}).get("manifest_path"),
                fixed_in=vuln.get("first_patched_version", {}).get("identifier"),
                cve=advisory.get("cve_id"),
                cwe=",".join([cwe.get("cwe_id", "") for cwe in advisory.get("cwes", [])]),
                url=alert.get("html_url")
            ))

        return issues

    def get_outdated_dependencies(self) -> List[Dict[str, Any]]:
        """Get outdated dependencies from Dependabot PRs."""
        if not self.enabled:
            return []

        prs = self._api_request(
            f"/repos/{self.owner}/{self.repo}/pulls?state=open"
        ) or []

        outdated = []
        for pr in prs:
            if pr.get("user", {}).get("login") == "dependabot[bot]":
                outdated.append({
                    "pr_number": pr.get("number"),
                    "title": pr.get("title"),
                    "url": pr.get("html_url"),
                    "created_at": pr.get("created_at"),
                    "labels": [l.get("name") for l in pr.get("labels", [])]
                })

        return outdated

    def list_alerts(self, state: str = "open") -> List[Dict[str, Any]]:
        """List all Dependabot alerts."""
        if not self.enabled:
            return []

        alerts = self._api_request(
            f"/repos/{self.owner}/{self.repo}/dependabot/alerts?state={state}"
        )
        return alerts or []

    def dismiss_alert(self, alert_number: int, reason: str = "tolerable_risk") -> bool:
        """Dismiss a Dependabot alert."""
        if not self.enabled:
            return False

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/dependabot/alerts/{alert_number}",
            method="PATCH",
            data={"state": "dismissed", "dismissed_reason": reason}
        )
        return result is not None

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        owner = config_values.get("owner", "")
        repo = config_values.get("repo", "")
        if token and owner and repo:
            typer.echo("\n   Verifying Dependabot access...")
            temp = DependabotIntegration()
            temp.token = token
            temp.owner = owner
            temp.repo = repo
            temp.enabled = True
            metrics = temp.get_project_metrics()
            if metrics:
                typer.secho(f"   Connected! Open alerts: {metrics.get('open_alerts', 0)}", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to access Dependabot", fg=typer.colors.RED)
        return config_values