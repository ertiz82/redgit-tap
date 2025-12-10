"""
CircleCI integration for RedGit.

Manage pipelines, trigger workflows, view status and logs.
"""

import os
import json
import subprocess
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


class CircleCIIntegration(CICDBase):
    """CircleCI integration"""

    name = "circleci"
    integration_type = IntegrationType.CI_CD

    # Custom notification events
    notification_events = {
        "pipeline_triggered": {
            "description": "CircleCI pipeline triggered",
            "default": True
        },
        "pipeline_success": {
            "description": "CircleCI pipeline succeeded",
            "default": True
        },
        "pipeline_failed": {
            "description": "CircleCI pipeline failed",
            "default": True
        },
        "workflow_on_hold": {
            "description": "CircleCI workflow on hold (approval needed)",
            "default": True
        },
    }

    def __init__(self):
        super().__init__()
        self.token = ""
        self.project_slug = ""  # gh/owner/repo or bb/owner/repo
        self._api_base = "https://circleci.com/api/v2"

    def setup(self, config: dict):
        """Setup CircleCI integration."""
        self.token = config.get("token") or os.getenv("CIRCLECI_TOKEN", "")
        self.project_slug = config.get("project_slug") or os.getenv("CIRCLECI_PROJECT", "")

        if not self.project_slug:
            self._detect_from_remote()

        if not self.token:
            self.enabled = False
            return

        self.enabled = True

    def _detect_from_remote(self):
        """Detect project slug from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                vcs = "gh"  # Default to GitHub

                if "github.com" in url:
                    vcs = "gh"
                elif "bitbucket.org" in url:
                    vcs = "bb"

                if url.startswith("git@"):
                    # git@github.com:owner/repo.git
                    path = url.split(":")[-1].replace(".git", "")
                else:
                    # https://github.com/owner/repo.git
                    path = "/".join(url.replace(".git", "").split("/")[-2:])

                if path:
                    self.project_slug = f"{vcs}/{path}"
        except Exception:
            pass

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make CircleCI API request."""
        try:
            url = f"{self._api_base}{endpoint}"
            headers = {
                "Circle-Token": self.token,
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

    def _map_status(self, status: str) -> str:
        """Map CircleCI status to standard status."""
        status_map = {
            "success": "success",
            "running": "running",
            "not_run": "pending",
            "failed": "failed",
            "error": "failed",
            "failing": "failed",
            "on_hold": "pending",
            "canceled": "cancelled",
            "unauthorized": "failed",
            "queued": "pending"
        }
        return status_map.get(status, status)

    def _pipeline_to_run(self, pipeline: dict) -> PipelineRun:
        """Convert CircleCI pipeline to PipelineRun."""
        vcs = pipeline.get("vcs", {})

        return PipelineRun(
            id=pipeline.get("id", ""),
            name=pipeline.get("project_slug", "pipeline"),
            status=self._map_status(pipeline.get("state", "")),
            branch=vcs.get("branch"),
            commit_sha=vcs.get("revision"),
            url=None,  # Would need to construct from project slug
            started_at=pipeline.get("created_at"),
            finished_at=pipeline.get("updated_at"),
            duration=None,
            trigger=pipeline.get("trigger", {}).get("type")
        )

    def _workflow_to_run(self, workflow: dict) -> PipelineRun:
        """Convert CircleCI workflow to PipelineRun."""
        return PipelineRun(
            id=workflow.get("id", ""),
            name=workflow.get("name", "workflow"),
            status=self._map_status(workflow.get("status", "")),
            branch=None,
            commit_sha=None,
            url=None,
            started_at=workflow.get("created_at"),
            finished_at=workflow.get("stopped_at"),
            duration=None,
            trigger=None
        )

    def trigger_pipeline(
        self,
        branch: str = None,
        workflow: str = None,
        inputs: Dict[str, Any] = None
    ) -> Optional[PipelineRun]:
        """Trigger a new pipeline."""
        if not self.enabled:
            return None

        # Get current branch if not specified
        if not branch:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, timeout=5
                )
                branch = result.stdout.strip() if result.returncode == 0 else "main"
            except Exception:
                branch = "main"

        data = {"branch": branch}
        if inputs:
            data["parameters"] = inputs

        result = self._api_request(
            f"/project/{self.project_slug}/pipeline",
            method="POST",
            data=data
        )

        if result:
            return PipelineRun(
                id=result.get("id", ""),
                name=result.get("project_slug", "pipeline"),
                status="pending",
                branch=branch,
                commit_sha=None,
                url=None,
                started_at=result.get("created_at"),
                finished_at=None,
                duration=None,
                trigger="api"
            )
        return None

    def get_pipeline_status(self, run_id: str) -> Optional[PipelineRun]:
        """Get status of a pipeline."""
        if not self.enabled:
            return None

        result = self._api_request(f"/pipeline/{run_id}")
        if result:
            return self._pipeline_to_run(result)
        return None

    def list_pipelines(
        self,
        branch: str = None,
        status: str = None,
        limit: int = 10
    ) -> List[PipelineRun]:
        """List pipelines."""
        if not self.enabled:
            return []

        endpoint = f"/project/{self.project_slug}/pipeline"
        if branch:
            endpoint += f"?branch={branch}"

        result = self._api_request(endpoint)

        if result and "items" in result:
            runs = []
            for pipeline in result["items"][:limit * 2]:
                run = self._pipeline_to_run(pipeline)

                # Filter by status
                if status:
                    if status != run.status:
                        continue

                runs.append(run)
                if len(runs) >= limit:
                    break

            return runs
        return []

    def cancel_pipeline(self, run_id: str) -> bool:
        """Cancel a pipeline - not directly supported, cancel workflows instead."""
        if not self.enabled:
            return False

        # Get workflows for this pipeline
        workflows = self.get_pipeline_workflows(run_id)
        success = True

        for wf in workflows:
            if wf.status == "running":
                if not self.cancel_workflow(wf.id):
                    success = False

        return success

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/workflow/{workflow_id}/cancel",
                method="POST"
            )
            return True
        except Exception:
            return False

    def get_pipeline_workflows(self, pipeline_id: str) -> List[PipelineRun]:
        """Get workflows for a pipeline."""
        if not self.enabled:
            return []

        result = self._api_request(f"/pipeline/{pipeline_id}/workflow")

        if result and "items" in result:
            return [self._workflow_to_run(wf) for wf in result["items"]]
        return []

    def get_pipeline_jobs(self, run_id: str) -> List[PipelineJob]:
        """Get jobs for a workflow."""
        if not self.enabled:
            return []

        result = self._api_request(f"/workflow/{run_id}/job")

        if result and "items" in result:
            jobs = []
            for job in result["items"]:
                jobs.append(PipelineJob(
                    id=str(job.get("id", "")),
                    name=job.get("name", ""),
                    status=self._map_status(job.get("status", "")),
                    stage=None,
                    started_at=job.get("started_at"),
                    finished_at=job.get("stopped_at"),
                    duration=None,
                    url=None
                ))
            return jobs
        return []

    def rerun_workflow(self, workflow_id: str, from_failed: bool = False) -> Optional[str]:
        """Rerun a workflow."""
        if not self.enabled:
            return None

        try:
            endpoint = f"/workflow/{workflow_id}/rerun"
            data = {}
            if from_failed:
                data["from_failed"] = True

            result = self._api_request(endpoint, method="POST", data=data if data else None)
            if result:
                return result.get("workflow_id")
        except Exception:
            pass
        return None

    def approve_job(self, workflow_id: str, approval_request_id: str) -> bool:
        """Approve a job that requires approval."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/workflow/{workflow_id}/approve/{approval_request_id}",
                method="POST"
            )
            return True
        except Exception:
            return False

    def get_job_artifacts(self, job_number: str) -> List[Dict[str, Any]]:
        """Get artifacts for a job."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/project/{self.project_slug}/{job_number}/artifacts"
        )

        if result and "items" in result:
            return [
                {
                    "path": a.get("path"),
                    "url": a.get("url"),
                    "node_index": a.get("node_index")
                }
                for a in result["items"]
            ]
        return []

    def list_project_pipelines(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent pipelines with more details."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/project/{self.project_slug}/pipeline?page-token=&mine=false"
        )

        if result and "items" in result:
            pipelines = []
            for p in result["items"][:limit]:
                vcs = p.get("vcs", {})
                pipelines.append({
                    "id": p.get("id"),
                    "number": p.get("number"),
                    "state": p.get("state"),
                    "branch": vcs.get("branch"),
                    "commit": vcs.get("revision", "")[:7] if vcs.get("revision") else "",
                    "created_at": p.get("created_at"),
                    "trigger": p.get("trigger", {}).get("type")
                })
            return pipelines
        return []

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        if token:
            typer.echo("\n   Verifying CircleCI token...")
            temp = CircleCIIntegration()
            temp.token = token
            temp.project_slug = config_values.get("project_slug", "")
            temp._detect_from_remote()
            temp.enabled = True

            if temp.project_slug:
                config_values["project_slug"] = temp.project_slug
                typer.echo(f"   Project: {temp.project_slug}")

            pipelines = temp.list_pipelines(limit=3)
            if pipelines:
                typer.secho(f"   Found {len(pipelines)} recent pipelines", fg=typer.colors.GREEN)
            else:
                typer.secho("   No pipelines found or no access", fg=typer.colors.YELLOW)
        return config_values