"""
Jira integration for redgit.

Implements TaskManagementBase for Jira Cloud API v3.
"""

import os
import requests
from typing import Optional, Dict, List, Any

try:
    from redgit.integrations.base import TaskManagementBase, Issue, Sprint, IntegrationType
except ImportError:
    # Fallback for standalone usage
    from dataclasses import dataclass
    from enum import Enum

    class IntegrationType(Enum):
        TASK_MANAGEMENT = "task_management"

    @dataclass
    class Issue:
        key: str
        summary: str
        description: str = ""
        status: str = ""
        type: str = "task"
        priority: str = "medium"
        assignee: str = ""
        reporter: str = ""
        labels: list = None
        created: str = ""
        updated: str = ""
        url: str = ""

        def __post_init__(self):
            if self.labels is None:
                self.labels = []

    @dataclass
    class Sprint:
        id: int
        name: str
        state: str
        start_date: str = ""
        end_date: str = ""
        goal: str = ""

    class TaskManagementBase:
        name = ""
        integration_type = IntegrationType.TASK_MANAGEMENT
        enabled = False
        def __init__(self): pass
        def setup(self, config): pass
        def get_issue(self, key): return None
        def create_issue(self, **kwargs): return None
        def transition_issue(self, key, status): return False
        def get_active_issues(self): return []
        @classmethod
        def get_prompts(cls): return {}


class JiraIntegration(TaskManagementBase):
    """Jira integration - Full task management support with Scrum/Kanban"""

    name = "jira"
    integration_type = IntegrationType.TASK_MANAGEMENT

    # Default issue type IDs (can be overridden in config)
    DEFAULT_ISSUE_TYPES = {
        "epic": "10001",
        "subtask": "10002",
        "task": "10003",
        "story": "10004",
        "feature": "10005",
        "bug": "10007"
    }

    # Default status mappings (can be overridden in config)
    # - todo: Initial status for new issues
    # - after_propose: Status after `rg propose` (started working)
    # - after_push: Status after `rg push` (completed)
    DEFAULT_STATUS_MAP = {
        "todo": ["To Do", "Open", "Backlog"],
        "after_propose": ["In Progress", "In Development", "In Review", "Devam Ediyor"],
        "after_push": ["Done", "Closed", "Resolved", "Complete", "Tamamlandı"]
    }

    def __init__(self):
        super().__init__()
        self.site = ""
        self.email = ""
        self.token = ""
        self.project_key = ""
        self.project_name = ""
        self.board_type = "scrum"  # scrum, kanban, none
        self.board_id = None
        self.issue_types = self.DEFAULT_ISSUE_TYPES.copy()
        self.status_map = self.DEFAULT_STATUS_MAP.copy()
        self.transition_strategy = "auto"  # auto or ask
        self.commit_prefix = ""
        self.branch_pattern = "feature/{issue_key}-{description}"
        self.story_points_field = "customfield"
        self.issue_language = None  # None = same as commit language, or "tr", "en", etc.
        self.session = None
        # Field permissions cache: {issue_type_id: set of field keys}
        self._field_permissions_cache: Dict[str, set] = {}

    def setup(self, config: dict):
        """
        Setup Jira connection.

        Config example (.redgit/config.yaml):
            integrations:
              jira:
                site: "https://your-domain.atlassian.net"
                email: "you@example.com"
                project_key: "SCRUM"
                board_type: "scrum"  # scrum, kanban, none
                board_id: 1  # optional, auto-detected if empty
                story_points_field: "customfield"  # optional
                # API token: JIRA_API_TOKEN env variable or token field
                # Transition strategy: auto or ask
                # - auto: Automatically transition using status mappings
                # - ask: Ask user to select target status for each issue
                transition_strategy: "auto"
                # Status mappings - which Jira statuses to use:
                statuses:
                  # after_propose: Where to move issues after `rg propose`
                  after_propose: ["In Progress", "Devam Ediyor"]
                  # after_push: Where to move issues after `rg push`
                  after_push: ["Done", "Tamamlandı", "Resolved"]
        """
        self.site = config.get("site", "").rstrip("/")
        self.email = config.get("email", "")
        self.token = config.get("token") or os.getenv("JIRA_API_TOKEN")
        self.project_key = config.get("project_key", "")
        self.project_name = config.get("project_name", "")
        self.board_type = config.get("board_type", "scrum")
        self.board_id = config.get("board_id")
        self.story_points_field = config.get("story_points_field", "customfield")
        self.transition_strategy = config.get("transition_strategy", "auto")

        # Override issue types if provided
        if config.get("issue_types"):
            self.issue_types.update(config["issue_types"])

        # Override status mappings if provided
        if config.get("statuses"):
            for key, values in config["statuses"].items():
                if isinstance(values, list):
                    self.status_map[key] = values
                elif isinstance(values, str):
                    self.status_map[key] = [values]

        # Issue language (for Jira issues, separate from commit language)
        self.issue_language = config.get("issue_language")

        # Commit and branch patterns
        self.commit_prefix = config.get("commit_prefix", self.project_key)
        self.branch_pattern = config.get(
            "branch_pattern",
            "feature/{issue_key}-{description}"
        )

        if not all([self.site, self.email, self.token]):
            self.enabled = False
            return

        self.session = requests.Session()
        self.session.auth = (self.email, self.token)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        self.enabled = True

        # Auto-detect board ID if not provided and board_type is not 'none'
        if self.board_type != "none" and not self.board_id and self.project_key:
            self.board_id = self._detect_board_id()

    def _detect_board_id(self) -> Optional[int]:
        """Auto-detect board ID for the project."""
        try:
            url = f"{self.site}/rest/agile/1.0/board"
            params = {"projectKeyOrId": self.project_key}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            boards = response.json().get("values", [])
            if boards:
                # Prefer matching board type
                for board in boards:
                    if board.get("type", "").lower() == self.board_type:
                        return board["id"]
                # Fallback to first board
                return boards[0]["id"]
        except Exception:
            pass
        return None

    def _get_creatable_fields(self, issue_type_id: str, force_refresh: bool = False) -> set:
        """
        Get available fields for issue creation based on screen configuration.

        Uses Jira's createmeta API to determine which fields can be set
        when creating an issue of the given type.

        Args:
            issue_type_id: The issue type ID to check
            force_refresh: Force refresh from API even if cached

        Returns:
            Set of field keys that can be set on issue creation
        """
        # Check cache first
        cache_key = f"{self.project_key}:{issue_type_id}"
        if not force_refresh and cache_key in self._field_permissions_cache:
            return self._field_permissions_cache[cache_key]

        available_fields = set()

        if not self.enabled or not self.project_key:
            return available_fields

        try:
            # Use createmeta API to get available fields for this issue type
            url = f"{self.site}/rest/api/3/issue/createmeta/{self.project_key}/issuetypes/{issue_type_id}"
            response = self.session.get(url)

            if response.status_code == 200:
                data = response.json()
                # Extract field keys from the response
                for field_key in data.get("values", []):
                    if isinstance(field_key, dict):
                        available_fields.add(field_key.get("fieldId", ""))
                    else:
                        available_fields.add(str(field_key))

                # Also check the 'fields' key if present (older API format)
                fields = data.get("fields", {})
                if isinstance(fields, dict):
                    available_fields.update(fields.keys())

            # Fallback: try older createmeta format
            if not available_fields:
                url = f"{self.site}/rest/api/3/issue/createmeta"
                params = {
                    "projectKeys": self.project_key,
                    "issuetypeIds": issue_type_id,
                    "expand": "projects.issuetypes.fields"
                }
                response = self.session.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    for project in data.get("projects", []):
                        for issuetype in project.get("issuetypes", []):
                            if str(issuetype.get("id")) == str(issue_type_id):
                                fields = issuetype.get("fields", {})
                                available_fields.update(fields.keys())

            # Cache the result
            if available_fields:
                self._field_permissions_cache[cache_key] = available_fields

        except Exception as e:
            import sys
            print(f"[Jira] Failed to get creatable fields: {e}", file=sys.stderr)

        return available_fields

    def _can_set_field(self, issue_type_id: str, field_key: str) -> bool:
        """
        Check if a field can be set when creating an issue.

        Args:
            issue_type_id: The issue type ID
            field_key: The field key to check (e.g., 'assignee', 'customfield')

        Returns:
            True if the field can be set, False otherwise
        """
        creatable_fields = self._get_creatable_fields(issue_type_id)

        # If we couldn't get field info, assume we can set it (fail open)
        if not creatable_fields:
            return True

        return field_key in creatable_fields

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """
        Hook called after Jira integration install.
        Auto-detects story_points_field from Jira API.

        Args:
            config_values: Dict of collected config values

        Returns:
            Updated config_values with auto-detected fields
        """
        import typer

        site = config_values.get("site", "").rstrip("/")
        email = config_values.get("email", "")
        token = config_values.get("token")

        if not all([site, email, token]):
            return config_values

        typer.echo("\n   🔍 Auto-detecting Jira fields...")

        # Detect story points field
        story_points_field = JiraIntegration.detect_story_points_field(site, email, token)
        if story_points_field:
            config_values["story_points_field"] = story_points_field
            typer.secho(f"   ✓ Story points field: {story_points_field}", fg=typer.colors.GREEN)
        else:
            typer.echo("   ⚠️  Story points field not found (using default: customfield)")

        return config_values

    @staticmethod
    def detect_story_points_field(site: str, email: str, token: str) -> Optional[str]:
        """
        Auto-detect story points custom field from Jira.

        Args:
            site: Jira site URL (e.g., https://company.atlassian.net)
            email: Jira account email
            token: Jira API token

        Returns:
            Custom field ID (e.g., "customfield") or None if not found
        """
        try:
            import requests
            session = requests.Session()
            session.auth = (email, token)
            session.headers.update({"Accept": "application/json"})

            url = f"{site.rstrip('/')}/rest/api/3/field"
            response = session.get(url)
            response.raise_for_status()

            fields = response.json()

            # Common story points field names (case-insensitive search)
            story_point_keywords = [
                "story point",
                "story_point",
                "storypoint",
                "story-point",
                "sp",
                "points",
                "estimation",
                "estimate"
            ]

            # First pass: exact matches for common names
            for field in fields:
                field_name = (field.get("name") or "").lower()
                field_id = field.get("id", "")

                # Skip non-custom fields
                if not field_id.startswith("customfield_"):
                    continue

                # Check for story points
                if "story point" in field_name or field_name == "story points":
                    return field_id

            # Second pass: keyword matching
            for field in fields:
                field_name = (field.get("name") or "").lower()
                field_id = field.get("id", "")

                if not field_id.startswith("customfield_"):
                    continue

                for keyword in story_point_keywords:
                    if keyword in field_name:
                        return field_id

            # Third pass: check schema for number type fields that might be story points
            for field in fields:
                field_id = field.get("id", "")
                schema = field.get("schema", {})

                if not field_id.startswith("customfield_"):
                    continue

                # Story points are typically number fields
                if schema.get("type") == "number":
                    field_name = (field.get("name") or "").lower()
                    # Avoid time tracking fields
                    if "time" not in field_name and "hour" not in field_name:
                        if "point" in field_name or "estimate" in field_name:
                            return field_id

        except Exception:
            pass

        return None

    # ==================== TaskManagementBase Implementation ====================

    def _get_issue_fields(self, include_priority: bool = False) -> str:
        """Get dynamic fields string for API calls."""
        fields = ["summary", "status", "issuetype", "assignee", "description", "parent"]
        if self.story_points_field:
            fields.append(self.story_points_field)
        if include_priority:
            fields.append("priority")
        # Add epic link field if known
        epic_field = self.get_epic_link_field()
        if epic_field and epic_field not in fields:
            fields.append(epic_field)
        return ",".join(fields)

    def get_my_active_issues(self, exclude_subtasks: bool = True) -> List[Issue]:
        """Get issues assigned to current user that are in progress or to do.

        Args:
            exclude_subtasks: If True, filter out subtasks (subtasks can't have child subtasks)
        """
        if not self.enabled:
            return []

        issues = []

        # Build status list from config (todo + after_propose statuses)
        active_statuses = []
        active_statuses.extend(self.status_map.get("todo", ["To Do", "Open", "Backlog"]))
        active_statuses.extend(self.status_map.get("after_propose", ["In Progress", "In Development"]))

        # Remove duplicates and format for JQL
        active_statuses = list(set(active_statuses))
        status_jql = ", ".join(f'"{s}"' for s in active_statuses)

        # JQL to find active issues assigned to current user
        jql = (
            f'project = "{self.project_key}" '
            f'AND assignee = currentUser() '
            f'AND status in ({status_jql}) '
            f'ORDER BY updated DESC'
        )

        # Use the new search method that handles API version changes
        raw_issues = self._search_jql(jql, max_results=50)
        for item in raw_issues:
            issue = self._parse_issue(item)
            # Filter out subtasks if requested (subtasks can't have child subtasks)
            if exclude_subtasks and issue.issue_type and "subtask" in issue.issue_type.lower().replace("-", "").replace(" ", ""):
                continue
            issues.append(issue)

        # Also get issues from active sprint if using scrum (only mine)
        if self.board_type == "scrum" and self.board_id:
            sprint_issues = self.get_sprint_issues()
            # Merge without duplicates - only issues assigned to current user
            existing_keys = {i.key for i in issues}
            my_email = self.email.lower() if self.email else ""
            for si in sprint_issues:
                if si.key not in existing_keys:
                    # Skip subtasks
                    if exclude_subtasks and si.issue_type and "subtask" in si.issue_type.lower().replace("-", "").replace(" ", ""):
                        continue
                    # Only add if assigned to me (check by email or displayName match)
                    if si.assignee and my_email and my_email in si.assignee.lower():
                        issues.append(si)

        return issues

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """Get a single issue by key."""
        if not self.enabled:
            return None

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}"
            params = {
                "fields": self._get_issue_fields()
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return self._parse_issue(response.json())
        except Exception:
            return None

    def create_issue(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        story_points: Optional[float] = None,
        assign_to_me: bool = True,
        parent_key: Optional[str] = None
    ) -> Optional[str]:
        """Create a new issue in the project.

        Args:
            summary: Issue title
            description: Issue description
            issue_type: Type of issue (task, story, bug, subtask, etc.)
            story_points: Story points (defaults to 1 if not specified)
            assign_to_me: Auto-assign to current user (default: True)
            parent_key: Parent issue key for subtasks

        Returns:
            Issue key on success, None on failure

        Raises:
            PermissionError: If user doesn't have permission to create issues
        """
        if not self.enabled or not self.project_key:
            return None

        # Handle subtask creation
        if parent_key or issue_type.lower() == "subtask":
            return self.create_subtask(
                parent_key=parent_key,
                summary=summary,
                description=description,
                assign_to_me=assign_to_me
            )

        issue_type_id = self.issue_types.get(issue_type.lower(), self.issue_types["task"])

        try:
            url = f"{self.site}/rest/api/3/issue"
            payload = {
                "fields": {
                    "project": {"key": self.project_key},
                    "summary": summary,
                    "issuetype": {"id": issue_type_id}
                }
            }

            if description:
                payload["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}]
                    }]
                }

            # Check field permissions and add optional fields only if allowed
            # Set story points (default to 1 if not specified) - only if field is available
            if self.story_points_field and self._can_set_field(issue_type_id, self.story_points_field):
                payload["fields"][self.story_points_field] = story_points if story_points else 1

            # Check if assignee can be set during creation
            can_set_assignee = self._can_set_field(issue_type_id, "assignee")

            # Auto-assign to current user (during creation if allowed)
            my_account_id = None
            if assign_to_me:
                my_account_id = self._get_my_account_id()
                if my_account_id and can_set_assignee:
                    payload["fields"]["assignee"] = {"accountId": my_account_id}

            response = self.session.post(url, json=payload)

            # Check for permission errors
            if response.status_code == 403:
                raise PermissionError("No permission to create issues in this project")
            if response.status_code == 400:
                error_data = response.json()
                errors = error_data.get("errors", {})
                if "issuetype" in errors or "project" in errors:
                    raise PermissionError(f"Permission error: {errors}")
                # If specific field errors, retry without those fields
                if errors:
                    for field_key in list(errors.keys()):
                        if field_key in payload["fields"] and field_key not in ["project", "summary", "issuetype"]:
                            del payload["fields"][field_key]
                    response = self.session.post(url, json=payload)

            response.raise_for_status()

            issue_key = response.json().get("key")

            # Assign after creation if couldn't set during creation
            if issue_key and assign_to_me and my_account_id and not can_set_assignee:
                self.assign_issue(issue_key, my_account_id)

            # Add to active sprint if using scrum
            if self.board_type == "scrum" and issue_key:
                self.add_issue_to_active_sprint(issue_key)

            return issue_key
        except PermissionError:
            raise
        except Exception:
            return None

    def _detect_subtask_type_id(self) -> Optional[str]:
        """Auto-detect subtask issue type ID from Jira API and save to config."""
        if not self.enabled:
            return None

        try:
            url = f"{self.site}/rest/api/3/issuetype/project?projectId={self._get_project_id()}"
            response = self.session.get(url)

            # Fallback to global issue types if project-specific fails
            if response.status_code != 200:
                url = f"{self.site}/rest/api/3/issuetype"
                response = self.session.get(url)

            response.raise_for_status()
            issue_types = response.json()

            # Find subtask type
            for it in issue_types:
                name = it.get("name", "").lower()
                # Check if it's a subtask type
                if it.get("subtask") or name in ["subtask", "sub-task", "alt görev"]:
                    subtask_id = it.get("id")
                    if subtask_id:
                        # Save to config for future use
                        self._save_subtask_type_to_config(subtask_id)
                        return subtask_id

        except Exception as e:
            import sys
            print(f"[Jira] Failed to detect subtask type: {e}", file=sys.stderr)

        return None

    def _get_project_id(self) -> Optional[str]:
        """Get project ID from project key."""
        if not self.enabled or not self.project_key:
            return None

        try:
            url = f"{self.site}/rest/api/3/project/{self.project_key}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json().get("id")
        except Exception:
            return None

    def _save_subtask_type_to_config(self, subtask_id: str):
        """Save detected subtask type ID to config.yaml."""
        try:
            import yaml
            from pathlib import Path

            # Try project config first, then global
            config_paths = [
                Path(".redgit/config.yaml"),
                Path.home() / ".redgit" / "config.yaml"
            ]

            for config_path in config_paths:
                if config_path.exists():
                    config = yaml.safe_load(config_path.read_text()) or {}

                    # Ensure structure exists
                    if "integrations" not in config:
                        config["integrations"] = {}
                    if "jira" not in config["integrations"]:
                        config["integrations"]["jira"] = {}
                    if "issue_types" not in config["integrations"]["jira"]:
                        config["integrations"]["jira"]["issue_types"] = {}

                    # Save subtask ID
                    config["integrations"]["jira"]["issue_types"]["subtask"] = subtask_id

                    # Write back
                    config_path.write_text(yaml.dump(config, allow_unicode=True, sort_keys=False))

                    import sys
                    print(f"[Jira] Auto-detected subtask type ID: {subtask_id} (saved to config)", file=sys.stderr)
                    break

        except Exception as e:
            import sys
            print(f"[Jira] Failed to save subtask type to config: {e}", file=sys.stderr)

    def create_subtask(
        self,
        parent_key: str,
        summary: str,
        description: str = "",
        assign_to_me: bool = True
    ) -> Optional[str]:
        """Create a subtask under a parent issue.

        Checks field permissions and adapts to Jira screen configuration.
        If certain fields cannot be set during creation, they will be
        set afterwards using separate API calls.

        Args:
            parent_key: Parent issue key (e.g., PROJ-123)
            summary: Subtask title
            description: Subtask description
            assign_to_me: Auto-assign to current user (default: True)

        Returns:
            Subtask key on success, None on failure
        """
        if not self.enabled or not parent_key:
            return None

        # Get subtask type ID - auto-detect if not configured
        subtask_type_id = self.issue_types.get("subtask")
        if not subtask_type_id:
            subtask_type_id = self._detect_subtask_type_id()
        if not subtask_type_id:
            subtask_type_id = "10002"  # Last resort fallback

        try:
            url = f"{self.site}/rest/api/3/issue"
            payload = {
                "fields": {
                    "project": {"key": self.project_key},
                    "parent": {"key": parent_key},
                    "summary": summary,
                    "issuetype": {"id": subtask_type_id}
                }
            }

            # Check if description can be set during creation
            if description and self._can_set_field(subtask_type_id, "description"):
                payload["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}]
                    }]
                }

            # Create subtask without assignee (assign separately afterwards)
            response = self.session.post(url, json=payload)

            # If specific field errors, retry without those fields
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    errors = error_data.get("errors", {})
                    if errors:
                        for field_key in list(errors.keys()):
                            if field_key in payload["fields"] and field_key not in ["project", "summary", "issuetype", "parent"]:
                                del payload["fields"][field_key]
                        response = self.session.post(url, json=payload)
                except Exception:
                    pass

            # Check for errors
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    errors = error_data.get("errors", {})
                    error_messages = error_data.get("errorMessages", [])
                    if errors or error_messages:
                        import sys
                        print(f"[Jira] Subtask creation failed: {errors or error_messages}", file=sys.stderr)
                except Exception:
                    pass

            response.raise_for_status()

            subtask_key = response.json().get("key")

            # Assign after creation if requested (works even if assignee field not on create screen)
            if subtask_key and assign_to_me:
                my_account_id = self._get_my_account_id()
                if my_account_id:
                    self.assign_issue(subtask_key, my_account_id)

            return subtask_key
        except Exception as e:
            import sys
            print(f"[Jira] Subtask creation error: {e}", file=sys.stderr)
            return None

    def can_create_issues(self) -> bool:
        """Check if current user has permission to create issues."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/mypermissions"
            params = {"projectKey": self.project_key, "permissions": "CREATE_ISSUES"}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            permissions = response.json().get("permissions", {})
            create_perm = permissions.get("CREATE_ISSUES", {})
            return create_perm.get("havePermission", False)
        except Exception:
            return True  # Assume yes if can't check

    def _get_my_account_id(self) -> Optional[str]:
        """Get current user's account ID."""
        if not self.enabled:
            return None

        try:
            url = f"{self.site}/rest/api/3/myself"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json().get("accountId")
        except Exception:
            return None

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add comment to Jira issue."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}/comment"
            payload = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}]
                    }]
                }
            }
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def get_available_transitions(self, issue_key: str) -> List[Dict]:
        """Get available transitions for an issue.

        Returns list of dicts with:
        - id: Transition ID
        - name: Transition name (action name, e.g., "Start Progress")
        - to: Target status name (e.g., "In Progress")
        """
        if not self.enabled:
            return []

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}/transitions"
            response = self.session.get(url)
            response.raise_for_status()

            transitions = response.json().get("transitions", [])
            return [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "to": t.get("to", {}).get("name", "")
                }
                for t in transitions
            ]
        except Exception:
            return []

    def transition_issue_by_id(self, issue_key: str, transition_id: str) -> bool:
        """Transition an issue using the transition ID directly.

        Args:
            issue_key: Jira issue key
            transition_id: Transition ID from get_available_transitions()

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}/transitions"
            resp = self.session.post(url, json={"transition": {"id": transition_id}})
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def transition_issue(self, issue_key: str, status: str, verbose: bool = False, auto_advance: bool = True) -> bool:
        """Change issue status (e.g., 'In Progress', 'Done').

        Uses status_map from config to find matching transitions.
        If target status is not directly reachable and auto_advance=True,
        will try to advance to the next available stage in the workflow.

        Args:
            issue_key: Jira issue key
            status: Target status (e.g., 'done', 'in_progress')
            verbose: Print debug information
            auto_advance: If True, advance to next stage if target not reachable
        """
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}/transitions"
            response = self.session.get(url)
            response.raise_for_status()

            transitions = response.json().get("transitions", [])

            if verbose:
                print(f"[DEBUG] {issue_key} available transitions:")
                for t in transitions:
                    print(f"  - '{t['name']}' -> '{t.get('to', {}).get('name', '')}'")

            # Try exact match first (Transition Name)
            for t in transitions:
                if t["name"].lower() == status.lower():
                    resp = self.session.post(url, json={"transition": {"id": t["id"]}})
                    return resp.status_code in (200, 204)

            # Check for Target Status Name (e.g. transition "Start Progress" -> status "In Progress")
            for t in transitions:
                if t.get("to", {}).get("name", "").lower() == status.lower():
                    resp = self.session.post(url, json={"transition": {"id": t["id"]}})
                    return resp.status_code in (200, 204)

            # Try mapped status names from config
            status_lower = status.lower().replace(" ", "_")
            if status_lower in self.status_map:
                for status_name in self.status_map[status_lower]:
                    for t in transitions:
                        # Check Transition Name
                        if t["name"].lower() == status_name.lower():
                            resp = self.session.post(url, json={"transition": {"id": t["id"]}})
                            return resp.status_code in (200, 204)
                        # Check Target Status Name
                        if t.get("to", {}).get("name", "").lower() == status_name.lower():
                            resp = self.session.post(url, json={"transition": {"id": t["id"]}})
                            return resp.status_code in (200, 204)

            # Auto-advance: If target status not reachable, try next available stage
            # BUT only if it's a "done-like" or "progress-like" status (never go backwards to todo)
            if auto_advance and transitions:
                # Keywords that indicate forward progress (acceptable auto-transitions)
                forward_keywords = ["done", "complete", "closed", "resolved", "finish",
                                   "review", "test", "qa", "verify", "approve",
                                   "progress", "development", "devam", "tamamlan"]

                # Keywords that indicate backwards movement (NEVER auto-transition to these)
                backward_keywords = ["todo", "backlog", "open", "new", "to do", "yapılacak", "açık"]

                # Filter out backward transitions
                valid_transitions = []
                for t in transitions:
                    target = t.get("to", {}).get("name", "").lower()
                    # Skip if target looks like a "todo" status
                    is_backward = any(kw in target for kw in backward_keywords)
                    if not is_backward:
                        valid_transitions.append(t)

                # Sort valid transitions by priority (done-like first)
                def get_priority(t):
                    target = t.get("to", {}).get("name", "").lower()
                    for i, keyword in enumerate(forward_keywords):
                        if keyword in target:
                            return i
                    return len(forward_keywords)  # Lowest priority

                sorted_transitions = sorted(valid_transitions, key=get_priority)

                # Only auto-advance if we have a valid forward transition
                if sorted_transitions:
                    best_transition = sorted_transitions[0]
                    target_name = best_transition.get('to', {}).get('name', '')

                    # Double-check it's a forward transition
                    target_lower = target_name.lower()
                    is_forward = any(kw in target_lower for kw in forward_keywords)

                    if is_forward:
                        if verbose:
                            print(f"[DEBUG] Auto-advancing to: {target_name}")
                        resp = self.session.post(url, json={"transition": {"id": best_transition["id"]}})
                        return resp.status_code in (200, 204)

            if verbose:
                print(f"[DEBUG] No matching transition found for status '{status}'")
                print(f"[DEBUG] Status map: {self.status_map.get(status_lower, [])}")
                print(f"[DEBUG] Available transitions: {[t.get('to', {}).get('name', '') for t in transitions]}")

        except Exception as e:
            if verbose:
                print(f"[DEBUG] Transition error: {e}")
        return False

    def format_branch_name(self, issue_key: str, description: str) -> str:
        """Format branch name using the configured pattern."""
        # Clean description for branch name
        clean_desc = description.lower()
        clean_desc = "".join(c if c.isalnum() or c == " " else "" for c in clean_desc)
        clean_desc = clean_desc.strip().replace(" ", "-")[:40]

        # Extract issue number from key (e.g., "SCRUM-656" -> "656")
        issue_number = issue_key.split("-")[-1] if "-" in issue_key else issue_key

        return self.branch_pattern.format(
            issue_key=issue_key,
            issue_number=issue_number,
            description=clean_desc,
            project_key=self.project_key
        )

    def get_commit_prefix(self) -> str:
        """Get prefix for commit messages."""
        return self.commit_prefix or self.project_key

    # ==================== Sprint Support ====================

    def supports_sprints(self) -> bool:
        """Jira supports sprints when board_type is scrum."""
        return self.board_type == "scrum" and self.board_id is not None

    def get_active_sprint(self) -> Optional[Sprint]:
        """Get the active sprint for the board."""
        if not self.enabled or not self.board_id or self.board_type != "scrum":
            return None

        try:
            url = f"{self.site}/rest/agile/1.0/board/{self.board_id}/sprint"
            params = {"state": "active"}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            sprints = response.json().get("values", [])
            if sprints:
                s = sprints[0]
                return Sprint(
                    id=str(s["id"]),
                    name=s.get("name", ""),
                    state=s.get("state", "active"),
                    start_date=s.get("startDate"),
                    end_date=s.get("endDate"),
                    goal=s.get("goal")
                )
        except Exception:
            pass
        return None

    def get_sprint_issues(self, sprint_id: str = None) -> List[Issue]:
        """Get issues in a sprint."""
        if not self.enabled:
            return []

        if sprint_id is None:
            sprint = self.get_active_sprint()
            if not sprint:
                return []
            sprint_id = sprint.id

        issues = []
        try:
            url = f"{self.site}/rest/agile/1.0/sprint/{sprint_id}/issue"
            params = {
                "fields": self._get_issue_fields()
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for item in response.json().get("issues", []):
                issues.append(self._parse_issue(item))
        except Exception:
            pass

        return issues

    def add_issue_to_sprint(self, issue_key: str, sprint_id: str) -> bool:
        """Add an issue to a sprint."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/agile/1.0/sprint/{sprint_id}/issue"
            payload = {"issues": [issue_key]}
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def add_issue_to_active_sprint(self, issue_key: str) -> bool:
        """Add an issue to the currently active sprint."""
        sprint = self.get_active_sprint()
        if sprint:
            return self.add_issue_to_sprint(issue_key, sprint.id)
        return False

    # ==================== Additional Jira-specific Methods ====================

    def get_board_info(self) -> Optional[Dict]:
        """Get board information."""
        if not self.enabled or not self.board_id:
            return None

        try:
            url = f"{self.site}/rest/agile/1.0/board/{self.board_id}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def get_backlog_issues(self, max_results: int = 50) -> List[Issue]:
        """Get issues in the backlog (not in any sprint)."""
        if not self.enabled or not self.board_id:
            return []

        issues = []
        try:
            url = f"{self.site}/rest/agile/1.0/board/{self.board_id}/backlog"
            params = {"maxResults": max_results}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for item in response.json().get("issues", []):
                issues.append(self._parse_issue(item))
        except Exception:
            pass

        return issues

    def get_future_sprints(self) -> List[Sprint]:
        """Get future sprints for the board."""
        if not self.enabled or not self.board_id or self.board_type != "scrum":
            return []

        sprints = []
        try:
            url = f"{self.site}/rest/agile/1.0/board/{self.board_id}/sprint"
            params = {"state": "future"}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for s in response.json().get("values", []):
                sprints.append(Sprint(
                    id=str(s["id"]),
                    name=s.get("name", ""),
                    state=s.get("state", "future"),
                    start_date=s.get("startDate"),
                    end_date=s.get("endDate"),
                    goal=s.get("goal")
                ))
        except Exception:
            pass

        return sprints

    # ==================== Hooks ====================

    def on_commit(self, group: dict, context: dict):
        """Add comment to Jira issue after commit."""
        if not self.enabled:
            return

        issue_key = context.get("issue_key")
        if not issue_key:
            return

        comment = (
            f"*Commit:* {group.get('commit_title', 'N/A')}\n"
            f"*Branch:* {group.get('branch', 'N/A')}\n"
            f"*Files:* {len(group.get('files', []))} files"
        )

        self.add_comment(issue_key, comment)

    # ==================== Project Management ====================

    def get_projects(self) -> List[Dict]:
        """Get all accessible Jira projects."""
        if not self.enabled:
            return []

        projects = []
        try:
            url = f"{self.site}/rest/api/3/project"
            response = self.session.get(url)
            response.raise_for_status()

            for p in response.json():
                projects.append({
                    "key": p.get("key"),
                    "name": p.get("name"),
                    "id": p.get("id"),
                    "style": p.get("style"),  # classic, next-gen
                    "lead": p.get("lead", {}).get("displayName"),
                    "url": f"{self.site}/browse/{p.get('key')}"
                })
        except Exception:
            pass

        return projects

    def get_project(self, project_key: str = None) -> Optional[Dict]:
        """Get project details."""
        if not self.enabled:
            return None

        key = project_key or self.project_key
        if not key:
            return None

        try:
            url = f"{self.site}/rest/api/3/project/{key}"
            response = self.session.get(url)
            response.raise_for_status()

            p = response.json()
            return {
                "key": p.get("key"),
                "name": p.get("name"),
                "id": p.get("id"),
                "description": p.get("description"),
                "lead": p.get("lead", {}).get("displayName"),
                "url": f"{self.site}/browse/{p.get('key')}",
                "issue_types": [it.get("name") for it in p.get("issueTypes", [])]
            }
        except Exception:
            return None

    # ==================== Team & User Management ====================

    def get_project_users(self, project_key: str = None, max_results: int = 100) -> List[Dict]:
        """Get users assignable to a project."""
        if not self.enabled:
            return []

        key = project_key or self.project_key
        if not key:
            return []

        users = []
        try:
            url = f"{self.site}/rest/api/3/user/assignable/search"
            params = {"project": key, "maxResults": max_results}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for u in response.json():
                users.append({
                    "account_id": u.get("accountId"),
                    "display_name": u.get("displayName"),
                    "email": u.get("emailAddress"),
                    "active": u.get("active", True),
                    "avatar": u.get("avatarUrls", {}).get("48x48")
                })
        except Exception:
            pass

        return users

    def get_all_users(self, max_results: int = 100) -> List[Dict]:
        """Get all users in the Jira instance."""
        if not self.enabled:
            return []

        users = []
        try:
            url = f"{self.site}/rest/api/3/users/search"
            params = {"maxResults": max_results}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for u in response.json():
                users.append({
                    "account_id": u.get("accountId"),
                    "display_name": u.get("displayName"),
                    "email": u.get("emailAddress"),
                    "active": u.get("active", True),
                    "avatar": u.get("avatarUrls", {}).get("48x48")
                })
        except Exception:
            pass

        return users

    def get_user(self, account_id: str) -> Optional[Dict]:
        """Get user details by account ID."""
        if not self.enabled:
            return None

        try:
            url = f"{self.site}/rest/api/3/user"
            params = {"accountId": account_id}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            u = response.json()
            return {
                "account_id": u.get("accountId"),
                "display_name": u.get("displayName"),
                "email": u.get("emailAddress"),
                "active": u.get("active", True),
                "avatar": u.get("avatarUrls", {}).get("48x48"),
                "timezone": u.get("timeZone")
            }
        except Exception:
            return None

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Get current authenticated user info (override base class).

        Returns:
            Dict with 'id', 'display_name', 'email' or None
        """
        account_id = self._get_my_account_id()
        if account_id:
            user = self.get_user(account_id)
            if user:
                return {
                    "id": user.get("account_id"),
                    "display_name": user.get("display_name"),
                    "email": user.get("email")
                }
        return None

    def get_team_members(self, project_key: str = None) -> List[Dict[str, Any]]:
        """
        Get team members for a project (override base class).

        Returns:
            List of dicts with 'id', 'display_name', 'email', 'active'
        """
        users = self.get_project_users(project_key)
        return [
            {
                "id": u.get("account_id"),
                "display_name": u.get("display_name"),
                "email": u.get("email"),
                "active": u.get("active", True)
            }
            for u in users
        ]

    def search_users(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search users by name or email."""
        if not self.enabled:
            return []

        users = []
        try:
            url = f"{self.site}/rest/api/3/user/search"
            params = {"query": query, "maxResults": max_results}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for u in response.json():
                users.append({
                    "account_id": u.get("accountId"),
                    "display_name": u.get("displayName"),
                    "email": u.get("emailAddress"),
                    "active": u.get("active", True)
                })
        except Exception:
            pass

        return users

    def assign_issue(self, issue_key: str, account_id: str) -> bool:
        """Assign an issue to a user."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}/assignee"
            payload = {"accountId": account_id}
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def unassign_issue(self, issue_key: str) -> bool:
        """Remove assignee from an issue."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}/assignee"
            payload = {"accountId": None}
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def get_user_issues(self, account_id: str = None, status: str = None, max_results: int = 50) -> List[Issue]:
        """Get issues assigned to a specific user."""
        if not self.enabled:
            return []

        issues = []

        # Build JQL
        jql_parts = [f'project = "{self.project_key}"']

        if account_id:
            jql_parts.append(f'assignee = "{account_id}"')
        else:
            jql_parts.append('assignee = currentUser()')

        if status:
            if status.lower() == "active":
                jql_parts.append('status in ("To Do", "In Progress", "Open", "In Development")')
            elif status.lower() == "done":
                jql_parts.append('status in ("Done", "Closed", "Resolved")')
            else:
                jql_parts.append(f'status = "{status}"')

        jql_parts.append('ORDER BY updated DESC')
        jql = ' AND '.join(jql_parts[:-1]) + ' ' + jql_parts[-1]

        try:
            url = f"{self.site}/rest/api/3/search"
            params = {
                "jql": jql,
                "maxResults": max_results,
                "fields": self._get_issue_fields(include_priority=True)
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for item in response.json().get("issues", []):
                issues.append(self._parse_issue(item))
        except Exception:
            pass

        return issues

    # ==================== Issue Queries ====================

    def _search_jql(self, jql: str, max_results: int = 50, fields: str = None) -> List[dict]:
        """
        Execute JQL search using the new /search/jql endpoint.
        Falls back to legacy /search if new endpoint fails.

        Args:
            jql: JQL query string
            max_results: Maximum results to return
            fields: Comma-separated field names

        Returns:
            List of raw issue dicts from API
        """
        if not self.enabled:
            return []

        if fields is None:
            fields = self._get_issue_fields(include_priority=True)

        # Try new endpoint first (POST /rest/api/3/search/jql)
        try:
            url = f"{self.site}/rest/api/3/search/jql"
            payload = {
                "jql": jql,
                "maxResults": max_results,
                "fields": fields.split(",") if isinstance(fields, str) else fields
            }
            response = self.session.post(url, json=payload)

            if response.status_code == 200:
                return response.json().get("issues", [])

        except Exception:
            pass

        # Fallback to legacy endpoint (GET /rest/api/3/search)
        try:
            url = f"{self.site}/rest/api/3/search"
            params = {
                "jql": jql,
                "maxResults": max_results,
                "fields": fields
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json().get("issues", [])

        except Exception:
            pass

        return []

    def search_issues(self, jql: str, max_results: int = 50) -> List[Issue]:
        """Search issues using JQL."""
        if not self.enabled:
            return []

        issues = []
        raw_issues = self._search_jql(jql, max_results)

        for item in raw_issues:
            issues.append(self._parse_issue(item))

        return issues

    def get_unassigned_issues(self, max_results: int = 50) -> List[Issue]:
        """Get unassigned issues in the project."""
        jql = (
            f'project = "{self.project_key}" '
            f'AND assignee IS EMPTY '
            f'AND status in ("To Do", "Open", "Backlog") '
            f'ORDER BY priority DESC, created ASC'
        )
        return self.search_issues(jql, max_results)

    # ==================== Internal Helpers ====================

    def _parse_issue(self, data: dict) -> Issue:
        """Parse Jira API response to Issue object."""
        fields = data.get("fields", {})

        # Extract description text
        description = ""
        desc_content = fields.get("description")
        if desc_content and isinstance(desc_content, dict):
            # ADF format
            for block in desc_content.get("content", []):
                if block.get("type") == "paragraph":
                    for item in block.get("content", []):
                        if item.get("type") == "text":
                            description += item.get("text", "")
                    description += "\n"
        elif isinstance(desc_content, str):
            description = desc_content

        # Extract assignee
        assignee = None
        assignee_data = fields.get("assignee")
        if assignee_data:
            assignee = assignee_data.get("displayName") or assignee_data.get("emailAddress")

        # Extract story points
        story_points = None
        if self.story_points_field:
            story_points = fields.get(self.story_points_field)

        # Extract parent/epic info
        parent_key = None
        parent_summary = None

        # Next-gen projects use 'parent' field
        parent_data = fields.get("parent")
        if parent_data:
            parent_key = parent_data.get("key")
            parent_fields = parent_data.get("fields", {})
            parent_summary = parent_fields.get("summary", "")

        # Classic projects may use epic link custom field
        if not parent_key:
            epic_field = self.get_epic_link_field()
            if epic_field:
                epic_key = fields.get(epic_field)
                if epic_key:
                    parent_key = epic_key
                    # Epic summary might be in a separate field or need to be fetched
                    # For now, just use the key

        return Issue(
            key=data.get("key", ""),
            summary=fields.get("summary", ""),
            description=description.strip(),
            status=fields.get("status", {}).get("name", "Unknown"),
            issue_type=fields.get("issuetype", {}).get("name", "Task"),
            assignee=assignee,
            url=f"{self.site}/browse/{data.get('key', '')}",
            story_points=story_points,
            parent_key=parent_key,
            parent_summary=parent_summary
        )

    # ==================== Issue Linking ====================

    def link_issues(self, source_key: str, target_key: str, link_type: str = "Blocks") -> bool:
        """
        Create a link between two issues.

        Link types:
        - "Blocks" / "is blocked by"
        - "Clones" / "is cloned by"
        - "Duplicate" / "is duplicated by"
        - "Relates" (relates to)

        Args:
            source_key: The issue that blocks/clones/etc
            target_key: The issue that is blocked/cloned/etc
            link_type: Type of link (default: "Blocks")

        Returns:
            True if link created successfully
        """
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issueLink"
            payload = {
                "type": {"name": link_type},
                "inwardIssue": {"key": target_key},
                "outwardIssue": {"key": source_key}
            }
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def get_issue_links(self, issue_key: str) -> List[Dict]:
        """
        Get all links for an issue.

        Returns list of dicts with:
        - type: Link type name
        - direction: "inward" or "outward"
        - issue_key: The linked issue key
        - issue_summary: The linked issue summary
        """
        if not self.enabled:
            return []

        links = []
        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}"
            params = {"fields": "issuelinks"}
            response = self.session.get(url, params=params)
            response.raise_for_status()

            for link in response.json().get("fields", {}).get("issuelinks", []):
                link_type = link.get("type", {}).get("name", "")

                if "inwardIssue" in link:
                    linked_issue = link["inwardIssue"]
                    direction = "inward"
                    relation = link.get("type", {}).get("inward", "")
                else:
                    linked_issue = link["outwardIssue"]
                    direction = "outward"
                    relation = link.get("type", {}).get("outward", "")

                links.append({
                    "type": link_type,
                    "direction": direction,
                    "relation": relation,
                    "issue_key": linked_issue.get("key"),
                    "issue_summary": linked_issue.get("fields", {}).get("summary", "")
                })
        except Exception:
            pass

        return links

    def get_link_types(self) -> List[Dict]:
        """Get available issue link types."""
        if not self.enabled:
            return []

        try:
            url = f"{self.site}/rest/api/3/issueLinkType"
            response = self.session.get(url)
            response.raise_for_status()

            return [
                {
                    "name": lt.get("name"),
                    "inward": lt.get("inward"),
                    "outward": lt.get("outward")
                }
                for lt in response.json().get("issueLinkTypes", [])
            ]
        except Exception:
            return []

    # ==================== Epic-Story Hierarchy ====================

    def get_epic_link_field(self) -> Optional[str]:
        """
        Discover the epic link custom field ID for the project.
        This varies between Jira instances.
        """
        if not self.enabled:
            return None

        try:
            url = f"{self.site}/rest/api/3/field"
            response = self.session.get(url)
            response.raise_for_status()

            for field in response.json():
                name = field.get("name", "").lower()
                # Common epic link field names
                if name in ["epic link", "parent link", "epic"]:
                    if field.get("custom"):
                        return field.get("id")

            # Fallback: search for "epic" in schema
            for field in response.json():
                schema = field.get("schema", {})
                if "epic" in schema.get("custom", "").lower():
                    return field.get("id")

        except Exception:
            pass

        return None

    def create_issue_with_parent(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "story",
        parent_key: str = None,
        story_points: Optional[float] = None,
        labels: List[str] = None,
        assignee_id: str = None
    ) -> Optional[Issue]:
        """
        Create an issue with optional parent (epic or parent issue).

        For next-gen projects: Uses native parent field
        For classic projects: Uses epic link custom field

        Args:
            summary: Issue title
            description: Issue description
            issue_type: Type of issue (story, task, subtask, bug)
            parent_key: Parent issue key (epic for stories, story for subtasks)
            story_points: Story point estimate
            labels: List of labels to add
            assignee_id: Account ID of assignee

        Returns:
            Created Issue object or None
        """
        if not self.enabled or not self.project_key:
            return None

        issue_type_id = self.issue_types.get(issue_type.lower(), self.issue_types.get("task"))

        try:
            url = f"{self.site}/rest/api/3/issue"
            payload = {
                "fields": {
                    "project": {"key": self.project_key},
                    "summary": summary,
                    "issuetype": {"id": issue_type_id}
                }
            }

            if description:
                payload["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}]
                    }]
                }

            if story_points and self.story_points_field:
                payload["fields"][self.story_points_field] = story_points

            if labels:
                payload["fields"]["labels"] = labels

            if assignee_id:
                payload["fields"]["assignee"] = {"accountId": assignee_id}

            # Handle parent relationship
            if parent_key:
                if issue_type.lower() == "subtask":
                    # Subtasks use native parent field
                    payload["fields"]["parent"] = {"key": parent_key}
                else:
                    # Try next-gen parent field first
                    payload["fields"]["parent"] = {"key": parent_key}

            response = self.session.post(url, json=payload)

            # If parent field failed (classic project), try epic link
            if response.status_code == 400 and parent_key:
                del payload["fields"]["parent"]
                epic_field = self.get_epic_link_field()
                if epic_field:
                    payload["fields"][epic_field] = parent_key
                    response = self.session.post(url, json=payload)

            response.raise_for_status()
            issue_key = response.json().get("key")

            if issue_key:
                return self.get_issue(issue_key)

        except Exception:
            pass

        return None

    def get_epic_issues(self, epic_key: str) -> List[Issue]:
        """Get all issues under an epic."""
        if not self.enabled:
            return []

        # Try JQL with parent (next-gen)
        jql = f'parent = "{epic_key}" ORDER BY rank ASC'
        issues = self.search_issues(jql)

        # If empty, try epic link field (classic)
        if not issues:
            epic_field = self.get_epic_link_field()
            if epic_field:
                jql = f'"{epic_field}" = "{epic_key}" ORDER BY rank ASC'
                issues = self.search_issues(jql)

        return issues

    def set_epic_link(self, issue_key: str, epic_key: str) -> bool:
        """Set or update the epic link for an issue."""
        if not self.enabled:
            return False

        try:
            # Try next-gen parent field
            url = f"{self.site}/rest/api/3/issue/{issue_key}"
            payload = {"fields": {"parent": {"key": epic_key}}}
            response = self.session.put(url, json=payload)

            if response.status_code == 400:
                # Try classic epic link field
                epic_field = self.get_epic_link_field()
                if epic_field:
                    payload = {"fields": {epic_field: epic_key}}
                    response = self.session.put(url, json=payload)

            response.raise_for_status()
            return True
        except Exception:
            return False

    # ==================== Bulk Operations ====================

    def bulk_create_issues(self, issues: List[Dict], batch_size: int = 50) -> List[Issue]:
        """
        Create multiple issues in bulk.

        Args:
            issues: List of issue dicts with keys:
                - summary (required)
                - description
                - issue_type (default: task)
                - parent_key
                - story_points
                - labels
                - assignee_id
            batch_size: Number of issues per API call (max 50)

        Returns:
            List of created Issue objects
        """
        if not self.enabled or not self.project_key:
            return []

        created_issues = []
        epic_field = self.get_epic_link_field()

        # Process in batches
        for i in range(0, len(issues), batch_size):
            batch = issues[i:i + batch_size]
            issue_updates = []

            for issue_data in batch:
                issue_type = issue_data.get("issue_type", "task")
                issue_type_id = self.issue_types.get(
                    issue_type.lower(),
                    self.issue_types.get("task")
                )

                fields = {
                    "project": {"key": self.project_key},
                    "summary": issue_data.get("summary", "Untitled"),
                    "issuetype": {"id": issue_type_id}
                }

                if issue_data.get("description"):
                    fields["description"] = {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": issue_data["description"]}]
                        }]
                    }

                if issue_data.get("story_points") and self.story_points_field:
                    fields[self.story_points_field] = issue_data["story_points"]

                if issue_data.get("labels"):
                    fields["labels"] = issue_data["labels"]

                if issue_data.get("assignee_id"):
                    fields["assignee"] = {"accountId": issue_data["assignee_id"]}

                if issue_data.get("parent_key"):
                    if issue_type.lower() == "subtask":
                        fields["parent"] = {"key": issue_data["parent_key"]}
                    elif epic_field:
                        fields[epic_field] = issue_data["parent_key"]
                    else:
                        fields["parent"] = {"key": issue_data["parent_key"]}

                issue_updates.append({"fields": fields})

            try:
                url = f"{self.site}/rest/api/3/issue/bulk"
                payload = {"issueUpdates": issue_updates}
                response = self.session.post(url, json=payload)
                response.raise_for_status()

                result = response.json()
                for item in result.get("issues", []):
                    issue = self.get_issue(item.get("key"))
                    if issue:
                        created_issues.append(issue)

            except Exception:
                # Fallback: create issues one by one
                for issue_data in batch:
                    issue = self.create_issue_with_parent(
                        summary=issue_data.get("summary", "Untitled"),
                        description=issue_data.get("description", ""),
                        issue_type=issue_data.get("issue_type", "task"),
                        parent_key=issue_data.get("parent_key"),
                        story_points=issue_data.get("story_points"),
                        labels=issue_data.get("labels"),
                        assignee_id=issue_data.get("assignee_id")
                    )
                    if issue:
                        created_issues.append(issue)

        return created_issues

    def bulk_assign_issues(self, assignments: Dict[str, str]) -> Dict[str, bool]:
        """
        Assign multiple issues to users.

        Args:
            assignments: Dict of {issue_key: account_id}

        Returns:
            Dict of {issue_key: success_bool}
        """
        if not self.enabled:
            return {}

        results = {}
        for issue_key, account_id in assignments.items():
            results[issue_key] = self.assign_issue(issue_key, account_id)

        return results

    def bulk_transition_issues(self, transitions: Dict[str, str]) -> Dict[str, bool]:
        """
        Transition multiple issues to new statuses.

        Args:
            transitions: Dict of {issue_key: target_status}

        Returns:
            Dict of {issue_key: success_bool}
        """
        if not self.enabled:
            return {}

        results = {}
        for issue_key, status in transitions.items():
            results[issue_key] = self.transition_issue(issue_key, status)

        return results

    # ==================== Sprint Management ====================

    def create_sprint(
        self,
        name: str,
        start_date: str = None,
        end_date: str = None,
        goal: str = None
    ) -> Optional[Sprint]:
        """
        Create a new sprint.

        Args:
            name: Sprint name
            start_date: ISO date string (e.g., "2024-01-15")
            end_date: ISO date string
            goal: Sprint goal description

        Returns:
            Created Sprint object or None
        """
        if not self.enabled or not self.board_id or self.board_type != "scrum":
            return None

        try:
            url = f"{self.site}/rest/agile/1.0/sprint"
            payload = {
                "name": name,
                "originBoardId": self.board_id
            }

            if start_date:
                payload["startDate"] = start_date
            if end_date:
                payload["endDate"] = end_date
            if goal:
                payload["goal"] = goal

            response = self.session.post(url, json=payload)
            response.raise_for_status()

            s = response.json()
            return Sprint(
                id=str(s["id"]),
                name=s.get("name", ""),
                state=s.get("state", "future"),
                start_date=s.get("startDate"),
                end_date=s.get("endDate"),
                goal=s.get("goal")
            )
        except Exception:
            return None

    def move_issues_to_sprint(self, issue_keys: List[str], sprint_id: str) -> bool:
        """
        Move multiple issues to a sprint.

        Args:
            issue_keys: List of issue keys to move
            sprint_id: Target sprint ID

        Returns:
            True if successful
        """
        if not self.enabled or not issue_keys:
            return False

        try:
            url = f"{self.site}/rest/agile/1.0/sprint/{sprint_id}/issue"
            payload = {"issues": issue_keys}
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def start_sprint(self, sprint_id: str, start_date: str = None, end_date: str = None) -> bool:
        """Start a sprint."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/agile/1.0/sprint/{sprint_id}"
            payload = {"state": "active"}
            if start_date:
                payload["startDate"] = start_date
            if end_date:
                payload["endDate"] = end_date

            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def close_sprint(self, sprint_id: str) -> bool:
        """Close/complete a sprint."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/agile/1.0/sprint/{sprint_id}"
            payload = {"state": "closed"}
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    # ==================== Labels & Custom Fields ====================

    def add_labels(self, issue_key: str, labels: List[str]) -> bool:
        """Add labels to an issue (preserves existing labels)."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}"
            payload = {
                "update": {
                    "labels": [{"add": label} for label in labels]
                }
            }
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def remove_labels(self, issue_key: str, labels: List[str]) -> bool:
        """Remove labels from an issue."""
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}"
            payload = {
                "update": {
                    "labels": [{"remove": label} for label in labels]
                }
            }
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def set_story_points(self, issue_key: str, points: float) -> bool:
        """Set story points for an issue."""
        if not self.enabled or not self.story_points_field:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}"
            payload = {"fields": {self.story_points_field: points}}
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def update_issue(self, issue_key: str, fields: Dict) -> bool:
        """
        Update issue fields.

        Args:
            issue_key: Issue to update
            fields: Dict of field_name -> value
                Supports: summary, description, labels, assignee, etc.

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        try:
            url = f"{self.site}/rest/api/3/issue/{issue_key}"

            # Transform fields to API format
            api_fields = {}
            for key, value in fields.items():
                if key == "description" and isinstance(value, str):
                    api_fields["description"] = {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": value}]
                        }]
                    }
                elif key == "assignee":
                    api_fields["assignee"] = {"accountId": value} if value else None
                else:
                    api_fields[key] = value

            payload = {"fields": api_fields}
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            return True
        except Exception:
            return False

    # ==================== Prompt Management ====================

    @classmethod
    def get_prompts(cls) -> Dict[str, Dict[str, any]]:
        """
        Get exportable prompts for Jira integration.

        Returns prompts that users can customize for issue creation and management.
        Response schemas are managed by RedGit and NOT included here.
        """
        return {
            "issue_title": {
                "description": "Generate Jira issue titles from code changes",
                "content": """# Jira Issue Title Generation

You are generating a Jira issue title based on code changes.

## Guidelines

1. **Title Style**: Clear, concise, and action-oriented
   - Use imperative mood: "Add", "Fix", "Update", "Refactor", "Remove"
   - Keep under 80 characters
   - Be specific about what was changed

2. **Language**: Write the title in {{ISSUE_LANGUAGE}}

3. **Examples by Language**:
   - English: "Add user authentication with JWT tokens"
   - Turkish: "JWT token ile kullanıcı kimlik doğrulaması ekle"
   - German: "Benutzerauthentifizierung mit JWT-Token hinzufügen"

## Code Changes

{{FILES}}

## Instructions

Generate a single, descriptive issue title in {{ISSUE_LANGUAGE}} that summarizes the main change.
""",
                "variables": ["FILES", "ISSUE_LANGUAGE"]
            },
            "issue_description": {
                "description": "Generate Jira issue descriptions from code changes",
                "content": """# Jira Issue Description Generation

You are generating a Jira issue description based on code changes.

## Guidelines

1. **Structure**:
   - Start with a brief summary (1-2 sentences)
   - List the main changes as bullet points
   - Mention any technical considerations
   - Note any dependencies or related changes

2. **Language**: Write the description in {{ISSUE_LANGUAGE}}

3. **Formatting**:
   - Use Jira wiki markup or plain text
   - Keep it concise but informative
   - Include file paths if relevant

## Code Changes

{{FILES}}

## Instructions

Generate a clear issue description in {{ISSUE_LANGUAGE}} that explains what was changed and why.
""",
                "variables": ["FILES", "ISSUE_LANGUAGE"]
            }
        }