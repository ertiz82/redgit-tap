"""
Azure Pipelines integration for RedGit.

Manage pipelines, trigger builds, view status and logs.
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


class AzurePipelinesIntegration(CICDBase):
    """Azure Pipelines integration"""

    name = "azure-pipelines"
    integration_type = IntegrationType.CI_CD

    # Custom notification events
    notification_events = {
        "pipeline_triggered": {
            "description": "Azure pipeline triggered",
            "default": True
        },
        "pipeline_succeeded": {
            "description": "Azure pipeline succeeded",
            "default": True
        },
        "pipeline_failed": {
            "description": "Azure pipeline failed",
            "default": True
        },
        "pipeline_cancelled": {
            "description": "Azure pipeline cancelled",
            "default": False
        },
    }

    def __init__(self):
        super().__init__()
        self.token = ""
        self.organization = ""
        self.project = ""
        self._api_version = "7.1"

    def setup(self, config: dict):
        """Setup Azure Pipelines integration."""
        self.token = config.get("token") or os.getenv("AZURE_DEVOPS_TOKEN", "")
        self.organization = config.get("organization") or os.getenv("AZURE_DEVOPS_ORG", "")
        self.project = config.get("project") or os.getenv("AZURE_DEVOPS_PROJECT", "")

        if not self.token or not self.organization or not self.project:
            self.enabled = False
            return

        self.enabled = True

    @property
    def _api_base(self) -> str:
        return f"https://dev.azure.com/{self.organization}/{self.project}/_apis"

    def _get_auth_header(self) -> str:
        """Get basic auth header."""
        credentials = f":{self.token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Azure DevOps API request."""
        try:
            separator = "&" if "?" in endpoint else "?"
            url = f"{self._api_base}{endpoint}{separator}api-version={self._api_version}"
            headers = {
                "Authorization": self._get_auth_header(),
                "Content-Type": "application/json"
            }

            req_data = None
            if data:
                req_data = json.dumps(data).encode("utf-8")

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

    def _map_status(self, status: str, result: str = None) -> str:
        """Map Azure status to standard status."""
        if status == "inProgress":
            return "running"
        elif status == "notStarted":
            return "pending"
        elif status == "completed":
            result_map = {
                "succeeded": "success",
                "failed": "failed",
                "canceled": "cancelled",
                "partiallySucceeded": "success"
            }
            return result_map.get(result, "completed")
        return status

    def _run_to_pipeline(self, run: dict) -> PipelineRun:
        """Convert Azure run to PipelineRun."""
        trigger_info = run.get("triggerInfo", {})
        branch = None

        # Try to get branch from various sources
        if "sourceBranch" in run:
            branch = run["sourceBranch"].replace("refs/heads/", "")
        elif trigger_info.get("ci.sourceBranch"):
            branch = trigger_info["ci.sourceBranch"].replace("refs/heads/", "")

        return PipelineRun(
            id=str(run.get("id", "")),
            name=run.get("pipeline", {}).get("name", run.get("name", "run")),
            status=self._map_status(run.get("state", ""), run.get("result")),
            branch=branch,
            commit_sha=run.get("sourceVersion"),
            url=run.get("_links", {}).get("web", {}).get("href"),
            started_at=run.get("createdDate"),
            finished_at=run.get("finishedDate"),
            duration=None,
            trigger=run.get("reason")
        )

    def trigger_pipeline(
        self,
        branch: str = None,
        workflow: str = None,
        inputs: Dict[str, Any] = None
    ) -> Optional[PipelineRun]:
        """Trigger a pipeline run."""
        if not self.enabled:
            return None

        # Need pipeline ID to trigger
        pipeline_id = workflow
        if not pipeline_id:
            # Get first pipeline
            pipelines = self.list_workflows()
            if pipelines:
                pipeline_id = str(pipelines[0].get("id"))
            else:
                return None

        data = {}
        if branch:
            data["resources"] = {
                "repositories": {
                    "self": {
                        "refName": f"refs/heads/{branch}"
                    }
                }
            }
        if inputs:
            data["templateParameters"] = inputs

        result = self._api_request(
            f"/pipelines/{pipeline_id}/runs",
            method="POST",
            data=data if data else {}
        )

        if result:
            return self._run_to_pipeline(result)
        return None

    def get_pipeline_status(self, run_id: str) -> Optional[PipelineRun]:
        """Get status of a run."""
        if not self.enabled:
            return None

        result = self._api_request(f"/build/builds/{run_id}")
        if result:
            return self._build_to_pipeline(result)
        return None

    def _build_to_pipeline(self, build: dict) -> PipelineRun:
        """Convert build to PipelineRun."""
        branch = build.get("sourceBranch", "").replace("refs/heads/", "")

        return PipelineRun(
            id=str(build.get("id", "")),
            name=build.get("definition", {}).get("name", "build"),
            status=self._map_status(build.get("status", ""), build.get("result")),
            branch=branch,
            commit_sha=build.get("sourceVersion"),
            url=build.get("_links", {}).get("web", {}).get("href"),
            started_at=build.get("startTime"),
            finished_at=build.get("finishTime"),
            duration=None,
            trigger=build.get("reason")
        )

    def list_pipelines(
        self,
        branch: str = None,
        status: str = None,
        limit: int = 10
    ) -> List[PipelineRun]:
        """List pipeline runs (builds)."""
        if not self.enabled:
            return []

        params = [f"$top={limit}"]
        if branch:
            params.append(f"branchName=refs/heads/{branch}")
        if status:
            azure_status = {
                "running": "inProgress",
                "pending": "notStarted",
                "success": "completed",
                "failed": "completed"
            }.get(status)
            if azure_status:
                params.append(f"statusFilter={azure_status}")
            if status in ["success", "failed"]:
                result_filter = "succeeded" if status == "success" else "failed"
                params.append(f"resultFilter={result_filter}")

        query = "&".join(params)
        result = self._api_request(f"/build/builds?{query}")

        if result and "value" in result:
            return [self._build_to_pipeline(b) for b in result["value"][:limit]]
        return []

    def cancel_pipeline(self, run_id: str) -> bool:
        """Cancel a build."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/build/builds/{run_id}",
                method="PATCH",
                data={"status": "Cancelling"}
            )
            return True
        except Exception:
            return False

    def get_pipeline_jobs(self, run_id: str) -> List[PipelineJob]:
        """Get timeline (stages/jobs) for a build."""
        if not self.enabled:
            return []

        result = self._api_request(f"/build/builds/{run_id}/timeline")

        if result and "records" in result:
            jobs = []
            for record in result["records"]:
                if record.get("type") in ["Stage", "Job", "Task"]:
                    jobs.append(PipelineJob(
                        id=record.get("id", ""),
                        name=record.get("name", ""),
                        status=self._map_status(record.get("state", ""), record.get("result")),
                        stage=record.get("parentId"),
                        started_at=record.get("startTime"),
                        finished_at=record.get("finishTime"),
                        duration=None,
                        url=record.get("log", {}).get("url")
                    ))
            return jobs
        return []

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List pipeline definitions."""
        if not self.enabled:
            return []

        result = self._api_request("/pipelines")

        if result and "value" in result:
            return [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "folder": p.get("folder", ""),
                    "url": p.get("_links", {}).get("web", {}).get("href")
                }
                for p in result["value"]
            ]
        return []

    def retry_pipeline(self, run_id: str) -> Optional[PipelineRun]:
        """Retry (rebuild) a pipeline."""
        if not self.enabled:
            return None

        try:
            # Get the original build
            original = self._api_request(f"/build/builds/{run_id}")
            if not original:
                return None

            # Queue a new build
            data = {
                "definition": {"id": original["definition"]["id"]},
                "sourceBranch": original.get("sourceBranch"),
                "sourceVersion": original.get("sourceVersion")
            }

            result = self._api_request("/build/builds", method="POST", data=data)
            if result:
                return self._build_to_pipeline(result)
        except Exception:
            pass
        return None

    def get_build_logs(self, run_id: str) -> Optional[str]:
        """Get all logs for a build."""
        if not self.enabled:
            return None

        try:
            result = self._api_request(f"/build/builds/{run_id}/logs")
            if result and "value" in result:
                # Get the last log (usually the most complete)
                logs = result["value"]
                if logs:
                    last_log = logs[-1]
                    log_url = last_log.get("url")
                    if log_url:
                        req = Request(
                            f"{log_url}?api-version={self._api_version}",
                            headers={"Authorization": self._get_auth_header()}
                        )
                        with urlopen(req, timeout=30) as response:
                            return response.read().decode("utf-8")
        except Exception:
            pass
        return None

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        org = config_values.get("organization", "")
        project = config_values.get("project", "")

        if token and org and project:
            typer.echo("\n   Verifying Azure DevOps connection...")
            temp = AzurePipelinesIntegration()
            temp.token = token
            temp.organization = org
            temp.project = project
            temp.enabled = True

            pipelines = temp.list_workflows()
            if pipelines:
                typer.secho(f"   Found {len(pipelines)} pipelines", fg=typer.colors.GREEN)
                for p in pipelines[:3]:
                    typer.echo(f"     - {p['name']}")
            else:
                typer.secho("   No pipelines found or no access", fg=typer.colors.YELLOW)
        return config_values