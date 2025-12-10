"""
Drone CI integration for RedGit.

Manage builds, trigger pipelines, view status and logs.
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


class DroneCIIntegration(CICDBase):
    """Drone CI integration"""

    name = "drone-ci"
    integration_type = IntegrationType.CI_CD

    # Custom notification events
    notification_events = {
        "build_triggered": {
            "description": "Drone build triggered",
            "default": True
        },
        "build_success": {
            "description": "Drone build succeeded",
            "default": True
        },
        "build_failure": {
            "description": "Drone build failed",
            "default": True
        },
        "build_promoted": {
            "description": "Drone build promoted to environment",
            "default": True
        },
    }

    def __init__(self):
        super().__init__()
        self.token = ""
        self.server = ""
        self.owner = ""
        self.repo = ""

    def setup(self, config: dict):
        """Setup Drone CI integration."""
        self.token = config.get("token") or os.getenv("DRONE_TOKEN", "")
        self.server = config.get("server") or os.getenv("DRONE_SERVER", "")
        self.owner = config.get("owner") or os.getenv("DRONE_OWNER", "")
        self.repo = config.get("repo") or os.getenv("DRONE_REPO", "")

        if not self.owner or not self.repo:
            self._detect_from_remote()

        if not self.token or not self.server:
            self.enabled = False
            return

        self.server = self.server.rstrip("/")
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
                if url.startswith("git@"):
                    # git@github.com:owner/repo.git
                    path = url.split(":")[-1].replace(".git", "")
                else:
                    # https://github.com/owner/repo.git
                    path = "/".join(url.replace(".git", "").split("/")[-2:])

                if "/" in path:
                    parts = path.split("/")
                    self.owner = self.owner or parts[0]
                    self.repo = self.repo or parts[1]
        except Exception:
            pass

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Drone API request."""
        try:
            url = f"{self.server}/api{endpoint}"
            headers = {
                "Authorization": f"Bearer {self.token}",
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
        """Map Drone status to standard status."""
        status_map = {
            "pending": "pending",
            "running": "running",
            "success": "success",
            "failure": "failed",
            "error": "failed",
            "killed": "cancelled",
            "skipped": "skipped",
            "blocked": "pending",
            "declined": "cancelled"
        }
        return status_map.get(status, status)

    def _build_to_run(self, build: dict) -> PipelineRun:
        """Convert Drone build to PipelineRun."""
        duration = None
        if build.get("started") and build.get("finished"):
            duration = build["finished"] - build["started"]

        return PipelineRun(
            id=str(build.get("number", "")),
            name=f"Build #{build.get('number', '')}",
            status=self._map_status(build.get("status", "")),
            branch=build.get("target") or build.get("ref", "").replace("refs/heads/", ""),
            commit_sha=build.get("after"),
            url=f"{self.server}/{self.owner}/{self.repo}/{build.get('number')}",
            started_at=str(build.get("started")) if build.get("started") else None,
            finished_at=str(build.get("finished")) if build.get("finished") else None,
            duration=duration,
            trigger=build.get("event")
        )

    def trigger_pipeline(
        self,
        branch: str = None,
        workflow: str = None,
        inputs: Dict[str, Any] = None
    ) -> Optional[PipelineRun]:
        """Trigger a new build."""
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

        # Drone triggers builds via POST to /repos/{owner}/{repo}/builds
        params = [f"branch={branch}"]
        if inputs:
            for key, value in inputs.items():
                params.append(f"{key}={value}")

        query = "&".join(params)
        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/builds?{query}",
            method="POST"
        )

        if result:
            return self._build_to_run(result)
        return None

    def get_pipeline_status(self, run_id: str) -> Optional[PipelineRun]:
        """Get status of a build."""
        if not self.enabled:
            return None

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/builds/{run_id}"
        )
        if result:
            return self._build_to_run(result)
        return None

    def list_pipelines(
        self,
        branch: str = None,
        status: str = None,
        limit: int = 10
    ) -> List[PipelineRun]:
        """List builds."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/builds?page=1&per_page={limit}"
        )

        if result and isinstance(result, list):
            runs = []
            for build in result:
                run = self._build_to_run(build)

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
        """Cancel a build."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/repos/{self.owner}/{self.repo}/builds/{run_id}",
                method="DELETE"
            )
            return True
        except Exception:
            return False

    def get_pipeline_jobs(self, run_id: str) -> List[PipelineJob]:
        """Get stages for a build."""
        if not self.enabled:
            return []

        result = self._api_request(
            f"/repos/{self.owner}/{self.repo}/builds/{run_id}"
        )

        if result and "stages" in result:
            jobs = []
            for stage in result["stages"]:
                duration = None
                if stage.get("started") and stage.get("stopped"):
                    duration = stage["stopped"] - stage["started"]

                jobs.append(PipelineJob(
                    id=str(stage.get("id", "")),
                    name=stage.get("name", ""),
                    status=self._map_status(stage.get("status", "")),
                    stage=stage.get("kind"),
                    started_at=str(stage.get("started")) if stage.get("started") else None,
                    finished_at=str(stage.get("stopped")) if stage.get("stopped") else None,
                    duration=duration,
                    url=None
                ))
            return jobs
        return []

    def retry_pipeline(self, run_id: str) -> Optional[PipelineRun]:
        """Restart a build."""
        if not self.enabled:
            return None

        try:
            result = self._api_request(
                f"/repos/{self.owner}/{self.repo}/builds/{run_id}",
                method="POST"
            )
            if result:
                return self._build_to_run(result)
        except Exception:
            pass
        return None

    def get_build_logs(self, run_id: str, stage: int = 1, step: int = 1) -> Optional[str]:
        """Get logs for a build step."""
        if not self.enabled:
            return None

        try:
            result = self._api_request(
                f"/repos/{self.owner}/{self.repo}/builds/{run_id}/logs/{stage}/{step}"
            )
            if result and isinstance(result, list):
                # Logs are returned as array of log lines
                return "\n".join(line.get("out", "") for line in result)
        except Exception:
            pass
        return None

    def promote_build(self, run_id: str, target: str, params: Dict[str, str] = None) -> Optional[PipelineRun]:
        """Promote a build to another environment."""
        if not self.enabled:
            return None

        try:
            query_params = [f"target={target}"]
            if params:
                for k, v in params.items():
                    query_params.append(f"{k}={v}")

            query = "&".join(query_params)
            result = self._api_request(
                f"/repos/{self.owner}/{self.repo}/builds/{run_id}/promote?{query}",
                method="POST"
            )
            if result:
                return self._build_to_run(result)
        except Exception:
            pass
        return None

    def approve_build(self, run_id: str, stage: int) -> bool:
        """Approve a blocked build stage."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/repos/{self.owner}/{self.repo}/builds/{run_id}/approve/{stage}",
                method="POST"
            )
            return True
        except Exception:
            return False

    def decline_build(self, run_id: str, stage: int) -> bool:
        """Decline a blocked build stage."""
        if not self.enabled:
            return False

        try:
            self._api_request(
                f"/repos/{self.owner}/{self.repo}/builds/{run_id}/decline/{stage}",
                method="POST"
            )
            return True
        except Exception:
            return False

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        server = config_values.get("server", "")

        if token and server:
            typer.echo("\n   Verifying Drone CI connection...")
            temp = DroneCIIntegration()
            temp.token = token
            temp.server = server.rstrip("/")
            temp.owner = config_values.get("owner", "")
            temp.repo = config_values.get("repo", "")
            temp._detect_from_remote()
            temp.enabled = True

            if temp.owner:
                config_values["owner"] = temp.owner
            if temp.repo:
                config_values["repo"] = temp.repo

            builds = temp.list_pipelines(limit=3)
            if builds:
                typer.secho(f"   Found {len(builds)} recent builds", fg=typer.colors.GREEN)
            else:
                typer.secho("   No builds found or no access", fg=typer.colors.YELLOW)
        return config_values