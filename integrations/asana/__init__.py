"""
Asana integration for RedGit.

Implements TaskManagementBase for Asana REST API.
"""

import os
import json
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from redgit.integrations.base import TaskManagementBase, Issue, Sprint, IntegrationType
except ImportError:
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


class AsanaIntegration(TaskManagementBase):
    """Asana integration - Project and task management"""

    name = "asana"
    integration_type = IntegrationType.TASK_MANAGEMENT

    # Custom notification events
    notification_events = {
        "task_created": {
            "description": "Asana task created",
            "default": True
        },
        "task_completed": {
            "description": "Asana task completed",
            "default": True
        },
        "task_transitioned": {
            "description": "Asana task moved to section",
            "default": False
        },
        "task_assigned": {
            "description": "Asana task assigned",
            "default": False
        },
        "subtask_created": {
            "description": "Asana subtask created",
            "default": False
        },
    }

    API_URL = "https://app.asana.com/api/1.0"

    DEFAULT_STATUS_MAP = {
        "todo": ["To Do", "Not Started", "Backlog"],
        "in_progress": ["In Progress", "Doing", "Working"],
        "done": ["Done", "Complete", "Completed"]
    }

    def __init__(self):
        super().__init__()
        self.api_key = ""
        self.workspace_id = ""
        self.project_id = ""
        self.project_key = "ASANA"
        self.status_map = self.DEFAULT_STATUS_MAP.copy()
        self.branch_pattern = "feature/{issue_id}-{description}"
        self.commit_prefix = ""
        self._me = None
        self._sections = {}

    def setup(self, config: dict):
        """Setup Asana connection."""
        self.api_key = config.get("api_key") or os.getenv("ASANA_API_KEY", "")
        self.workspace_id = config.get("workspace_id", "")
        self.project_id = config.get("project_id", "")
        self.project_key = config.get("project_key", "ASANA")

        if config.get("statuses"):
            for key, values in config["statuses"].items():
                if isinstance(values, list):
                    self.status_map[key] = values
                elif isinstance(values, str):
                    self.status_map[key] = [values]

        self.branch_pattern = config.get("branch_pattern", "feature/{issue_id}-{description}")
        self.commit_prefix = config.get("commit_prefix", self.project_key)

        if not self.api_key:
            self.enabled = False
            return

        try:
            me = self._get_me()
            if me:
                self._me = me
                # Auto-detect workspace if not set
                if not self.workspace_id:
                    workspaces = me.get("workspaces", [])
                    if workspaces:
                        self.workspace_id = workspaces[0]["gid"]
                self.enabled = True
                # Cache sections for status mapping
                if self.project_id:
                    self._load_sections()
            else:
                self.enabled = False
        except Exception:
            self.enabled = False

    def _request(self, method: str, endpoint: str, data: dict = None) -> Optional[dict]:
        """Make API request to Asana."""
        if not self.api_key:
            return None

        url = f"{self.API_URL}/{endpoint}"

        try:
            body = json.dumps({"data": data}).encode("utf-8") if data else None
            req = Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method=method
            )
            with urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("data")
        except (HTTPError, URLError, json.JSONDecodeError):
            return None

    def _get_me(self) -> Optional[dict]:
        """Get current user info."""
        return self._request("GET", "users/me")

    def _load_sections(self):
        """Load project sections for status mapping."""
        if not self.project_id:
            return

        sections = self._request("GET", f"projects/{self.project_id}/sections")
        if sections:
            self._sections = {s["name"]: s["gid"] for s in sections}

    def get_my_active_issues(self) -> List[Issue]:
        """Get tasks assigned to current user."""
        if not self.enabled or not self._me:
            return []

        # Get tasks assigned to me in the workspace
        params = f"assignee={self._me['gid']}&workspace={self.workspace_id}&completed_since=now"
        if self.project_id:
            params += f"&project={self.project_id}"

        data = self._request("GET", f"tasks?{params}&opt_fields=name,completed,assignee.name,memberships.section.name,notes,permalink_url,custom_fields")

        if not data:
            return []

        return [self._parse_task(task) for task in data if not task.get("completed")]

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """Get a single task by ID."""
        if not self.enabled:
            return None

        task_id = issue_key.replace(f"{self.project_key}-", "")
        data = self._request("GET", f"tasks/{task_id}?opt_fields=name,completed,assignee.name,memberships.section.name,notes,permalink_url,custom_fields")

        if data:
            return self._parse_task(data)
        return None

    def create_issue(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        story_points: Optional[float] = None,
        assign_to_me: bool = True
    ) -> Optional[str]:
        """Create a new task."""
        if not self.enabled or not self.workspace_id:
            return None

        task_data = {
            "name": summary,
            "workspace": self.workspace_id,
        }

        if description:
            task_data["notes"] = description

        if self.project_id:
            task_data["projects"] = [self.project_id]

        if assign_to_me and self._me:
            task_data["assignee"] = self._me["gid"]

        data = self._request("POST", "tasks", task_data)

        if data and data.get("gid"):
            return f"{self.project_key}-{data['gid']}"
        return None

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add comment (story) to task."""
        if not self.enabled:
            return False

        task_id = issue_key.replace(f"{self.project_key}-", "")

        data = self._request("POST", f"tasks/{task_id}/stories", {
            "text": comment
        })

        return data is not None

    def transition_issue(self, issue_key: str, status: str) -> bool:
        """Move task to a section (status)."""
        if not self.enabled or not self.project_id:
            return False

        task_id = issue_key.replace(f"{self.project_key}-", "")

        # Find section ID
        section_id = None
        status_lower = status.lower().replace(" ", "_")

        # Try exact match
        if status in self._sections:
            section_id = self._sections[status]

        # Try mapped status
        if not section_id and status_lower in self.status_map:
            for mapped_name in self.status_map[status_lower]:
                if mapped_name in self._sections:
                    section_id = self._sections[mapped_name]
                    break

        # Try partial match
        if not section_id:
            for name, gid in self._sections.items():
                if status.lower() in name.lower():
                    section_id = gid
                    break

        if not section_id:
            return False

        # Add task to section
        data = self._request("POST", f"sections/{section_id}/addTask", {
            "task": task_id
        })

        return data is not None or data == {}

    def format_branch_name(self, issue_key: str, description: str) -> str:
        """Format branch name."""
        clean_desc = description.lower()
        clean_desc = "".join(c if c.isalnum() or c == " " else "" for c in clean_desc)
        clean_desc = clean_desc.strip().replace(" ", "-")[:40]

        issue_number = issue_key.split("-")[-1] if "-" in issue_key else issue_key

        return self.branch_pattern.format(
            issue_key=issue_key,
            issue_id=issue_key,
            issue_number=issue_number,
            description=clean_desc,
            project_key=self.project_key
        )

    def get_commit_prefix(self) -> str:
        return self.commit_prefix or self.project_key

    def supports_sprints(self) -> bool:
        return False  # Asana uses projects/sections, not sprints

    def get_active_sprint(self) -> Optional[Sprint]:
        return None

    def get_sprint_issues(self, sprint_id: str = None) -> List[Issue]:
        return []

    def add_issue_to_sprint(self, issue_key: str, sprint_id: str) -> bool:
        return False

    def get_workspaces(self) -> List[Dict]:
        """Get user's workspaces."""
        if not self.enabled or not self._me:
            return []

        return [
            {"id": w["gid"], "name": w["name"]}
            for w in self._me.get("workspaces", [])
        ]

    def get_projects(self, workspace_id: str = None) -> List[Dict]:
        """Get projects in workspace."""
        if not self.enabled:
            return []

        ws = workspace_id or self.workspace_id
        if not ws:
            return []

        data = self._request("GET", f"workspaces/{ws}/projects?opt_fields=name,archived,permalink_url")

        if not data:
            return []

        return [
            {
                "id": p["gid"],
                "name": p["name"],
                "archived": p.get("archived", False),
                "url": p.get("permalink_url", "")
            }
            for p in data if not p.get("archived")
        ]

    def get_sections(self) -> List[Dict]:
        """Get sections in current project."""
        if not self.enabled or not self.project_id:
            return []

        data = self._request("GET", f"projects/{self.project_id}/sections")

        if not data:
            return []

        return [{"id": s["gid"], "name": s["name"]} for s in data]

    def get_team_members(self) -> List[Dict]:
        """Get workspace members."""
        if not self.enabled or not self.workspace_id:
            return []

        data = self._request("GET", f"workspaces/{self.workspace_id}/users?opt_fields=name,email")

        if not data:
            return []

        return [
            {
                "id": u["gid"],
                "name": u.get("name", "Unknown"),
                "email": u.get("email", ""),
                "active": True
            }
            for u in data
        ]

    def assign_issue(self, issue_key: str, user_id: str) -> bool:
        """Assign task to user."""
        if not self.enabled:
            return False

        task_id = issue_key.replace(f"{self.project_key}-", "")

        data = self._request("PUT", f"tasks/{task_id}", {
            "assignee": user_id
        })

        return data is not None

    def unassign_issue(self, issue_key: str) -> bool:
        """Remove assignee from task."""
        if not self.enabled:
            return False

        task_id = issue_key.replace(f"{self.project_key}-", "")

        data = self._request("PUT", f"tasks/{task_id}", {
            "assignee": None
        })

        return data is not None

    def get_unassigned_issues(self, max_results: int = 50) -> List[Issue]:
        """Get unassigned tasks in project."""
        if not self.enabled or not self.project_id:
            return []

        data = self._request("GET", f"projects/{self.project_id}/tasks?opt_fields=name,completed,assignee.name,memberships.section.name,notes,permalink_url&limit={max_results}")

        if not data:
            return []

        return [
            self._parse_task(task)
            for task in data
            if not task.get("completed") and not task.get("assignee")
        ]

    def search_issues(self, query: str, max_results: int = 50) -> List[Issue]:
        """Search tasks by name."""
        if not self.enabled or not self.workspace_id:
            return []

        # Asana search
        search_data = {
            "text": query,
            "resource_subtype": "default_task"
        }

        if self.project_id:
            search_data["projects.any"] = self.project_id

        data = self._request("GET", f"workspaces/{self.workspace_id}/tasks/search?text={query}&opt_fields=name,completed,assignee.name,memberships.section.name,notes,permalink_url")

        if not data:
            return []

        return [self._parse_task(task) for task in data[:max_results] if not task.get("completed")]

    def complete_task(self, issue_key: str) -> bool:
        """Mark task as complete."""
        if not self.enabled:
            return False

        task_id = issue_key.replace(f"{self.project_key}-", "")

        data = self._request("PUT", f"tasks/{task_id}", {
            "completed": True
        })

        return data is not None

    def get_subtasks(self, issue_key: str) -> List[Issue]:
        """Get subtasks of a task."""
        if not self.enabled:
            return []

        task_id = issue_key.replace(f"{self.project_key}-", "")

        data = self._request("GET", f"tasks/{task_id}/subtasks?opt_fields=name,completed,assignee.name")

        if not data:
            return []

        return [self._parse_task(task) for task in data]

    def create_subtask(self, parent_key: str, summary: str) -> Optional[str]:
        """Create a subtask."""
        if not self.enabled:
            return None

        parent_id = parent_key.replace(f"{self.project_key}-", "")

        data = self._request("POST", f"tasks/{parent_id}/subtasks", {
            "name": summary
        })

        if data and data.get("gid"):
            return f"{self.project_key}-{data['gid']}"
        return None

    def add_tag(self, issue_key: str, tag_name: str) -> bool:
        """Add tag to task."""
        if not self.enabled or not self.workspace_id:
            return False

        task_id = issue_key.replace(f"{self.project_key}-", "")

        # Find or create tag
        tags = self._request("GET", f"workspaces/{self.workspace_id}/tags")
        tag_id = None

        if tags:
            for t in tags:
                if t["name"].lower() == tag_name.lower():
                    tag_id = t["gid"]
                    break

        if not tag_id:
            # Create tag
            new_tag = self._request("POST", "tags", {
                "name": tag_name,
                "workspace": self.workspace_id
            })
            if new_tag:
                tag_id = new_tag["gid"]

        if not tag_id:
            return False

        data = self._request("POST", f"tasks/{task_id}/addTag", {
            "tag": tag_id
        })

        return data is not None or data == {}

    def _parse_task(self, task: dict) -> Issue:
        """Parse Asana task to Issue."""
        # Get status from section
        status = "To Do"
        memberships = task.get("memberships", [])
        if memberships:
            section = memberships[0].get("section", {})
            status = section.get("name", "To Do")

        assignee = None
        assignee_data = task.get("assignee")
        if assignee_data:
            assignee = assignee_data.get("name")

        task_id = task.get("gid", "")

        return Issue(
            key=f"{self.project_key}-{task_id}",
            summary=task.get("name", "Untitled"),
            description=task.get("notes", "") or "",
            status=status,
            issue_type="task",
            assignee=assignee,
            url=task.get("permalink_url", ""),
            story_points=None,
            labels=None
        )

    def on_commit(self, group: dict, context: dict):
        """Add comment after commit."""
        if not self.enabled:
            return

        issue_key = context.get("issue_key")
        if not issue_key:
            return

        comment = (
            f"Commit: {group.get('commit_title', 'N/A')}\n"
            f"Branch: {group.get('branch', 'N/A')}\n"
            f"Files: {len(group.get('files', []))} files"
        )

        self.add_comment(issue_key, comment)

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Hook after install."""
        import typer

        api_key = config_values.get("api_key", "")
        if not api_key:
            return config_values

        typer.echo("\n   Verifying Asana connection...")

        temp = AsanaIntegration()
        temp.api_key = api_key

        me = temp._get_me()
        if me:
            typer.secho(f"   Connected as: {me.get('name', 'Unknown')}", fg=typer.colors.GREEN)

            workspaces = me.get("workspaces", [])
            if workspaces:
                typer.echo("\n   Workspaces:")
                for w in workspaces:
                    typer.echo(f"     - {w['name']} ({w['gid']})")

                if not config_values.get("workspace_id"):
                    config_values["workspace_id"] = workspaces[0]["gid"]
                    typer.echo(f"\n   Auto-selected workspace: {workspaces[0]['name']}")
        else:
            typer.secho("   Failed to connect", fg=typer.colors.RED)

        return config_values