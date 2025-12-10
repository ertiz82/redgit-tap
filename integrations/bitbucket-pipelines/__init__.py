"""
Bitbucket Pipelines integration for RedGit.

Manage pipelines, trigger builds, view status and logs.
"""

import os
import json
import base64
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


class BitbucketPipelinesIntegration(CICDBase):
    """Bitbucket Pipelines integration"""

    name = "bitbucket-pipelines"
    integration_type = IntegrationType.CI_CD

    # Custom notification events
    notification_events = {
        "pipeline_triggered": {
            "description": "Bitbucket pipeline triggered",
            "default": True
        },
        "pipeline_successful": {
            "description": "Bitbucket pipeline successful",
            "default": True
        },
        "pipeline_failed": {
            "description": "Bitbucket pipeline failed",
            "default": True
        },
        "pipeline_stopped": {
            "description": "Bitbucket pipeline stopped",
            "default": False
        },
    }

    def __init__(self):
        super().__init__()
        self.username = ""
        self.app_password = ""
        self.workspace = ""
        self.repo_slug = ""
        self._api_base = "https://api.bitbucket.org/2.0"

    def setup(self, config: dict):
        """Setup Bitbucket Pipelines integration."""
        self.username = config.get("username") or os.getenv("BITBUCKET_USERNAME", "")
        self.app_password = config.get("app_password") or os.getenv("BITBUCKET_APP_PASSWORD", "")
        self.workspace = config.get("workspace") or os.getenv("BITBUCKET_WORKSPACE", "")
        self.repo_slug = config.get("repo_slug") or os.getenv("BITBUCKET_REPO", "")

        if not self.workspace or not self.repo_slug:
            self._detect_from_remote()

        if not self.username or not self.app_password:
            self.enabled = False
            return

        self.enabled = True

    def _detect_from_remote(self):
        """Detect workspace/repo from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                if "bitbucket.org" in url:
                    if url.startswith("git@"):
                        # git@bitbucket.org:workspace/repo.git
                        path = url.split(":")[-1].replace(".git", "")
                    else:
                        # https://bitbucket.org/workspace/repo.git
                        path = "/".join(url.replace(".git", "").split("/")[-2:])

                    if "/" in path:
                        parts = path.split("/")
                        self.workspace = self.workspace or parts[0]
                        self.repo_slug = self.repo_slug or parts[1]
        except Exception:
            pass

    def _get_auth_header(self) -> str:
        """Get basic auth header."""
        credentials = f"{self.username}:{self.app_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Bitbucket API request."""
        try:
            url = f"{self._api_base}{endpoint}"
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

    def _map_status(self, state: str, result: str = None) -> str:
        """Map Bitbucket status to standard status."""
        if state == "PENDING":
            return "pending"
        elif state == "IN_PROGRESS":
            return "running"
        elif state == "COMPLETED":
            result_map = {
                "SUCCESSFUL": "success",
                "FAILED": "failed",
                "ERROR": "failed",
                "STOPPED": "cancelled"
            }
            return result_map.get(result, "completed")
        return state.lower()

    def _pipeline_to_run(self, pipeline: dict) -> PipelineRun:
        """Convert Bitbucket pipeline to PipelineRun."""
        state = pipeline.get("state", {})
        target = pipeline.get("target", {})

        branch = None
        commit_sha = None

        if target.get("type") == "pipeline_ref_target":
            branch = target.get("ref_name")
            commit_sha = target.get("commit", {}).get("hash")
        elif target.get("type") == "pipeline_commit_target":
            commit_sha = target.get("commit", {}).get("hash")

        duration = None
        if pipeline.get("duration_in_seconds"):
            duration = pipeline["duration_in_seconds"]

        return PipelineRun(
            id=str(pipeline.get("uuid", "").strip("{}")),
            name=f"Pipeline #{pipeline.get('build_number', '')}",
            status=self._map_status(state.get("name", ""), state.get("result", {}).get("name")),
            branch=branch,
            commit_sha=commit_sha,
            url=pipeline.get("links", {}).get("html", {}).get("href"),
            started_at=pipeline.get("created_on"),
            finished_at=pipeline.get("completed_on"),
            duration=duration,
            trigger=pipeline.get("trigger", {}).get("type")
        )

    def trigger_pipeline(
        self,
        branch: str = None,
        workflow: str = None,
        inputs: Dict[str, Any] = None
    ) -> Optional[PipelineRun]:
        """Trigger a pipeline."""
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

        data = {
            "target": {
                "type": "pipeline_ref_target",
                "ref_type": "branch",
                "ref_name": branch
            }
        }

        # Add custom pipeline if specified
        if workflow:
            data["target"]["selector"] = {
                "type": "custom",
                "pattern": workflow
            }

        # Add variables if provided
        if inputs:
            data["variables"] = [
                {"key": k, "value": str(v)} for k, v in inputs.items()
            ]

        result = self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}/pipelines/",
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
            f"/repositories/{self.workspace}/{self.repo_slug}/pipelines/{{{run_id}}}"
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

        params = [f"pagelen={limit}", "sort=-created_on"]

        query = "&".join(params)
        result = self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}/pipelines/?{query}"
        )

        if result and "values" in result:
            runs = []
            for pipeline in result["values"]:
                run = self._pipeline_to_run(pipeline)

                # Filter by branch
                if branch and run.branch != branch:
                    continue

                # Filter by status
                if status and run.status != status:
                    continue

                runs.append(run)
                if len(runs) >= limit:
                    break

            return runs
        return []

    def cancel_pipeline(self, run_id: str) -> bool:
        """Stop a pipeline."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/repositories/{self.workspace}/{self.repo_slug}/pipelines/{{{run_id}}}/stopPipeline",
                method="POST"
            )
            return True
        except Exception:
            return False

    def get_pipeline_jobs(self, run_id: str) -> List[PipelineJob]:
        """Get steps for a pipeline."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repositories/{self.workspace}/{self.repo_slug}/pipelines/{{{run_id}}}/steps/"
        )

        if result and "values" in result:
            jobs = []
            for step in result["values"]:
                state = step.get("state", {})
                jobs.append(PipelineJob(
                    id=str(step.get("uuid", "").strip("{}")),
                    name=step.get("name", ""),
                    status=self._map_status(state.get("name", ""), state.get("result", {}).get("name")),
                    stage=step.get("script_commands", [{}])[0].get("name") if step.get("script_commands") else None,
                    started_at=step.get("started_on"),
                    finished_at=step.get("completed_on"),
                    duration=step.get("duration_in_seconds"),
                    url=step.get("links", {}).get("html", {}).get("href"),
                    logs_url=step.get("links", {}).get("log", {}).get("href")
                ))
            return jobs
        return []

    def get_step_log(self, run_id: str, step_id: str) -> Optional[str]:
        """Get log for a step."""
        if not self.enabled:
            return None

        try:
            url = f"{self._api_base}/repositories/{self.workspace}/{self.repo_slug}/pipelines/{{{run_id}}}/steps/{{{step_id}}}/log"
            headers = {
                "Authorization": self._get_auth_header(),
                "Accept": "application/octet-stream"
            }
            req = Request(url, headers=headers)

            with urlopen(req, timeout=30) as response:
                return response.read().decode("utf-8")
        except Exception:
            return None

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        username = config_values.get("username", "")
        app_password = config_values.get("app_password", "")

        if username and app_password:
            typer.echo("\n   Verifying Bitbucket connection...")
            temp = BitbucketPipelinesIntegration()
            temp.username = username
            temp.app_password = app_password
            temp.workspace = config_values.get("workspace", "")
            temp.repo_slug = config_values.get("repo_slug", "")
            temp._detect_from_remote()
            temp.enabled = True

            if temp.workspace:
                config_values["workspace"] = temp.workspace
            if temp.repo_slug:
                config_values["repo_slug"] = temp.repo_slug

            pipelines = temp.list_pipelines(limit=3)
            if pipelines:
                typer.secho(f"   Found {len(pipelines)} recent pipelines", fg=typer.colors.GREEN)
            else:
                typer.secho("   No pipelines found or no access", fg=typer.colors.YELLOW)
        return config_values