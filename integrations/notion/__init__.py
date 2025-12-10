"""
Notion integration for RedGit.

Implements TaskManagementBase for Notion API.
Uses Notion databases as task boards.
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


class NotionIntegration(TaskManagementBase):
    """Notion integration - Database-based task management"""

    name = "notion"
    integration_type = IntegrationType.TASK_MANAGEMENT

    API_URL = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"

    DEFAULT_STATUS_MAP = {
        "todo": ["To Do", "Not Started", "Backlog"],
        "in_progress": ["In Progress", "Doing", "Started"],
        "done": ["Done", "Complete", "Completed"]
    }

    def __init__(self):
        super().__init__()
        self.api_key = ""
        self.database_id = ""
        self.project_key = "NOTION"
        self.status_property = "Status"
        self.title_property = "Name"
        self.assignee_property = "Assignee"
        self.points_property = "Points"
        self.sprint_property = "Sprint"
        self.status_map = self.DEFAULT_STATUS_MAP.copy()
        self.branch_pattern = "feature/{issue_id}-{description}"
        self.commit_prefix = ""
        self._me = None

    def setup(self, config: dict):
        """Setup Notion connection."""
        self.api_key = config.get("api_key") or os.getenv("NOTION_API_KEY", "")
        self.database_id = config.get("database_id", "")
        self.project_key = config.get("project_key", "NOTION")

        # Property mappings
        self.status_property = config.get("status_property", "Status")
        self.title_property = config.get("title_property", "Name")
        self.assignee_property = config.get("assignee_property", "Assignee")
        self.points_property = config.get("points_property", "Points")
        self.sprint_property = config.get("sprint_property", "Sprint")

        if config.get("statuses"):
            for key, values in config["statuses"].items():
                if isinstance(values, list):
                    self.status_map[key] = values
                elif isinstance(values, str):
                    self.status_map[key] = [values]

        self.branch_pattern = config.get("branch_pattern", "feature/{issue_id}-{description}")
        self.commit_prefix = config.get("commit_prefix", self.project_key)

        if not self.api_key or not self.database_id:
            self.enabled = False
            return

        # Verify connection
        try:
            me = self._get_me()
            if me:
                self._me = me
                self.enabled = True
            else:
                self.enabled = False
        except Exception:
            self.enabled = False

    def _request(self, method: str, endpoint: str, data: dict = None) -> Optional[dict]:
        """Make API request to Notion."""
        if not self.api_key:
            return None

        url = f"{self.API_URL}/{endpoint}"

        try:
            body = json.dumps(data).encode("utf-8") if data else None
            req = Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Notion-Version": self.API_VERSION,
                },
                method=method
            )
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, json.JSONDecodeError):
            return None

    def _get_me(self) -> Optional[dict]:
        """Get current user info."""
        return self._request("GET", "users/me")

    def get_my_active_issues(self) -> List[Issue]:
        """Get issues assigned to current user that are active."""
        if not self.enabled:
            return []

        # Query database for active issues
        filter_data = {
            "filter": {
                "and": [
                    {
                        "property": self.status_property,
                        "status": {
                            "does_not_equal": "Done"
                        }
                    }
                ]
            },
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}]
        }

        # Add assignee filter if we have user info
        if self._me and self._me.get("id"):
            filter_data["filter"]["and"].append({
                "property": self.assignee_property,
                "people": {"contains": self._me["id"]}
            })

        data = self._request("POST", f"databases/{self.database_id}/query", filter_data)

        if not data:
            return []

        return [self._parse_page(page) for page in data.get("results", [])]

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """Get a single issue by ID."""
        if not self.enabled:
            return None

        # Issue key format: NOTION-<page_id_short>
        page_id = issue_key.replace(f"{self.project_key}-", "")

        data = self._request("GET", f"pages/{page_id}")
        if data:
            return self._parse_page(data)
        return None

    def create_issue(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        story_points: Optional[float] = None,
        assign_to_me: bool = True
    ) -> Optional[str]:
        """Create a new page in the database."""
        if not self.enabled or not self.database_id:
            return None

        properties = {
            self.title_property: {
                "title": [{"text": {"content": summary}}]
            }
        }

        # Set status to initial
        properties[self.status_property] = {
            "status": {"name": "To Do"}
        }

        # Set points if provided
        if story_points is not None and self.points_property:
            properties[self.points_property] = {"number": story_points}

        # Assign to me
        if assign_to_me and self._me and self._me.get("id"):
            properties[self.assignee_property] = {
                "people": [{"id": self._me["id"]}]
            }

        page_data = {
            "parent": {"database_id": self.database_id},
            "properties": properties
        }

        # Add description as page content
        if description:
            page_data["children"] = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": description}}]
                    }
                }
            ]

        data = self._request("POST", "pages", page_data)

        if data and data.get("id"):
            return f"{self.project_key}-{data['id'][:8]}"
        return None

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add comment to a page."""
        if not self.enabled:
            return False

        page_id = issue_key.replace(f"{self.project_key}-", "")

        comment_data = {
            "parent": {"page_id": page_id},
            "rich_text": [{"type": "text", "text": {"content": comment}}]
        }

        data = self._request("POST", "comments", comment_data)
        return data is not None

    def transition_issue(self, issue_key: str, status: str) -> bool:
        """Change page status."""
        if not self.enabled:
            return False

        page_id = issue_key.replace(f"{self.project_key}-", "")

        # Find matching status name
        target_status = status
        status_lower = status.lower().replace(" ", "_")
        if status_lower in self.status_map:
            target_status = self.status_map[status_lower][0]

        update_data = {
            "properties": {
                self.status_property: {
                    "status": {"name": target_status}
                }
            }
        }

        data = self._request("PATCH", f"pages/{page_id}", update_data)
        return data is not None

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
        return bool(self.sprint_property)

    def get_active_sprint(self) -> Optional[Sprint]:
        """Get active sprint from database property."""
        if not self.enabled or not self.sprint_property:
            return None
        # Notion doesn't have native sprints, return None
        return None

    def get_sprint_issues(self, sprint_id: str = None) -> List[Issue]:
        """Get issues in a sprint."""
        if not self.enabled or not self.sprint_property or not sprint_id:
            return []

        filter_data = {
            "filter": {
                "property": self.sprint_property,
                "select": {"equals": sprint_id}
            }
        }

        data = self._request("POST", f"databases/{self.database_id}/query", filter_data)

        if not data:
            return []

        return [self._parse_page(page) for page in data.get("results", [])]

    def add_issue_to_sprint(self, issue_key: str, sprint_id: str) -> bool:
        """Add issue to sprint."""
        if not self.enabled or not self.sprint_property:
            return False

        page_id = issue_key.replace(f"{self.project_key}-", "")

        update_data = {
            "properties": {
                self.sprint_property: {
                    "select": {"name": sprint_id}
                }
            }
        }

        data = self._request("PATCH", f"pages/{page_id}", update_data)
        return data is not None

    def get_team_members(self) -> List[Dict]:
        """Get workspace users."""
        if not self.enabled:
            return []

        data = self._request("GET", "users")
        if not data:
            return []

        return [
            {
                "id": u["id"],
                "name": u.get("name", "Unknown"),
                "email": u.get("person", {}).get("email", ""),
                "active": True
            }
            for u in data.get("results", [])
            if u.get("type") == "person"
        ]

    def assign_issue(self, issue_key: str, user_id: str) -> bool:
        """Assign page to user."""
        if not self.enabled:
            return False

        page_id = issue_key.replace(f"{self.project_key}-", "")

        update_data = {
            "properties": {
                self.assignee_property: {
                    "people": [{"id": user_id}]
                }
            }
        }

        data = self._request("PATCH", f"pages/{page_id}", update_data)
        return data is not None

    def unassign_issue(self, issue_key: str) -> bool:
        """Remove assignee from page."""
        if not self.enabled:
            return False

        page_id = issue_key.replace(f"{self.project_key}-", "")

        update_data = {
            "properties": {
                self.assignee_property: {
                    "people": []
                }
            }
        }

        data = self._request("PATCH", f"pages/{page_id}", update_data)
        return data is not None

    def get_unassigned_issues(self, max_results: int = 50) -> List[Issue]:
        """Get unassigned pages."""
        if not self.enabled:
            return []

        filter_data = {
            "filter": {
                "and": [
                    {
                        "property": self.assignee_property,
                        "people": {"is_empty": True}
                    },
                    {
                        "property": self.status_property,
                        "status": {"does_not_equal": "Done"}
                    }
                ]
            },
            "page_size": max_results
        }

        data = self._request("POST", f"databases/{self.database_id}/query", filter_data)

        if not data:
            return []

        return [self._parse_page(page) for page in data.get("results", [])]

    def search_issues(self, query: str, max_results: int = 50) -> List[Issue]:
        """Search pages by title."""
        if not self.enabled:
            return []

        filter_data = {
            "filter": {
                "property": self.title_property,
                "title": {"contains": query}
            },
            "page_size": max_results
        }

        data = self._request("POST", f"databases/{self.database_id}/query", filter_data)

        if not data:
            return []

        return [self._parse_page(page) for page in data.get("results", [])]

    def get_databases(self) -> List[Dict]:
        """Get accessible databases."""
        if not self.enabled:
            return []

        data = self._request("POST", "search", {
            "filter": {"property": "object", "value": "database"}
        })

        if not data:
            return []

        return [
            {
                "id": db["id"],
                "title": self._get_title_text(db.get("title", [])),
                "url": db.get("url", "")
            }
            for db in data.get("results", [])
        ]

    def _parse_page(self, page: dict) -> Issue:
        """Parse Notion page to Issue."""
        properties = page.get("properties", {})

        # Get title
        title_prop = properties.get(self.title_property, {})
        title = self._get_title_text(title_prop.get("title", []))

        # Get status
        status_prop = properties.get(self.status_property, {})
        status = status_prop.get("status", {}).get("name", "Unknown")

        # Get assignee
        assignee = None
        assignee_prop = properties.get(self.assignee_property, {})
        people = assignee_prop.get("people", [])
        if people:
            assignee = people[0].get("name")

        # Get points
        points = None
        points_prop = properties.get(self.points_property, {})
        if points_prop.get("number") is not None:
            points = points_prop["number"]

        page_id = page.get("id", "")

        return Issue(
            key=f"{self.project_key}-{page_id[:8]}",
            summary=title,
            description="",
            status=status,
            issue_type="task",
            assignee=assignee,
            url=page.get("url", ""),
            story_points=points,
            labels=None
        )

    def _get_title_text(self, title_array: list) -> str:
        """Extract text from title array."""
        if not title_array:
            return "Untitled"
        return "".join(t.get("plain_text", "") for t in title_array)

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

        typer.echo("\n   Verifying Notion connection...")

        temp = NotionIntegration()
        temp.api_key = api_key

        me = temp._get_me()
        if me:
            typer.secho(f"   Connected as: {me.get('name', 'Unknown')}", fg=typer.colors.GREEN)

            # List databases
            databases = temp.get_databases()
            if databases:
                typer.echo("\n   Available databases:")
                for db in databases[:5]:
                    typer.echo(f"     - {db['title']} ({db['id'][:8]}...)")
        else:
            typer.secho("   Failed to connect", fg=typer.colors.RED)

        return config_values