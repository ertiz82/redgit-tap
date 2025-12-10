"""
Jenkins integration for RedGit.

Manage jobs, trigger builds, view status and logs.
"""

import os
import json
import base64
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from redgit.integrations.base import CICDBase, IntegrationType, PipelineRun, PipelineJob
except ImportError:
    from enum import Enum
    from dataclasses import dataclass

    class IntegrationType(Enum):
        CI_CD = "ci_cd"

    @dataclass
    class PipelineRun:
        id: str
        name: str
        status: str
        branch: Optional[str] = None
        commit_sha: Optional[str] = None
        url: Optional[str] = None
        started_at: Optional[str] = None
        finished_at: Optional[str] = None
        duration: Optional[int] = None
        trigger: Optional[str] = None

    @dataclass
    class PipelineJob:
        id: str
        name: str
        status: str
        stage: Optional[str] = None
        started_at: Optional[str] = None
        finished_at: Optional[str] = None
        duration: Optional[int] = None
        url: Optional[str] = None
        logs_url: Optional[str] = None

    class CICDBase:
        integration_type = IntegrationType.CI_CD
        def __init__(self):
            self.enabled = False
        def setup(self, config): pass


class JenkinsIntegration(CICDBase):
    """Jenkins CI/CD integration"""

    name = "jenkins"
    integration_type = IntegrationType.CI_CD

    # Custom notification events
    notification_events = {
        "build_triggered": {
            "description": "Jenkins build triggered",
            "default": True
        },
        "build_success": {
            "description": "Jenkins build succeeded",
            "default": True
        },
        "build_failed": {
            "description": "Jenkins build failed",
            "default": True
        },
        "build_unstable": {
            "description": "Jenkins build unstable",
            "default": True
        },
    }

    def __init__(self):
        super().__init__()
        self.url = ""
        self.username = ""
        self.token = ""
        self.job_name = ""

    def setup(self, config: dict):
        """Setup Jenkins integration."""
        self.url = config.get("url") or os.getenv("JENKINS_URL", "")
        self.username = config.get("username") or os.getenv("JENKINS_USER", "")
        self.token = config.get("token") or os.getenv("JENKINS_TOKEN", "")
        self.job_name = config.get("job_name") or os.getenv("JENKINS_JOB", "")

        if not self.url or not self.token:
            self.enabled = False
            return

        self.url = self.url.rstrip("/")
        self.enabled = True

    def _get_auth_header(self) -> str:
        """Get basic auth header."""
        credentials = f"{self.username}:{self.token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Jenkins API request."""
        try:
            url = f"{self.url}{endpoint}"
            headers = {
                "Authorization": self._get_auth_header()
            }

            req_data = None
            if data:
                from urllib.parse import urlencode
                req_data = urlencode(data).encode("utf-8")
                headers["Content-Type"] = "application/x-www-form-urlencoded"

            req = Request(url, data=req_data, headers=headers, method=method)

            with urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8")
                if content:
                    return json.loads(content)
                return {}
        except HTTPError as e:
            if e.code == 404:
                return None
            raise
        except URLError:
            return None

    def _map_status(self, result: str, building: bool = False) -> str:
        """Map Jenkins status to standard status."""
        if building:
            return "running"
        status_map = {
            "SUCCESS": "success",
            "FAILURE": "failed",
            "UNSTABLE": "failed",
            "ABORTED": "cancelled",
            "NOT_BUILT": "pending",
            None: "pending"
        }
        return status_map.get(result, "pending")

    def _build_to_run(self, build: dict, job_name: str = None) -> PipelineRun:
        """Convert Jenkins build to PipelineRun."""
        # Extract branch from parameters or actions
        branch = None
        trigger = None

        for action in build.get("actions", []):
            if action.get("_class") == "hudson.model.ParametersAction":
                for param in action.get("parameters", []):
                    if param.get("name") in ["BRANCH", "branch", "GIT_BRANCH"]:
                        branch = param.get("value")
            if action.get("_class") == "hudson.model.CauseAction":
                for cause in action.get("causes", []):
                    if "userId" in cause:
                        trigger = "manual"
                    elif "shortDescription" in cause:
                        desc = cause["shortDescription"].lower()
                        if "timer" in desc or "schedule" in desc:
                            trigger = "schedule"
                        elif "scm" in desc or "push" in desc:
                            trigger = "push"

        duration = None
        if build.get("duration"):
            duration = build["duration"] // 1000  # Convert ms to seconds

        return PipelineRun(
            id=str(build["number"]),
            name=job_name or build.get("fullDisplayName", "build"),
            status=self._map_status(build.get("result"), build.get("building", False)),
            branch=branch,
            commit_sha=None,
            url=build.get("url"),
            started_at=None,  # Jenkins uses timestamp, would need conversion
            finished_at=None,
            duration=duration,
            trigger=trigger
        )

    def trigger_pipeline(
        self,
        branch: str = None,
        workflow: str = None,
        inputs: Dict[str, Any] = None
    ) -> Optional[PipelineRun]:
        """Trigger a Jenkins build."""
        if not self.enabled:
            return None

        job = workflow or self.job_name
        if not job:
            return None

        # Build with parameters if provided
        if inputs or branch:
            params = inputs or {}
            if branch:
                params["BRANCH"] = branch

            endpoint = f"/job/{job}/buildWithParameters"
            self._api_request(endpoint, method="POST", data=params)
        else:
            endpoint = f"/job/{job}/build"
            self._api_request(endpoint, method="POST")

        # Get the latest build (queued)
        return self.get_latest_run(workflow=job)

    def get_pipeline_status(self, run_id: str) -> Optional[PipelineRun]:
        """Get status of a build."""
        if not self.enabled:
            return None

        job = self.job_name
        if not job:
            return None

        result = self._api_request(
            f"/job/{job}/{run_id}/api/json"
        )
        if result:
            return self._build_to_run(result, job)
        return None

    def list_pipelines(
        self,
        branch: str = None,
        status: str = None,
        limit: int = 10
    ) -> List[PipelineRun]:
        """List recent builds."""
        if not self.enabled:
            return []

        job = self.job_name
        if not job:
            return []

        result = self._api_request(
            f"/job/{job}/api/json?tree=builds[number,result,building,duration,url,actions[parameters[name,value],causes[shortDescription,userId]]]"
        )

        if result and "builds" in result:
            runs = []
            for build in result["builds"][:limit * 2]:  # Get more to filter
                run = self._build_to_run(build, job)

                # Filter by status
                if status:
                    if status == "running" and run.status != "running":
                        continue
                    if status == "success" and run.status != "success":
                        continue
                    if status == "failed" and run.status != "failed":
                        continue

                # Filter by branch (if available)
                if branch and run.branch and run.branch != branch:
                    continue

                runs.append(run)
                if len(runs) >= limit:
                    break

            return runs
        return []

    def cancel_pipeline(self, run_id: str) -> bool:
        """Cancel/stop a build."""
        if not self.enabled:
            return False

        job = self.job_name
        if not job:
            return False

        try:
            self._api_request(
                f"/job/{job}/{run_id}/stop",
                method="POST"
            )
            return True
        except Exception:
            return False

    def get_pipeline_logs(self, run_id: str, job_id: str = None) -> Optional[str]:
        """Get build console output."""
        if not self.enabled:
            return None

        job = self.job_name
        if not job:
            return None

        try:
            url = f"{self.url}/job/{job}/{run_id}/consoleText"
            headers = {"Authorization": self._get_auth_header()}
            req = Request(url, headers=headers)

            with urlopen(req, timeout=30) as response:
                return response.read().decode("utf-8")
        except Exception:
            return None

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List available jobs."""
        if not self.enabled:
            return []

        result = self._api_request(
            "/api/json?tree=jobs[name,url,color,lastBuild[number,result]]"
        )

        if result and "jobs" in result:
            return [
                {
                    "name": j["name"],
                    "url": j.get("url"),
                    "status": self._color_to_status(j.get("color", "")),
                    "last_build": j.get("lastBuild", {}).get("number")
                }
                for j in result["jobs"]
            ]
        return []

    def _color_to_status(self, color: str) -> str:
        """Convert Jenkins color to status."""
        if "_anime" in color:
            return "running"
        color_map = {
            "blue": "success",
            "red": "failed",
            "yellow": "unstable",
            "grey": "pending",
            "disabled": "disabled",
            "aborted": "cancelled",
            "notbuilt": "pending"
        }
        return color_map.get(color.replace("_anime", ""), "unknown")

    def get_build_info(self, job_name: str, build_number: str) -> Optional[Dict[str, Any]]:
        """Get detailed build info."""
        if not self.enabled:
            return None

        result = self._api_request(
            f"/job/{job_name}/{build_number}/api/json"
        )
        return result

    def get_queue(self) -> List[Dict[str, Any]]:
        """Get build queue."""
        if not self.enabled:
            return []

        result = self._api_request("/queue/api/json")

        if result and "items" in result:
            return [
                {
                    "id": item["id"],
                    "task": item.get("task", {}).get("name"),
                    "why": item.get("why"),
                    "stuck": item.get("stuck", False)
                }
                for item in result["items"]
            ]
        return []

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        url = config_values.get("url", "")
        token = config_values.get("token", "")
        if url and token:
            typer.echo("\n   Verifying Jenkins connection...")
            temp = JenkinsIntegration()
            temp.url = url.rstrip("/")
            temp.username = config_values.get("username", "")
            temp.token = token
            temp.enabled = True

            jobs = temp.list_jobs()
            if jobs:
                typer.secho(f"   Found {len(jobs)} jobs", fg=typer.colors.GREEN)
                for j in jobs[:3]:
                    typer.echo(f"     - {j['name']} [{j['status']}]")
            else:
                typer.secho("   No jobs found or no access", fg=typer.colors.YELLOW)
        return config_values