"""
Trello integration for RedGit.

Implements TaskManagementBase for Trello REST API.
"""

import os
import json
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

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


class TrelloIntegration(TaskManagementBase):
    """Trello integration - Kanban board task management"""

    name = "trello"
    integration_type = IntegrationType.TASK_MANAGEMENT

    API_URL = "https://api.trello.com/1"

    DEFAULT_STATUS_MAP = {
        "todo": ["To Do", "Backlog", "Ideas"],
        "in_progress": ["In Progress", "Doing", "Working"],
        "done": ["Done", "Complete", "Completed"]
    }

    def __init__(self):
        super().__init__()
        self.api_key = ""
        self.token = ""
        self.board_id = ""
        self.project_key = "TRELLO"
        self.status_map = self.DEFAULT_STATUS_MAP.copy()
        self.branch_pattern = "feature/{issue_id}-{description}"
        self.commit_prefix = ""
        self._me = None
        self._lists = {}

    def setup(self, config: dict):
        """Setup Trello connection."""
        self.api_key = config.get("api_key") or os.getenv("TRELLO_API_KEY", "")
        self.token = config.get("token") or os.getenv("TRELLO_TOKEN", "")
        self.board_id = config.get("board_id", "")
        self.project_key = config.get("project_key", "TRELLO")

        if config.get("statuses"):
            for key, values in config["statuses"].items():
                if isinstance(values, list):
                    self.status_map[key] = values
                elif isinstance(values, str):
                    self.status_map[key] = [values]

        self.branch_pattern = config.get("branch_pattern", "feature/{issue_id}-{description}")
        self.commit_prefix = config.get("commit_prefix", self.project_key)

        if not self.api_key or not self.token:
            self.enabled = False
            return

        try:
            me = self._get_me()
            if me:
                self._me = me
                self.enabled = True
                # Cache lists for status mapping
                if self.board_id:
                    self._load_lists()
            else:
                self.enabled = False
        except Exception:
            self.enabled = False

    def _request(self, method: str, endpoint: str, params: dict = None, data: dict = None) -> Optional[Any]:
        """Make API request to Trello."""
        if not self.api_key or not self.token:
            return None

        # Add auth params
        auth_params = {"key": self.api_key, "token": self.token}
        if params:
            auth_params.update(params)

        url = f"{self.API_URL}/{endpoint}"
        if auth_params:
            url += "?" + urlencode(auth_params)

        try:
            body = json.dumps(data).encode("utf-8") if data and method in ["POST", "PUT"] else None
            headers = {"Content-Type": "application/json"} if body else {}

            req = Request(url, data=body, headers=headers, method=method)
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, json.JSONDecodeError):
            return None

    def _get_me(self) -> Optional[dict]:
        """Get current user info."""
        return self._request("GET", "members/me")

    def _load_lists(self):
        """Load board lists for status mapping."""
        if not self.board_id:
            return

        lists = self._request("GET", f"boards/{self.board_id}/lists")
        if lists:
            self._lists = {l["name"]: l["id"] for l in lists}

    def get_my_active_issues(self) -> List[Issue]:
        """Get cards assigned to current user."""
        if not self.enabled or not self._me:
            return []

        # Get cards assigned to me on the board
        cards = self._request("GET", f"boards/{self.board_id}/cards", {
            "filter": "open",
            "members": "true",
            "member_fields": "fullName",
            "list": "true"
        })

        if not cards:
            return []

        my_id = self._me.get("id")
        return [
            self._parse_card(card)
            for card in cards
            if my_id in card.get("idMembers", [])
        ]

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """Get a single card by ID."""
        if not self.enabled:
            return None

        card_id = issue_key.replace(f"{self.project_key}-", "")
        card = self._request("GET", f"cards/{card_id}", {
            "members": "true",
            "member_fields": "fullName",
            "list": "true"
        })

        if card:
            return self._parse_card(card)
        return None

    def create_issue(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        story_points: Optional[float] = None,
        assign_to_me: bool = True
    ) -> Optional[str]:
        """Create a new card."""
        if not self.enabled or not self.board_id:
            return None

        # Find first list (usually To Do/Backlog)
        if not self._lists:
            self._load_lists()

        list_id = None
        for name, lid in self._lists.items():
            if any(s.lower() in name.lower() for s in ["to do", "backlog", "todo"]):
                list_id = lid
                break

        if not list_id and self._lists:
            list_id = list(self._lists.values())[0]

        if not list_id:
            return None

        card_data = {
            "name": summary,
            "idList": list_id,
        }

        if description:
            card_data["desc"] = description

        if assign_to_me and self._me:
            card_data["idMembers"] = self._me["id"]

        card = self._request("POST", "cards", card_data)

        if card and card.get("id"):
            return f"{self.project_key}-{card['id']}"
        return None

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add comment to card."""
        if not self.enabled:
            return False

        card_id = issue_key.replace(f"{self.project_key}-", "")

        result = self._request("POST", f"cards/{card_id}/actions/comments", {
            "text": comment
        })

        return result is not None

    def transition_issue(self, issue_key: str, status: str) -> bool:
        """Move card to a list (status)."""
        if not self.enabled:
            return False

        card_id = issue_key.replace(f"{self.project_key}-", "")

        if not self._lists:
            self._load_lists()

        # Find list ID
        list_id = None
        status_lower = status.lower().replace(" ", "_")

        # Try exact match
        if status in self._lists:
            list_id = self._lists[status]

        # Try mapped status
        if not list_id and status_lower in self.status_map:
            for mapped_name in self.status_map[status_lower]:
                if mapped_name in self._lists:
                    list_id = self._lists[mapped_name]
                    break

        # Try partial match
        if not list_id:
            for name, lid in self._lists.items():
                if status.lower() in name.lower():
                    list_id = lid
                    break

        if not list_id:
            return False

        result = self._request("PUT", f"cards/{card_id}", {"idList": list_id})
        return result is not None

    def format_branch_name(self, issue_key: str, description: str) -> str:
        """Format branch name."""
        clean_desc = description.lower()
        clean_desc = "".join(c if c.isalnum() or c == " " else "" for c in clean_desc)
        clean_desc = clean_desc.strip().replace(" ", "-")[:40]

        issue_number = issue_key.split("-")[-1][:8] if "-" in issue_key else issue_key[:8]

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
        return False  # Trello doesn't have native sprints

    def get_active_sprint(self) -> Optional[Sprint]:
        return None

    def get_sprint_issues(self, sprint_id: str = None) -> List[Issue]:
        return []

    def add_issue_to_sprint(self, issue_key: str, sprint_id: str) -> bool:
        return False

    def get_boards(self) -> List[Dict]:
        """Get user's boards."""
        if not self.enabled or not self._me:
            return []

        boards = self._request("GET", f"members/me/boards", {
            "filter": "open",
            "fields": "name,url,shortUrl"
        })

        if not boards:
            return []

        return [
            {
                "id": b["id"],
                "name": b["name"],
                "url": b.get("shortUrl", b.get("url", ""))
            }
            for b in boards
        ]

    def get_lists(self) -> List[Dict]:
        """Get lists on current board."""
        if not self.enabled or not self.board_id:
            return []

        lists = self._request("GET", f"boards/{self.board_id}/lists")

        if not lists:
            return []

        return [{"id": l["id"], "name": l["name"]} for l in lists]

    def get_team_members(self) -> List[Dict]:
        """Get board members."""
        if not self.enabled or not self.board_id:
            return []

        members = self._request("GET", f"boards/{self.board_id}/members", {
            "fields": "fullName,username"
        })

        if not members:
            return []

        return [
            {
                "id": m["id"],
                "name": m.get("fullName", m.get("username", "Unknown")),
                "username": m.get("username", ""),
                "active": True
            }
            for m in members
        ]

    def assign_issue(self, issue_key: str, user_id: str) -> bool:
        """Add member to card."""
        if not self.enabled:
            return False

        card_id = issue_key.replace(f"{self.project_key}-", "")

        result = self._request("POST", f"cards/{card_id}/idMembers", {
            "value": user_id
        })

        return result is not None

    def unassign_issue(self, issue_key: str) -> bool:
        """Remove all members from card."""
        if not self.enabled:
            return False

        card_id = issue_key.replace(f"{self.project_key}-", "")

        # Get card members
        card = self._request("GET", f"cards/{card_id}")
        if not card:
            return False

        for member_id in card.get("idMembers", []):
            self._request("DELETE", f"cards/{card_id}/idMembers/{member_id}")

        return True

    def get_unassigned_issues(self, max_results: int = 50) -> List[Issue]:
        """Get cards without members."""
        if not self.enabled or not self.board_id:
            return []

        cards = self._request("GET", f"boards/{self.board_id}/cards", {
            "filter": "open",
            "members": "true"
        })

        if not cards:
            return []

        return [
            self._parse_card(card)
            for card in cards[:max_results]
            if not card.get("idMembers")
        ]

    def search_issues(self, query: str, max_results: int = 50) -> List[Issue]:
        """Search cards by name."""
        if not self.enabled or not self.board_id:
            return []

        # Get all cards and filter
        cards = self._request("GET", f"boards/{self.board_id}/cards", {
            "filter": "open",
            "members": "true",
            "member_fields": "fullName",
            "list": "true"
        })

        if not cards:
            return []

        query_lower = query.lower()
        return [
            self._parse_card(card)
            for card in cards[:max_results]
            if query_lower in card.get("name", "").lower()
        ]

    def archive_card(self, issue_key: str) -> bool:
        """Archive a card."""
        if not self.enabled:
            return False

        card_id = issue_key.replace(f"{self.project_key}-", "")

        result = self._request("PUT", f"cards/{card_id}", {"closed": "true"})
        return result is not None

    def get_labels(self) -> List[Dict]:
        """Get board labels."""
        if not self.enabled or not self.board_id:
            return []

        labels = self._request("GET", f"boards/{self.board_id}/labels")

        if not labels:
            return []

        return [
            {
                "id": l["id"],
                "name": l.get("name", ""),
                "color": l.get("color", "")
            }
            for l in labels
        ]

    def add_label(self, issue_key: str, label_id: str) -> bool:
        """Add label to card."""
        if not self.enabled:
            return False

        card_id = issue_key.replace(f"{self.project_key}-", "")

        result = self._request("POST", f"cards/{card_id}/idLabels", {
            "value": label_id
        })

        return result is not None

    def get_checklists(self, issue_key: str) -> List[Dict]:
        """Get card checklists."""
        if not self.enabled:
            return []

        card_id = issue_key.replace(f"{self.project_key}-", "")

        checklists = self._request("GET", f"cards/{card_id}/checklists")

        if not checklists:
            return []

        result = []
        for cl in checklists:
            items = [
                {
                    "name": item["name"],
                    "complete": item.get("state") == "complete"
                }
                for item in cl.get("checkItems", [])
            ]
            result.append({
                "id": cl["id"],
                "name": cl["name"],
                "items": items
            })

        return result

    def create_checklist(self, issue_key: str, name: str, items: List[str] = None) -> bool:
        """Create a checklist on card."""
        if not self.enabled:
            return False

        card_id = issue_key.replace(f"{self.project_key}-", "")

        checklist = self._request("POST", "checklists", {
            "idCard": card_id,
            "name": name
        })

        if not checklist:
            return False

        if items:
            for item in items:
                self._request("POST", f"checklists/{checklist['id']}/checkItems", {
                    "name": item
                })

        return True

    def _parse_card(self, card: dict) -> Issue:
        """Parse Trello card to Issue."""
        # Get list name (status)
        status = "Unknown"
        if card.get("list"):
            status = card["list"].get("name", "Unknown")

        # Get assignee
        assignee = None
        members = card.get("members", [])
        if members:
            assignee = members[0].get("fullName")

        card_id = card.get("id", "")

        return Issue(
            key=f"{self.project_key}-{card_id}",
            summary=card.get("name", "Untitled"),
            description=card.get("desc", "") or "",
            status=status,
            issue_type="card",
            assignee=assignee,
            url=card.get("shortUrl", card.get("url", "")),
            story_points=None,
            labels=[l.get("name") for l in card.get("labels", []) if l.get("name")]
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
        token = config_values.get("token", "")

        if not api_key or not token:
            return config_values

        typer.echo("\n   Verifying Trello connection...")

        temp = TrelloIntegration()
        temp.api_key = api_key
        temp.token = token

        me = temp._get_me()
        if me:
            typer.secho(f"   Connected as: {me.get('fullName', me.get('username', 'Unknown'))}", fg=typer.colors.GREEN)

            boards = temp.get_boards()
            if boards:
                typer.echo("\n   Your boards:")
                for b in boards[:5]:
                    typer.echo(f"     - {b['name']} ({b['id']})")
        else:
            typer.secho("   Failed to connect", fg=typer.colors.RED)

        return config_values