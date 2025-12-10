"""
Travis CI integration for RedGit.

Manage builds, trigger jobs, view status and logs.
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


class TravisCIIntegration(CICDBase):
    """Travis CI integration"""

    name = "travis-ci"
    integration_type = IntegrationType.CI_CD

    # Custom notification events
    notification_events = {
        "build_triggered": {
            "description": "Travis CI build triggered",
            "default": True
        },
        "build_passed": {
            "description": "Travis CI build passed",
            "default": True
        },
        "build_failed": {
            "description": "Travis CI build failed",
            "default": True
        },
        "build_errored": {
            "description": "Travis CI build errored",
            "default": True
        },
    }

    def __init__(self):
        super().__init__()
        self.token = ""
        self.repo_slug = ""  # owner/repo
        self._api_base = "https://api.travis-ci.com"  # .com for private, .org for public

    def setup(self, config: dict):
        """Setup Travis CI integration."""
        self.token = config.get("token") or os.getenv("TRAVIS_TOKEN", "")
        self.repo_slug = config.get("repo_slug") or os.getenv("TRAVIS_REPO", "")
        endpoint = config.get("endpoint") or os.getenv("TRAVIS_ENDPOINT", "com")

        if endpoint == "org":
            self._api_base = "https://api.travis-ci.org"
        else:
            self._api_base = "https://api.travis-ci.com"

        if not self.repo_slug:
            self._detect_from_remote()

        if not self.token:
            self.enabled = False
            return

        self.enabled = True

    def _detect_from_remote(self):
        """Detect repo slug from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                if "github.com" in url:
                    if url.startswith("git@"):
                        path = url.split(":")[-1].replace(".git", "")
                    else:
                        path = "/".join(url.replace(".git", "").split("/")[-2:])
                    if path:
                        self.repo_slug = path
        except Exception:
            pass

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict = None
    ) -> Optional[dict]:
        """Make Travis CI API request."""
        try:
            url = f"{self._api_base}{endpoint}"
            headers = {
                "Authorization": f"token {self.token}",
                "Travis-API-Version": "3",
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

    def _map_status(self, state: str) -> str:
        """Map Travis state to standard status."""
        status_map = {
            "created": "pending",
            "received": "pending",
            "started": "running",
            "passed": "success",
            "failed": "failed",
            "errored": "failed",
            "canceled": "cancelled",
            "booting": "pending"
        }
        return status_map.get(state, state)

    def _build_to_run(self, build: dict) -> PipelineRun:
        """Convert Travis build to PipelineRun."""
        branch = build.get("branch", {})
        if isinstance(branch, dict):
            branch_name = branch.get("name")
        else:
            branch_name = branch

        commit = build.get("commit", {})

        return PipelineRun(
            id=str(build.get("id", "")),
            name=f"Build #{build.get('number', '')}",
            status=self._map_status(build.get("state", "")),
            branch=branch_name,
            commit_sha=commit.get("sha") if isinstance(commit, dict) else None,
            url=f"https://app.travis-ci.com/{self.repo_slug}/builds/{build.get('id')}",
            started_at=build.get("started_at"),
            finished_at=build.get("finished_at"),
            duration=build.get("duration"),
            trigger=build.get("event_type")
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

        data = {
            "request": {
                "branch": branch
            }
        }

        if inputs:
            data["request"]["config"] = {"env": inputs}

        # URL encode the repo slug
        encoded_slug = self.repo_slug.replace("/", "%2F")

        result = self._api_request(
            f"/repo/{encoded_slug}/requests",
            method="POST",
            data=data
        )

        if result and result.get("request"):
            req = result["request"]
            return PipelineRun(
                id=str(req.get("id", "")),
                name=f"Request #{req.get('id')}",
                status="pending",
                branch=branch,
                commit_sha=None,
                url=None,
                started_at=None,
                finished_at=None,
                duration=None,
                trigger="api"
            )
        return None

    def get_pipeline_status(self, run_id: str) -> Optional[PipelineRun]:
        """Get status of a build."""
        if not self.enabled:
            return None

        result = self._api_request(f"/build/{run_id}")
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

        encoded_slug = self.repo_slug.replace("/", "%2F")
        params = [f"limit={limit}"]
        if branch:
            params.append(f"branch.name={branch}")
        if status:
            travis_state = {
                "pending": "created",
                "running": "started",
                "success": "passed",
                "failed": "failed",
                "cancelled": "canceled"
            }.get(status, status)
            params.append(f"state={travis_state}")

        query = "&".join(params)
        result = self._api_request(f"/repo/{encoded_slug}/builds?{query}")

        if result and "builds" in result:
            return [self._build_to_run(b) for b in result["builds"][:limit]]
        return []

    def cancel_pipeline(self, run_id: str) -> bool:
        """Cancel a build."""
        if not self.enabled:
            return False

        try:
            self._api_request(f"/build/{run_id}/cancel", method="POST")
            return True
        except Exception:
            return False

    def get_pipeline_jobs(self, run_id: str) -> List[PipelineJob]:
        """Get jobs for a build."""
        if not self.enabled:
            return []

        result = self._api_request(f"/build/{run_id}/jobs")

        if result and "jobs" in result:
            jobs = []
            for job in result["jobs"]:
                jobs.append(PipelineJob(
                    id=str(job.get("id", "")),
                    name=job.get("number", ""),
                    status=self._map_status(job.get("state", "")),
                    stage=job.get("stage", {}).get("name") if isinstance(job.get("stage"), dict) else None,
                    started_at=job.get("started_at"),
                    finished_at=job.get("finished_at"),
                    duration=job.get("duration"),
                    url=None
                ))
            return jobs
        return []

    def retry_pipeline(self, run_id: str) -> Optional[PipelineRun]:
        """Restart a build."""
        if not self.enabled:
            return None

        try:
            result = self._api_request(f"/build/{run_id}/restart", method="POST")
            if result:
                return self._build_to_run(result)
        except Exception:
            pass
        return None

    def get_job_log(self, job_id: str) -> Optional[str]:
        """Get log for a job."""
        if not self.enabled:
            return None

        try:
            result = self._api_request(f"/job/{job_id}/log")
            if result:
                return result.get("content", "")
        except Exception:
            pass
        return None

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        token = config_values.get("token", "")
        if token:
            typer.echo("\n   Verifying Travis CI token...")
            temp = TravisCIIntegration()
            temp.token = token
            temp.repo_slug = config_values.get("repo_slug", "")
            endpoint = config_values.get("endpoint", "com")
            temp._api_base = f"https://api.travis-ci.{endpoint}"
            temp._detect_from_remote()
            temp.enabled = True

            if temp.repo_slug:
                config_values["repo_slug"] = temp.repo_slug

            builds = temp.list_pipelines(limit=3)
            if builds:
                typer.secho(f"   Found {len(builds)} recent builds", fg=typer.colors.GREEN)
            else:
                typer.secho("   No builds found or no access", fg=typer.colors.YELLOW)
        return config_values