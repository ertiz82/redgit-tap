"""
Sentry integration for redgit.

Implements ErrorTrackingBase for Sentry API.
"""

import os
import requests
from typing import Optional, Dict, List, Any

try:
    from redgit.integrations.base import (
        ErrorTrackingBase,
        ErrorGroup,
        ErrorEvent,
        ErrorStackFrame,
        ErrorMatchResult,
        IntegrationType
    )
except ImportError:
    # Fallback for standalone usage
    from dataclasses import dataclass
    from enum import Enum

    class IntegrationType(Enum):
        ERROR_TRACKING = "error_tracking"

    @dataclass
    class ErrorStackFrame:
        filename: str
        function: str
        lineno: int
        colno: Optional[int] = None
        context_line: Optional[str] = None
        pre_context: Optional[List[str]] = None
        post_context: Optional[List[str]] = None
        in_app: bool = True
        module: Optional[str] = None
        package: Optional[str] = None

    @dataclass
    class ErrorEvent:
        id: str
        timestamp: str
        message: Optional[str] = None
        environment: Optional[str] = None
        release: Optional[str] = None
        user_id: Optional[str] = None
        user_email: Optional[str] = None
        tags: Optional[Dict[str, str]] = None
        context: Optional[Dict[str, Any]] = None
        stacktrace: Optional[List[ErrorStackFrame]] = None

    @dataclass
    class ErrorGroup:
        id: str
        title: str
        culprit: str
        level: str
        status: str
        platform: str
        first_seen: str
        last_seen: str
        count: int
        user_count: int
        filename: Optional[str] = None
        function: Optional[str] = None
        lineno: Optional[int] = None
        stacktrace: Optional[List[ErrorStackFrame]] = None
        url: Optional[str] = None
        short_id: Optional[str] = None
        affected_files: Optional[List[str]] = None
        metadata: Optional[Dict[str, Any]] = None

    @dataclass
    class ErrorMatchResult:
        error: ErrorGroup
        matched_files: List[str]
        confidence: float
        match_reason: str

    class ErrorTrackingBase:
        name = ""
        integration_type = IntegrationType.ERROR_TRACKING
        enabled = False
        error_prefix = "ERROR"
        default_environment = "production"
        min_confidence = 0.5
        auto_resolve = False
        def __init__(self): pass
        def setup(self, config): pass
        def get_recent_errors(self, limit=20, status="unresolved", environment=None): return []
        def get_error(self, error_id): return None
        def get_error_events(self, error_id, limit=10): return []
        def link_commit_to_error(self, error_id, commit_sha, repository=None): return False
        def resolve_error(self, error_id, status="resolved", resolve_in_release=None): return False


class SentryIntegration(ErrorTrackingBase):
    """Sentry integration - Error tracking and monitoring"""

    name = "sentry"
    integration_type = IntegrationType.ERROR_TRACKING
    error_prefix = "SENTRY"

    def __init__(self):
        super().__init__()
        self.auth_token = ""
        self.organization = ""
        self.project_slug = ""
        self.base_url = "https://sentry.io/api/0"
        self.default_environment = "production"
        self.min_confidence = 0.5
        self.auto_resolve = False
        self.session = None

    def setup(self, config: dict):
        """
        Setup Sentry connection.

        Config example (.redgit/config.yaml):
            integrations:
              sentry:
                organization: "my-org"
                project_slug: "my-project"
                environment: "production"  # optional, default: production
                auto_resolve: false  # optional, default: false
                min_confidence: 0.5  # optional, default: 0.5
                # API token: SENTRY_AUTH_TOKEN env variable or auth_token field
        """
        self.auth_token = config.get("auth_token") or os.getenv("SENTRY_AUTH_TOKEN")
        self.organization = config.get("organization", "")
        self.project_slug = config.get("project_slug", "")
        self.default_environment = config.get("environment", "production")
        self.min_confidence = config.get("min_confidence", 0.5)
        self.auto_resolve = config.get("auto_resolve", False)

        # Custom base URL for self-hosted Sentry
        if config.get("base_url"):
            self.base_url = config["base_url"].rstrip("/")

        # Validate required fields
        if not all([self.auth_token, self.organization, self.project_slug]):
            self.enabled = False
            return

        # Setup session
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        })

        # Test connection
        try:
            resp = self.session.get(
                f"{self.base_url}/projects/{self.organization}/{self.project_slug}/",
                timeout=10
            )
            if resp.status_code == 200:
                self.enabled = True
            else:
                self.enabled = False
        except Exception:
            self.enabled = False

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Make an authenticated request to Sentry API."""
        if not self.session:
            return None

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = self.session.request(method, url, timeout=30, **kwargs)
            return resp
        except Exception:
            return None

    def _parse_stacktrace(self, exception_data: dict) -> List[ErrorStackFrame]:
        """Parse Sentry exception data into ErrorStackFrame objects."""
        frames = []
        stacktrace = exception_data.get("stacktrace", {})
        raw_frames = stacktrace.get("frames", [])

        for frame in raw_frames:
            frames.append(ErrorStackFrame(
                filename=frame.get("filename", ""),
                function=frame.get("function", "<unknown>"),
                lineno=frame.get("lineno", 0),
                colno=frame.get("colno"),
                context_line=frame.get("context_line"),
                pre_context=frame.get("pre_context"),
                post_context=frame.get("post_context"),
                in_app=frame.get("in_app", False),
                module=frame.get("module"),
                package=frame.get("package")
            ))

        return frames

    def _extract_affected_files(self, stacktrace: List[ErrorStackFrame]) -> List[str]:
        """Extract unique affected files from stacktrace."""
        files = set()
        for frame in stacktrace:
            if frame.in_app and frame.filename:
                files.add(frame.filename)
        return list(files)

    def _parse_issue(self, data: dict) -> ErrorGroup:
        """Parse Sentry issue data into ErrorGroup object."""
        # Extract stacktrace from latest event metadata
        stacktrace = []
        affected_files = []
        filename = None
        function = None
        lineno = None

        metadata = data.get("metadata", {})
        if "exception" in metadata:
            exc_data = metadata.get("exception", {})
            if "values" in exc_data:
                # Get first exception
                first_exc = exc_data["values"][0] if exc_data["values"] else {}
                stacktrace = self._parse_stacktrace(first_exc)
                affected_files = self._extract_affected_files(stacktrace)

                # Get location info from top frame (last in list, first in stack)
                if stacktrace:
                    for frame in reversed(stacktrace):
                        if frame.in_app:
                            filename = frame.filename
                            function = frame.function
                            lineno = frame.lineno
                            break

        # Use culprit as fallback for location
        culprit = data.get("culprit", "")
        if not filename and culprit:
            # Culprit often has format: "module.submodule in function_name"
            parts = culprit.split(" in ")
            if len(parts) >= 1:
                filename = parts[0]
            if len(parts) >= 2:
                function = parts[1]

        return ErrorGroup(
            id=str(data.get("id", "")),
            title=data.get("title", ""),
            culprit=culprit,
            level=data.get("level", "error"),
            status=data.get("status", "unresolved"),
            platform=data.get("platform", ""),
            first_seen=data.get("firstSeen", ""),
            last_seen=data.get("lastSeen", ""),
            count=data.get("count", 0),
            user_count=data.get("userCount", 0),
            filename=filename,
            function=function,
            lineno=lineno,
            stacktrace=stacktrace if stacktrace else None,
            url=data.get("permalink"),
            short_id=data.get("shortId"),
            affected_files=affected_files if affected_files else None,
            metadata=metadata
        )

    def get_recent_errors(
        self,
        limit: int = 20,
        status: str = "unresolved",
        environment: str = None
    ) -> List[ErrorGroup]:
        """Get recent error groups from Sentry."""
        if not self.enabled:
            return []

        params = {
            "query": f"is:{status}",
            "limit": limit,
            "sort": "date"
        }

        if environment:
            params["environment"] = environment
        elif self.default_environment:
            params["environment"] = self.default_environment

        resp = self._make_request(
            "GET",
            f"projects/{self.organization}/{self.project_slug}/issues/",
            params=params
        )

        if not resp or resp.status_code != 200:
            return []

        errors = []
        for item in resp.json():
            errors.append(self._parse_issue(item))

        return errors

    def get_error(self, error_id: str) -> Optional[ErrorGroup]:
        """Get a specific error group by ID."""
        if not self.enabled:
            return None

        resp = self._make_request("GET", f"issues/{error_id}/")

        if not resp or resp.status_code != 200:
            return None

        return self._parse_issue(resp.json())

    def get_error_events(
        self,
        error_id: str,
        limit: int = 10
    ) -> List[ErrorEvent]:
        """Get individual events for an error group."""
        if not self.enabled:
            return []

        resp = self._make_request(
            "GET",
            f"issues/{error_id}/events/",
            params={"limit": limit}
        )

        if not resp or resp.status_code != 200:
            return []

        events = []
        for item in resp.json():
            # Parse stacktrace from event
            stacktrace = []
            entries = item.get("entries", [])
            for entry in entries:
                if entry.get("type") == "exception":
                    exc_data = entry.get("data", {})
                    if "values" in exc_data:
                        first_exc = exc_data["values"][0] if exc_data["values"] else {}
                        stacktrace = self._parse_stacktrace(first_exc)
                        break

            # Extract user info
            user_data = item.get("user", {})

            events.append(ErrorEvent(
                id=item.get("eventID", ""),
                timestamp=item.get("dateCreated", ""),
                message=item.get("message"),
                environment=item.get("environment"),
                release=item.get("release", {}).get("version") if item.get("release") else None,
                user_id=user_data.get("id"),
                user_email=user_data.get("email"),
                tags={t["key"]: t["value"] for t in item.get("tags", [])},
                context=item.get("context"),
                stacktrace=stacktrace if stacktrace else None
            ))

        return events

    def link_commit_to_error(
        self,
        error_id: str,
        commit_sha: str,
        repository: str = None
    ) -> bool:
        """Link a commit to an error group."""
        if not self.enabled:
            return False

        # Sentry doesn't have a direct API to link commits to issues.
        # Instead, we add a comment to the issue with the commit reference.
        comment_data = {
            "text": f"Linked to commit: `{commit_sha}`"
        }

        resp = self._make_request(
            "POST",
            f"issues/{error_id}/comments/",
            json=comment_data
        )

        return resp is not None and resp.status_code in (200, 201)

    def resolve_error(
        self,
        error_id: str,
        status: str = "resolved",
        resolve_in_release: str = None
    ) -> bool:
        """Resolve or change status of an error group."""
        if not self.enabled:
            return False

        # Map status to Sentry API values
        status_map = {
            "resolved": "resolved",
            "ignored": "ignored",
            "unresolved": "unresolved"
        }

        sentry_status = status_map.get(status, "resolved")

        data = {"status": sentry_status}

        if resolve_in_release and sentry_status == "resolved":
            data["statusDetails"] = {"inRelease": resolve_in_release}

        resp = self._make_request(
            "PUT",
            f"issues/{error_id}/",
            json=data
        )

        return resp is not None and resp.status_code == 200

    def get_project_stats(self) -> Dict[str, Any]:
        """Get project statistics and error counts."""
        if not self.enabled:
            return {}

        resp = self._make_request(
            "GET",
            f"projects/{self.organization}/{self.project_slug}/stats/"
        )

        if not resp or resp.status_code != 200:
            return {}

        return resp.json()

    def get_releases(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent releases for the project."""
        if not self.enabled:
            return []

        resp = self._make_request(
            "GET",
            f"projects/{self.organization}/{self.project_slug}/releases/",
            params={"limit": limit}
        )

        if not resp or resp.status_code != 200:
            return []

        return resp.json()

    def create_release(
        self,
        version: str,
        refs: List[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new release.

        Args:
            version: Release version (e.g., "1.0.0", commit SHA)
            refs: List of commit refs [{"repository": "org/repo", "commit": "sha"}]
        """
        if not self.enabled:
            return None

        data = {
            "version": version,
            "projects": [self.project_slug]
        }

        if refs:
            data["refs"] = refs

        resp = self._make_request(
            "POST",
            f"organizations/{self.organization}/releases/",
            json=data
        )

        if not resp or resp.status_code not in (200, 201):
            return None

        return resp.json()

    def associate_commits(
        self,
        version: str,
        commits: List[Dict[str, str]]
    ) -> bool:
        """
        Associate commits with a release.

        Args:
            version: Release version
            commits: List of commit info [{"id": "sha", "message": "msg", ...}]
        """
        if not self.enabled:
            return False

        resp = self._make_request(
            "POST",
            f"organizations/{self.organization}/releases/{version}/commits/",
            json=commits
        )

        return resp is not None and resp.status_code in (200, 201)

    def format_error_ref(self, error: ErrorGroup) -> str:
        """Format error reference for commit messages."""
        short_id = error.short_id or f"SENTRY-{error.id[:8]}"
        return f"Fixes: {short_id}"
