"""
GitHub Actions integration for RedGit.

Manage workflows, trigger runs, view status and logs.
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


class GitHubActionsIntegration(CICDBase):
    """GitHub Actions CI/CD integration"""

    name = "github-actions"
    integration_type = IntegrationType.CI_CD

    # Custom notification events
    notification_events = {
        "workflow_triggered": {
            "description": "Workflow dispatch triggered",
            "default": True
        },
        "workflow_completed": {
            "description": "Workflow run completed",
            "default": True
        },
        "workflow_failed": {
            "description": "Workflow run failed",
            "default": True
        },
    }

    def __init__(self):
        super().__init__()
        self.token = ""
        self.owner = ""
        self.repo = ""
        self._api_base = "https://api.github.com"

    def setup(self, config: dict):
        """Setup GitHub Actions integration."""
        self.token = config.get("token") or os.getenv("GITHUB_TOKEN", "")
        self.owner = config.get("owner") or os.getenv("GITHUB_OWNER", "")
        self.repo = config.get("repo") or os.getenv("GITHUB_REPO", "")

        if not self.owner or not self.repo:
            self._detect_from_remote()

        if not self.token:
            self.enabled = False
            return

        self.enabled = True

    def _detect_from_remote(self):
        """Detect owner/repo from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                if "github.com" in url:
                    if url.startswith("git@"):
                        parts = url.split(":")[-1].replace(".git", "").split("/")
                    else:
                        parts = url.replace(".git", "").split("/")[-2:]
                    if len(parts) >= 2:
                        self.owner = self.owner or parts[-2]
                        self.repo = self.repo or parts[-1]
        except Exception:
            pass

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make GitHub API request."""
        try:
            url = f"{self._api_base}{endpoint}"
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

    def _map_status(self, status: str, conclusion: str = None) -> str:
        """Map GitHub status to standard status."""
        if status == "queued":
            return "pending"
        elif status == "in_progress":
            return "running"
        elif status == "completed":
            if conclusion == "success":
                return "success"
            elif conclusion == "failure":
                return "failed"
            elif conclusion == "cancelled":
                return "cancelled"
            else:
                return conclusion or "completed"
        return status

    def _run_to_pipeline(self, run: dict) -> PipelineRun:
        """Convert GitHub run to PipelineRun."""
        duration = None
        if run.get("run_started_at") and run.get("updated_at"):
            # Calculate approximate duration
            pass

        return PipelineRun(
            id=str(run["id"]),
            name=run.get("name", run.get("workflow_id", "")),
            status=self._map_status(run.get("status", ""), run.get("conclusion")),
            branch=run.get("head_branch"),
            commit_sha=run.get("head_sha"),
            url=run.get("html_url"),
            started_at=run.get("run_started_at"),
            finished_at=run.get("updated_at") if run.get("status") == "completed" else None,
            duration=duration,
            trigger=run.get("event")
        )

    def trigger_pipeline(
        self,
        branch: str = None,
        workflow: str = None,
        inputs: Dict[str, Any] = None
    ) -> Optional[PipelineRun]:
        """Trigger a workflow run."""
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

        # If workflow specified, trigger it directly
        if workflow:
            data = {"ref": branch}
            if inputs:
                data["inputs"] = inputs

            result = self._api_request(
                f"/repos/{self.owner}/{self.repo}/actions/workflows/{workflow}/dispatches",
                method="POST",
                data=data
            )
            # dispatch returns 204 on success, no body
            if result is None:
                # Get the latest run for this workflow
                runs = self.list_pipelines(branch=branch, limit=1)
                return runs[0] if runs else None

        return None

    def get_pipeline_status(self, run_id: str) -> Optional[PipelineRun]:
        """Get status of a workflow run."""
        if not self.enabled:
            return None

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}"
        )
        if result:
            return self._run_to_pipeline(result)
        return None

    def list_pipelines(
        self,
        branch: str = None,
        status: str = None,
        limit: int = 10
    ) -> List[PipelineRun]:
        """List workflow runs."""
        if not self.enabled:
            return []

        params = [f"per_page={limit}"]
        if branch:
            params.append(f"branch={branch}")
        if status:
            github_status = {
                "pending": "queued",
                "running": "in_progress",
                "success": "completed",
                "failed": "completed"
            }.get(status, status)
            params.append(f"status={github_status}")

        query = "&".join(params)
        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/actions/runs?{query}"
        )

        if result and "workflow_runs" in result:
            runs = []
            for run in result["workflow_runs"][:limit]:
                pipeline = self._run_to_pipeline(run)
                # Filter by conclusion if needed
                if status in ["success", "failed"]:
                    if status == "success" and pipeline.status != "success":
                        continue
                    if status == "failed" and pipeline.status != "failed":
                        continue
                runs.append(pipeline)
            return runs
        return []

    def cancel_pipeline(self, run_id: str) -> bool:
        """Cancel a workflow run."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/cancel",
                method="POST"
            )
            return True
        except Exception:
            return False

    def get_pipeline_jobs(self, run_id: str) -> List[PipelineJob]:
        """Get jobs for a workflow run."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/jobs"
        )

        if result and "jobs" in result:
            jobs = []
            for job in result["jobs"]:
                jobs.append(PipelineJob(
                    id=str(job["id"]),
                    name=job["name"],
                    status=self._map_status(job.get("status", ""), job.get("conclusion")),
                    started_at=job.get("started_at"),
                    finished_at=job.get("completed_at"),
                    url=job.get("html_url")
                ))
            return jobs
        return []

    def retry_pipeline(self, run_id: str) -> Optional[PipelineRun]:
        """Re-run a workflow."""
        if not self.enabled:
            return None

        try:
            self._api_request(
                f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/rerun",
                method="POST"
            )
            return self.get_pipeline_status(run_id)
        except Exception:
            return None

    def retry_failed_jobs(self, run_id: str) -> bool:
        """Re-run only failed jobs."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/rerun-failed-jobs",
                method="POST"
            )
            return True
        except Exception:
            return False

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List repository workflows."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/actions/workflows"
        )

        if result and "workflows" in result:
            return [
                {
                    "id": w["id"],
                    "name": w["name"],
                    "path": w["path"],
                    "state": w["state"]
                }
                for w in result["workflows"]
            ]
        return []

    def get_workflow_runs(self, workflow_id: str, limit: int = 10) -> List[PipelineRun]:
        """Get runs for a specific workflow."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/actions/workflows/{workflow_id}/runs?per_page={limit}"
        )

        if result and "workflow_runs" in result:
            return [self._run_to_pipeline(run) for run in result["workflow_runs"][:limit]]
        return []

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        if token:
            typer.echo("\n   Verifying GitHub token...")
            temp = GitHubActionsIntegration()
            temp.token = token
            temp.owner = config_values.get("owner", "")
            temp.repo = config_values.get("repo", "")
            temp._detect_from_remote()
            temp.enabled = True

            workflows = temp.list_workflows()
            if workflows:
                typer.secho(f"   Found {len(workflows)} workflows", fg=typer.colors.GREEN)
                for w in workflows[:3]:
                    typer.echo(f"     - {w['name']}")
            else:
                typer.secho("   No workflows found or no access", fg=typer.colors.YELLOW)
        return config_values