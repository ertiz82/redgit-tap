"""
GitLab CI integration for RedGit.

Manage pipelines, trigger jobs, view status and logs.
"""

import os
import json
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import subprocess

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


class GitLabCIIntegration(CICDBase):
    """GitLab CI/CD integration"""

    name = "gitlab-ci"
    integration_type = IntegrationType.CI_CD

    # Custom notification events
    notification_events = {
        "pipeline_triggered": {
            "description": "Pipeline triggered",
            "default": True
        },
        "pipeline_success": {
            "description": "Pipeline completed successfully",
            "default": True
        },
        "pipeline_failed": {
            "description": "Pipeline failed",
            "default": True
        },
        "job_manual": {
            "description": "Manual job ready to play",
            "default": False
        },
    }

    def __init__(self):
        super().__init__()
        self.token = ""
        self.project_id = ""
        self.base_url = "https://gitlab.com"
        self._api_base = ""

    def setup(self, config: dict):
        """Setup GitLab CI integration."""
        self.token = config.get("token") or os.getenv("GITLAB_TOKEN", "")
        self.project_id = config.get("project_id") or os.getenv("GITLAB_PROJECT_ID", "")
        self.base_url = config.get("base_url") or os.getenv("GITLAB_URL", "https://gitlab.com")
        self._api_base = f"{self.base_url.rstrip('/')}/api/v4"

        if not self.project_id:
            self._detect_from_remote()

        if not self.token:
            self.enabled = False
            return

        self.enabled = True

    def _detect_from_remote(self):
        """Detect project from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                if "gitlab" in url.lower():
                    if url.startswith("git@"):
                        # git@gitlab.com:user/repo.git
                        path = url.split(":")[-1].replace(".git", "")
                    else:
                        # https://gitlab.com/user/repo.git
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        path = parsed.path.strip("/").replace(".git", "")

                    if path:
                        # URL encode the path for API calls
                        self.project_id = path.replace("/", "%2F")
        except Exception:
            pass

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make GitLab API request."""
        try:
            url = f"{self._api_base}{endpoint}"
            headers = {
                "PRIVATE-TOKEN": self.token,
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
        """Map GitLab status to standard status."""
        status_map = {
            "created": "pending",
            "waiting_for_resource": "pending",
            "preparing": "pending",
            "pending": "pending",
            "running": "running",
            "success": "success",
            "failed": "failed",
            "canceled": "cancelled",
            "skipped": "skipped",
            "manual": "pending"
        }
        return status_map.get(status, status)

    def _pipeline_to_run(self, pipeline: dict) -> PipelineRun:
        """Convert GitLab pipeline to PipelineRun."""
        return PipelineRun(
            id=str(pipeline["id"]),
            name=pipeline.get("ref", "pipeline"),
            status=self._map_status(pipeline.get("status", "")),
            branch=pipeline.get("ref"),
            commit_sha=pipeline.get("sha"),
            url=pipeline.get("web_url"),
            started_at=pipeline.get("started_at"),
            finished_at=pipeline.get("finished_at"),
            duration=pipeline.get("duration"),
            trigger=pipeline.get("source")
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

        data = {"ref": branch}
        if inputs:
            data["variables"] = [
                {"key": k, "value": str(v)} for k, v in inputs.items()
            ]

        result = self._api_request(
            f"/projects/{self.project_id}/pipeline",
            method="POST",
            data=data
        )

        if result:
            return self._pipeline_to_run(result)
        return None

    def get_pipeline_status(self, run_id: str) -> Optional[PipelineRun]:
        """Get status of a pipeline."""
        if not self.enabled:
            return None

        result = self._api_request(
            f"/projects/{self.project_id}/pipelines/{run_id}"
        )
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

        params = [f"per_page={limit}"]
        if branch:
            params.append(f"ref={branch}")
        if status:
            gitlab_status = {
                "pending": "pending",
                "running": "running",
                "success": "success",
                "failed": "failed",
                "cancelled": "canceled"
            }.get(status, status)
            params.append(f"status={gitlab_status}")

        query = "&".join(params)
        result = self._api_request(
            f"/projects/{self.project_id}/pipelines?{query}"
        )

        if result and isinstance(result, list):
            return [self._pipeline_to_run(p) for p in result[:limit]]
        return []

    def cancel_pipeline(self, run_id: str) -> bool:
        """Cancel a pipeline."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/projects/{self.project_id}/pipelines/{run_id}/cancel",
                method="POST"
            )
            return True
        except Exception:
            return False

    def get_pipeline_jobs(self, run_id: str) -> List[PipelineJob]:
        """Get jobs for a pipeline."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/projects/{self.project_id}/pipelines/{run_id}/jobs"
        )

        if result and isinstance(result, list):
            jobs = []
            for job in result:
                jobs.append(PipelineJob(
                    id=str(job["id"]),
                    name=job["name"],
                    status=self._map_status(job.get("status", "")),
                    stage=job.get("stage"),
                    started_at=job.get("started_at"),
                    finished_at=job.get("finished_at"),
                    duration=job.get("duration"),
                    url=job.get("web_url")
                ))
            return jobs
        return []

    def retry_pipeline(self, run_id: str) -> Optional[PipelineRun]:
        """Retry a failed pipeline."""
        if not self.enabled:
            return None

        try:
            result = self._api_request(
                f"/projects/{self.project_id}/pipelines/{run_id}/retry",
                method="POST"
            )
            if result:
                return self._pipeline_to_run(result)
        except Exception:
            pass
        return None

    def retry_job(self, job_id: str) -> bool:
        """Retry a specific job."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/projects/{self.project_id}/jobs/{job_id}/retry",
                method="POST"
            )
            return True
        except Exception:
            return False

    def get_job_logs(self, job_id: str) -> Optional[str]:
        """Get logs for a job."""
        if not self.enabled:
            return None

        try:
            url = f"{self._api_base}/projects/{self.project_id}/jobs/{job_id}/trace"
            headers = {"PRIVATE-TOKEN": self.token}
            req = Request(url, headers=headers)

            with urlopen(req, timeout=30) as response:
                return response.read().decode("utf-8")
        except Exception:
            return None

    def play_job(self, job_id: str) -> bool:
        """Play a manual job."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/projects/{self.project_id}/jobs/{job_id}/play",
                method="POST"
            )
            return True
        except Exception:
            return False

    def list_pipeline_schedules(self) -> List[Dict[str, Any]]:
        """List pipeline schedules."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/projects/{self.project_id}/pipeline_schedules"
        )

        if result and isinstance(result, list):
            return [
                {
                    "id": s["id"],
                    "description": s.get("description", ""),
                    "ref": s.get("ref"),
                    "cron": s.get("cron"),
                    "active": s.get("active", False),
                    "next_run_at": s.get("next_run_at")
                }
                for s in result
            ]
        return []

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        if token:
            typer.echo("\n   Verifying GitLab token...")
            temp = GitLabCIIntegration()
            temp.token = token
            temp.project_id = config_values.get("project_id", "")
            temp.base_url = config_values.get("base_url", "https://gitlab.com")
            temp._api_base = f"{temp.base_url.rstrip('/')}/api/v4"
            temp._detect_from_remote()
            temp.enabled = True

            if temp.project_id:
                config_values["project_id"] = temp.project_id

            pipelines = temp.list_pipelines(limit=3)
            if pipelines:
                typer.secho(f"   Found {len(pipelines)} recent pipelines", fg=typer.colors.GREEN)
            else:
                typer.secho("   No pipelines found or no access", fg=typer.colors.YELLOW)
        return config_values