
"""
ClickUp integration for RedGit.

Implements TaskManagementBase for ClickUp REST API.
ClickUp is a flexible project management tool with tasks, lists, and spaces.
"""

import os
import json
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

# Import from redgit core
try:
    from redgit.integrations.base import TaskManagementBase, Issue, Sprint, IntegrationType
except ImportError:
    # For standalone testing
    from enum import Enum

    class IntegrationType(Enum):
        TASK_MANAGEMENT = "task_management"

    class Issue:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class Sprint:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class TaskManagementBase:
        integration_type = IntegrationType.TASK_MANAGEMENT
        def __init__(self):
            self.enabled = False
        def setup(self, config): pass


class ClickUpIntegration(TaskManagementBase):
    """ClickUp integration - Flexible project management with tasks and lists"""

    name = "clickup"
    integration_type = IntegrationType.TASK_MANAGEMENT

    notification_events = {
        "task_created": {
            "description": "ClickUp task created",
            "default": True
        },
        "task_completed": {
            "description": "ClickUp task completed",
            "default": True
        },
        "task_transitioned": {
            "description": "ClickUp task status changed",
            "default": False
        },
    }

    API_BASE = "https://api.clickup.com/api/v2"

    DEFAULT_STATUS_MAP = {
        "todo": ["to do", "open", "backlog"],
        "in_progress": ["in progress", "in review", "active"],
        "done": ["complete", "closed", "done"]
    }

    def __init__(self):
        super().__init__()
        self.api_token = ""
        self.team_id = ""
        self.list_id = ""
        self.project_key = ""
        self.branch_pattern = "feature/CU-{issue_key}-{description}"
        self.issue_language = "en"
        self.commit_prefix = ""
        self.status_map = self.DEFAULT_STATUS_MAP.copy()
        self._me = None

    def setup(self, config: dict):
        """Setup ClickUp connection."""
        self.api_token = config.get("api_token") or os.getenv("CLICKUP_API_TOKEN", "")
        self.team_id = config.get("team_id", "")
        self.list_id = config.get("list_id", "")
        self.project_key = config.get("project_key", "")
        self.branch_pattern = config.get("branch_pattern", "feature/CU-{issue_key}-{description}")
        self.issue_language = config.get("issue_language", "en")
        self.commit_prefix = config.get("commit_prefix", "")

        if config.get("statuses"):
            for key, values in config["statuses"].items():
                if isinstance(values, list):
                    self.status_map[key] = values
                elif isinstance(values, str):
                    self.status_map[key] = [values]

        if not self.api_token:
            self.enabled = False
            return

        try:
            me = self._get_me()
            if me:
                self._me = me
                self.enabled = True
            else:
                self.enabled = False
        except Exception:
            self.enabled = False

    def _request(self, method: str, path: str, data: dict = None, params: dict = None) -> Optional[dict]:
        """Make an API request to ClickUp."""
        if not self.api_token:
            return None

        url = f"{self.API_BASE}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"

        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")

        try:
            req = Request(
                url,
                data=body,
                headers={
                    "Authorization": self.api_token,
                    "Content-Type": "application/json",
                },
                method=method
            )
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError):
            return None
        except json.JSONDecodeError:
            return None

    def _get_me(self) -> Optional[dict]:
        """Get current user info."""
        data = self._request("GET", "/user")
        return data.get("user") if data else None

    def get_current_user(self) -> Optional[dict]:
        """Get current user."""
        if self._me:
            return {
                "id": str(self._me.get("id", "")),
                "name": self._me.get("username") or self._me.get("email", ""),
                "email": self._me.get("email", "")
            }
        return None

    def get_workspaces(self) -> List[dict]:
        """Get all workspaces (teams)."""
        data = self._request("GET", "/team")
        if not data:
            return []
        return [
            {
                "id": str(t.get("id", "")),
                "name": t.get("name", "")
            }
            for t in data.get("teams", [])
        ]

    def get_spaces(self, team_id: str = None) -> List[dict]:
        """Get all spaces in a workspace."""
        tid = team_id or self.team_id
        if not tid:
            return []
        data = self._request("GET", f"/team/{tid}/space", params={"archived": "false"})
        if not data:
            return []
        return [
            {
                "id": str(s.get("id", "")),
                "name": s.get("name", "")
            }
            for s in data.get("spaces", [])
        ]

    def get_lists(self, space_id: str) -> List[dict]:
        """Get all lists in a space (direct lists, not in folders)."""
        data = self._request("GET", f"/space/{space_id}/list", params={"archived": "false"})
        if not data:
            return []
        return [
            {
                "id": str(l.get("id", "")),
                "name": l.get("name", "")
            }
            for l in data.get("lists", [])
        ]

    # ==================== TaskManagementBase Implementation ====================

    def get_my_active_issues(self) -> List[Issue]:
        """Get tasks assigned to current user that are not done."""
        if not self.enabled or not self._me:
            return []

        user_id = str(self._me.get("id", ""))
        if not user_id:
            return []

        params = {
            "assignees[]": [user_id],
            "include_closed": "false",
            "subtasks": "false",
            "page": "0",
            "order_by": "updated",
            "reverse": "true"
        }

        data = self._request("GET", f"/team/{self.team_id}/task", params=params)
        if not data:
            return []

        tasks = data.get("tasks", [])
        issues = []
        for task in tasks:
            status = task.get("status", {}).get("status", "").lower()
            # Skip done/closed tasks
            done_statuses = self.status_map.get("done", ["complete", "closed", "done"])
            if any(status == s.lower() for s in done_statuses):
                continue
            issues.append(self._parse_task(task))

        return issues

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """Get a single task by ID."""
        if not self.enabled:
            return None

        data = self._request("GET", f"/task/{issue_key}")
        if not data or "err" in data:
            return None

        return self._parse_task(data)

    def create_issue(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        story_points: Optional[float] = None,
        parent_key: Optional[str] = None
    ) -> Optional[str]:
        """Create a new task in the configured list."""
        if not self.enabled or not self.list_id:
            return None

        payload: Dict[str, Any] = {
            "name": summary,
        }

        if description:
            payload["description"] = description

        if self._me:
            payload["assignees"] = [int(self._me["id"])]

        if story_points is not None:
            payload["time_estimate"] = int(story_points * 3600 * 1000)  # ms

        if parent_key:
            payload["parent"] = parent_key

        data = self._request("POST", f"/list/{self.list_id}/task", data=payload)

        if data and data.get("id"):
            return data["id"]

        return None

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add a comment to a task."""
        if not self.enabled:
            return False

        data = self._request(
            "POST",
            f"/task/{issue_key}/comment",
            data={"comment_text": comment}
        )

        return data is not None and "id" in data

    def transition_issue(self, issue_key: str, status: str) -> bool:
        """Change task status."""
        if not self.enabled:
            return False

        data = self._request(
            "PUT",
            f"/task/{issue_key}",
            data={"status": status.lower()}
        )

        return data is not None and "id" in data

    def format_branch_name(self, issue_key: str, description: str) -> str:
        """Format branch name using the configured pattern."""
        clean_desc = description.lower()
        clean_desc = "".join(c if c.isalnum() or c == " " else "" for c in clean_desc)
        clean_desc = clean_desc.strip().replace(" ", "-")[:40]

        return self.branch_pattern.format(
            issue_key=issue_key,
            description=clean_desc,
        )

    def get_commit_prefix(self) -> str:
        """Get prefix for commit messages."""
        return self.commit_prefix or self.project_key or "CU"

    # ==================== Additional Methods ====================

    def get_team_members(self, project_key: str = None) -> List[dict]:
        """Get workspace members."""
        if not self.enabled or not self.team_id:
            return []

        data = self._request("GET", f"/team/{self.team_id}/member")
        if not data:
            return []

        return [
            {
                "id": str(m.get("user", {}).get("id", "")),
                "name": m.get("user", {}).get("username", "") or m.get("user", {}).get("email", ""),
                "email": m.get("user", {}).get("email", "")
            }
            for m in data.get("members", [])
        ]

    def assign_issue(self, issue_key: str, account_id: str) -> bool:
        """Assign a task to a user."""
        if not self.enabled:
            return False

        data = self._request(
            "POST",
            f"/task/{issue_key}/assignee",
            data={"assignee": int(account_id)}
        )

        return data is not None

    def get_statuses(self, list_id: str = None) -> List[dict]:
        """Get available statuses for a list."""
        lid = list_id or self.list_id
        if not lid:
            return []

        data = self._request("GET", f"/list/{lid}")
        if not data:
            return []

        return [
            {
                "status": s.get("status", ""),
                "type": s.get("type", ""),
                "color": s.get("color", "")
            }
            for s in data.get("statuses", [])
        ]

    def search_tasks(self, query: str, list_id: str = None) -> List[Issue]:
        """Search tasks by text in a list."""
        if not self.enabled:
            return []

        lid = list_id or self.list_id
        if not lid:
            return []

        data = self._request(
            "GET",
            f"/list/{lid}/task",
            params={
                "include_closed": "false",
                "page": "0",
            }
        )

        if not data:
            return []

        tasks = data.get("tasks", [])
        query_lower = query.lower()
        return [
            self._parse_task(t) for t in tasks
            if query_lower in t.get("name", "").lower()
            or query_lower in (t.get("description") or "").lower()
        ]

    def get_list_tasks(self, list_id: str = None, include_closed: bool = False) -> List[Issue]:
        """Get all tasks in a list."""
        if not self.enabled:
            return []

        lid = list_id or self.list_id
        if not lid:
            return []

        data = self._request(
            "GET",
            f"/list/{lid}/task",
            params={
                "include_closed": "true" if include_closed else "false",
                "page": "0",
                "order_by": "updated",
                "reverse": "true"
            }
        )

        if not data:
            return []

        return [self._parse_task(t) for t in data.get("tasks", [])]

    def on_commit(self, group: dict, context: dict):
        """Add comment to ClickUp task after commit."""
        if not self.enabled:
            return

        issue_key = context.get("issue_key")
        if not issue_key:
            return

        comment = (
            f"**Commit:** {group.get('commit_title', 'N/A')}\n"
            f"**Branch:** {group.get('branch', 'N/A')}\n"
            f"**Files:** {len(group.get('files', []))} files"
        )

        self.add_comment(issue_key, comment)

    def _parse_task(self, data: dict) -> Issue:
        """Parse ClickUp API task response to Issue object."""
        assignees = data.get("assignees", [])
        assignee = assignees[0].get("username") if assignees else None

        status = data.get("status", {})
        status_name = status.get("status", "Unknown")

        labels = [t.get("name", "") for t in data.get("tags", [])]

        sprint = None
        list_info = data.get("list")
        if list_info:
            sprint = list_info.get("name")

        story_points = None
        for cf in data.get("custom_fields", []):
            if "point" in cf.get("name", "").lower() or "story" in cf.get("name", "").lower():
                val = cf.get("value")
                if val is not None:
                    try:
                        story_points = float(val)
                    except (TypeError, ValueError):
                        pass
                break

        return Issue(
            key=data.get("id", ""),
            summary=data.get("name", ""),
            description=data.get("description", "") or "",
            status=status_name,
            issue_type="task",
            assignee=assignee,
            url=data.get("url", ""),
            sprint=sprint,
            story_points=story_points,
            labels=labels if labels else None
        )

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Hook called after ClickUp integration install."""
        import typer

        api_token = config_values.get("api_token", "")

        if not api_token:
            return config_values

        typer.echo("\n   Verifying ClickUp connection...")

        temp = ClickUpIntegration()
        temp.api_token = api_token

        me = temp._get_me()
        if me:
            typer.secho(f"   Logged in as: {me.get('username', 'Unknown')}", fg=typer.colors.GREEN)

            team_id = config_values.get("team_id", "")
            if not team_id:
                workspaces = temp.get_workspaces()
                if len(workspaces) == 1:
                    config_values["team_id"] = workspaces[0]["id"]
                    typer.secho(f"   Auto-selected workspace: {workspaces[0]['name']}", fg=typer.colors.GREEN)
                elif workspaces:
                    typer.echo("\n   Available workspaces:")
                    for i, ws in enumerate(workspaces, 1):
                        typer.echo(f"     [{i}] {ws['name']} (ID: {ws['id']})")
        else:
            typer.secho("   Failed to verify API token", fg=typer.colors.RED)

        return config_values