"""
Linear integration for RedGit.

Implements TaskManagementBase for Linear GraphQL API.
Linear is a modern issue tracking tool for software teams.
"""

import os
import json
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

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


class LinearIntegration(TaskManagementBase):
    """Linear integration - Modern issue tracking with cycles and projects"""

    name = "linear"
    integration_type = IntegrationType.TASK_MANAGEMENT

    # Linear API endpoint
    API_URL = "https://api.linear.app/graphql"

    # Default status mappings
    DEFAULT_STATUS_MAP = {
        "todo": ["Todo", "Backlog", "Triage"],
        "in_progress": ["In Progress", "In Review", "Started"],
        "done": ["Done", "Completed", "Canceled"]
    }

    def __init__(self):
        super().__init__()
        self.api_key = ""
        self.team_id = ""
        self.team_key = ""  # Team identifier (e.g., "ENG")
        self.project_key = ""  # For compatibility
        self.status_map = self.DEFAULT_STATUS_MAP.copy()
        self.branch_pattern = "feature/{issue_id}-{description}"
        self.commit_prefix = ""
        self.default_state_id = None  # Default state for new issues
        self._me = None  # Cached current user

    def setup(self, config: dict):
        """
        Setup Linear connection.

        Config example (.redgit/config.yaml):
            integrations:
              linear:
                api_key: "lin_api_xxx"  # or LINEAR_API_KEY env var
                team_key: "ENG"  # Team identifier
                # Optional:
                branch_pattern: "feature/{issue_id}-{description}"
                statuses:
                  in_progress: ["In Progress", "Started"]
                  done: ["Done", "Completed"]
        """
        self.api_key = config.get("api_key") or os.getenv("LINEAR_API_KEY", "")
        self.team_key = config.get("team_key", "")
        self.project_key = self.team_key  # Alias for compatibility

        # Override status mappings if provided
        if config.get("statuses"):
            for key, values in config["statuses"].items():
                if isinstance(values, list):
                    self.status_map[key] = values
                elif isinstance(values, str):
                    self.status_map[key] = [values]

        # Branch pattern
        self.branch_pattern = config.get(
            "branch_pattern",
            "feature/{issue_id}-{description}"
        )
        self.commit_prefix = config.get("commit_prefix", self.team_key)

        if not self.api_key:
            self.enabled = False
            return

        # Verify connection and get team ID
        try:
            me = self._get_me()
            if me:
                self._me = me
                # Get team ID from team key
                if self.team_key:
                    self.team_id = self._get_team_id(self.team_key)
                self.enabled = bool(self.team_id)
            else:
                self.enabled = False
        except Exception:
            self.enabled = False

    def _graphql(self, query: str, variables: dict = None) -> Optional[dict]:
        """Execute a GraphQL query against Linear API."""
        if not self.api_key:
            return None

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                self.API_URL,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self.api_key,
                },
                method="POST"
            )
            with urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                if "errors" in result:
                    return None
                return result.get("data")
        except (HTTPError, URLError, json.JSONDecodeError):
            return None

    def _get_me(self) -> Optional[dict]:
        """Get current user info."""
        query = """
        query {
            viewer {
                id
                name
                email
            }
        }
        """
        data = self._graphql(query)
        return data.get("viewer") if data else None

    def _get_team_id(self, team_key: str) -> Optional[str]:
        """Get team ID from team key."""
        query = """
        query($key: String!) {
            teams(filter: { key: { eq: $key } }) {
                nodes {
                    id
                    key
                    name
                }
            }
        }
        """
        data = self._graphql(query, {"key": team_key})
        if data:
            teams = data.get("teams", {}).get("nodes", [])
            if teams:
                return teams[0].get("id")
        return None

    # ==================== TaskManagementBase Implementation ====================

    def get_my_active_issues(self) -> List[Issue]:
        """Get issues assigned to current user that are active."""
        if not self.enabled or not self._me:
            return []

        query = """
        query($userId: String!, $teamId: String!) {
            issues(
                filter: {
                    assignee: { id: { eq: $userId } }
                    team: { id: { eq: $teamId } }
                    state: { type: { nin: ["completed", "canceled"] } }
                }
                orderBy: updatedAt
                first: 50
            ) {
                nodes {
                    id
                    identifier
                    title
                    description
                    state { name }
                    assignee { name email }
                    estimate
                    url
                    labels { nodes { name } }
                    cycle { id name }
                }
            }
        }
        """
        data = self._graphql(query, {
            "userId": self._me["id"],
            "teamId": self.team_id
        })

        if not data:
            return []

        return [self._parse_issue(node) for node in data.get("issues", {}).get("nodes", [])]

    def get_issue(self, issue_key: str) -> Optional[Issue]:
        """Get a single issue by identifier (e.g., ENG-123)."""
        if not self.enabled:
            return None

        query = """
        query($identifier: String!) {
            issue(id: $identifier) {
                id
                identifier
                title
                description
                state { name }
                assignee { name email }
                estimate
                url
                labels { nodes { name } }
                cycle { id name }
                parent { identifier title }
                children { nodes { identifier title state { name } } }
            }
        }
        """
        # Try with identifier format (ENG-123)
        data = self._graphql(query, {"identifier": issue_key})

        if not data or not data.get("issue"):
            # Try searching by identifier
            search_query = """
            query($filter: IssueFilter!) {
                issues(filter: $filter, first: 1) {
                    nodes {
                        id
                        identifier
                        title
                        description
                        state { name }
                        assignee { name email }
                        estimate
                        url
                        labels { nodes { name } }
                        cycle { id name }
                    }
                }
            }
            """
            data = self._graphql(search_query, {
                "filter": {"identifier": {"eq": issue_key}}
            })
            if data:
                nodes = data.get("issues", {}).get("nodes", [])
                if nodes:
                    return self._parse_issue(nodes[0])
            return None

        return self._parse_issue(data["issue"])

    def create_issue(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        story_points: Optional[float] = None,
        assign_to_me: bool = True
    ) -> Optional[str]:
        """Create a new issue in the team."""
        if not self.enabled or not self.team_id:
            return None

        mutation = """
        mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    identifier
                }
            }
        }
        """

        input_data = {
            "teamId": self.team_id,
            "title": summary,
        }

        if description:
            input_data["description"] = description

        if story_points is not None:
            input_data["estimate"] = int(story_points)

        if assign_to_me and self._me:
            input_data["assigneeId"] = self._me["id"]

        # Add to active cycle if exists
        cycle = self.get_active_sprint()
        if cycle:
            input_data["cycleId"] = cycle.id

        data = self._graphql(mutation, {"input": input_data})

        if data and data.get("issueCreate", {}).get("success"):
            return data["issueCreate"]["issue"]["identifier"]

        return None

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add comment to Linear issue."""
        if not self.enabled:
            return False

        # First get the issue ID
        issue = self._get_issue_id(issue_key)
        if not issue:
            return False

        mutation = """
        mutation($input: CommentCreateInput!) {
            commentCreate(input: $input) {
                success
            }
        }
        """

        data = self._graphql(mutation, {
            "input": {
                "issueId": issue,
                "body": comment
            }
        })

        return data and data.get("commentCreate", {}).get("success", False)

    def transition_issue(self, issue_key: str, status: str) -> bool:
        """Change issue status."""
        if not self.enabled:
            return False

        issue_id = self._get_issue_id(issue_key)
        if not issue_id:
            return False

        # Get state ID for the status
        state_id = self._get_state_id(status)
        if not state_id:
            return False

        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
            }
        }
        """

        data = self._graphql(mutation, {
            "id": issue_id,
            "input": {"stateId": state_id}
        })

        return data and data.get("issueUpdate", {}).get("success", False)

    def format_branch_name(self, issue_key: str, description: str) -> str:
        """Format branch name using the configured pattern."""
        # Clean description for branch name
        clean_desc = description.lower()
        clean_desc = "".join(c if c.isalnum() or c == " " else "" for c in clean_desc)
        clean_desc = clean_desc.strip().replace(" ", "-")[:40]

        # Extract issue number
        issue_number = issue_key.split("-")[-1] if "-" in issue_key else issue_key

        return self.branch_pattern.format(
            issue_key=issue_key,
            issue_id=issue_key,
            issue_number=issue_number,
            description=clean_desc,
            team_key=self.team_key
        )

    def get_commit_prefix(self) -> str:
        """Get prefix for commit messages."""
        return self.commit_prefix or self.team_key

    # ==================== Cycle (Sprint) Support ====================

    def supports_sprints(self) -> bool:
        """Linear supports cycles (similar to sprints)."""
        return True

    def get_active_sprint(self) -> Optional[Sprint]:
        """Get the active cycle for the team."""
        if not self.enabled or not self.team_id:
            return None

        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                activeCycle {
                    id
                    name
                    number
                    startsAt
                    endsAt
                }
            }
        }
        """
        data = self._graphql(query, {"teamId": self.team_id})

        if data and data.get("team", {}).get("activeCycle"):
            c = data["team"]["activeCycle"]
            return Sprint(
                id=c["id"],
                name=c.get("name") or f"Cycle {c.get('number', '')}",
                state="active",
                start_date=c.get("startsAt"),
                end_date=c.get("endsAt"),
                goal=None
            )
        return None

    def get_sprint_issues(self, sprint_id: str = None) -> List[Issue]:
        """Get issues in a cycle."""
        if not self.enabled:
            return []

        if sprint_id is None:
            cycle = self.get_active_sprint()
            if not cycle:
                return []
            sprint_id = cycle.id

        query = """
        query($cycleId: String!) {
            cycle(id: $cycleId) {
                issues {
                    nodes {
                        id
                        identifier
                        title
                        description
                        state { name }
                        assignee { name email }
                        estimate
                        url
                        labels { nodes { name } }
                    }
                }
            }
        }
        """
        data = self._graphql(query, {"cycleId": sprint_id})

        if not data:
            return []

        return [
            self._parse_issue(node)
            for node in data.get("cycle", {}).get("issues", {}).get("nodes", [])
        ]

    def add_issue_to_sprint(self, issue_key: str, sprint_id: str) -> bool:
        """Add issue to a cycle."""
        if not self.enabled:
            return False

        issue_id = self._get_issue_id(issue_key)
        if not issue_id:
            return False

        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
            }
        }
        """

        data = self._graphql(mutation, {
            "id": issue_id,
            "input": {"cycleId": sprint_id}
        })

        return data and data.get("issueUpdate", {}).get("success", False)

    # ==================== Linear-specific Methods ====================

    def get_teams(self) -> List[Dict]:
        """Get all teams the user has access to."""
        if not self.enabled:
            return []

        query = """
        query {
            teams {
                nodes {
                    id
                    key
                    name
                    description
                }
            }
        }
        """
        data = self._graphql(query)

        if not data:
            return []

        return [
            {
                "id": t["id"],
                "key": t["key"],
                "name": t["name"],
                "description": t.get("description", "")
            }
            for t in data.get("teams", {}).get("nodes", [])
        ]

    def get_projects(self) -> List[Dict]:
        """Get projects in the team."""
        if not self.enabled or not self.team_id:
            return []

        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                projects {
                    nodes {
                        id
                        name
                        description
                        state
                        url
                    }
                }
            }
        }
        """
        data = self._graphql(query, {"teamId": self.team_id})

        if not data:
            return []

        return [
            {
                "id": p["id"],
                "name": p["name"],
                "description": p.get("description", ""),
                "state": p.get("state", ""),
                "url": p.get("url", "")
            }
            for p in data.get("team", {}).get("projects", {}).get("nodes", [])
        ]

    def get_team_members(self) -> List[Dict]:
        """Get team members."""
        if not self.enabled or not self.team_id:
            return []

        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                members {
                    nodes {
                        id
                        name
                        email
                        active
                    }
                }
            }
        }
        """
        data = self._graphql(query, {"teamId": self.team_id})

        if not data:
            return []

        return [
            {
                "id": m["id"],
                "name": m["name"],
                "email": m.get("email", ""),
                "active": m.get("active", True)
            }
            for m in data.get("team", {}).get("members", {}).get("nodes", [])
        ]

    def get_workflow_states(self) -> List[Dict]:
        """Get workflow states for the team."""
        if not self.enabled or not self.team_id:
            return []

        query = """
        query($teamId: String!) {
            workflowStates(filter: { team: { id: { eq: $teamId } } }) {
                nodes {
                    id
                    name
                    type
                    position
                }
            }
        }
        """
        data = self._graphql(query, {"teamId": self.team_id})

        if not data:
            return []

        return [
            {
                "id": s["id"],
                "name": s["name"],
                "type": s.get("type", ""),
                "position": s.get("position", 0)
            }
            for s in data.get("workflowStates", {}).get("nodes", [])
        ]

    def get_cycles(self) -> List[Sprint]:
        """Get all cycles for the team."""
        if not self.enabled or not self.team_id:
            return []

        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                cycles(orderBy: startsAt, first: 20) {
                    nodes {
                        id
                        name
                        number
                        startsAt
                        endsAt
                    }
                }
            }
        }
        """
        data = self._graphql(query, {"teamId": self.team_id})

        if not data:
            return []

        cycles = []
        active_cycle = self.get_active_sprint()
        active_id = active_cycle.id if active_cycle else None

        for c in data.get("team", {}).get("cycles", {}).get("nodes", []):
            state = "active" if c["id"] == active_id else "future"
            cycles.append(Sprint(
                id=c["id"],
                name=c.get("name") or f"Cycle {c.get('number', '')}",
                state=state,
                start_date=c.get("startsAt"),
                end_date=c.get("endsAt"),
                goal=None
            ))

        return cycles

    def get_backlog_issues(self, max_results: int = 50) -> List[Issue]:
        """Get issues not in any cycle (backlog)."""
        if not self.enabled or not self.team_id:
            return []

        query = """
        query($teamId: String!, $first: Int!) {
            issues(
                filter: {
                    team: { id: { eq: $teamId } }
                    cycle: { null: true }
                    state: { type: { nin: ["completed", "canceled"] } }
                }
                first: $first
                orderBy: createdAt
            ) {
                nodes {
                    id
                    identifier
                    title
                    description
                    state { name }
                    assignee { name email }
                    estimate
                    url
                    labels { nodes { name } }
                }
            }
        }
        """
        data = self._graphql(query, {"teamId": self.team_id, "first": max_results})

        if not data:
            return []

        return [
            self._parse_issue(node)
            for node in data.get("issues", {}).get("nodes", [])
        ]

    def get_unassigned_issues(self, max_results: int = 50) -> List[Issue]:
        """Get unassigned issues in the team."""
        if not self.enabled or not self.team_id:
            return []

        query = """
        query($teamId: String!, $first: Int!) {
            issues(
                filter: {
                    team: { id: { eq: $teamId } }
                    assignee: { null: true }
                    state: { type: { nin: ["completed", "canceled"] } }
                }
                first: $first
                orderBy: createdAt
            ) {
                nodes {
                    id
                    identifier
                    title
                    description
                    state { name }
                    estimate
                    url
                    labels { nodes { name } }
                }
            }
        }
        """
        data = self._graphql(query, {"teamId": self.team_id, "first": max_results})

        if not data:
            return []

        return [
            self._parse_issue(node)
            for node in data.get("issues", {}).get("nodes", [])
        ]

    def assign_issue(self, issue_key: str, user_id: str) -> bool:
        """Assign an issue to a user."""
        if not self.enabled:
            return False

        issue_id = self._get_issue_id(issue_key)
        if not issue_id:
            return False

        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
            }
        }
        """

        data = self._graphql(mutation, {
            "id": issue_id,
            "input": {"assigneeId": user_id}
        })

        return data and data.get("issueUpdate", {}).get("success", False)

    def unassign_issue(self, issue_key: str) -> bool:
        """Remove assignee from an issue."""
        if not self.enabled:
            return False

        issue_id = self._get_issue_id(issue_key)
        if not issue_id:
            return False

        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
            }
        }
        """

        data = self._graphql(mutation, {
            "id": issue_id,
            "input": {"assigneeId": None}
        })

        return data and data.get("issueUpdate", {}).get("success", False)

    def search_issues(self, query_text: str, max_results: int = 50) -> List[Issue]:
        """Search issues by text."""
        if not self.enabled or not self.team_id:
            return []

        query = """
        query($teamId: String!, $search: String!, $first: Int!) {
            issues(
                filter: {
                    team: { id: { eq: $teamId } }
                    or: [
                        { title: { contains: $search } }
                        { description: { contains: $search } }
                    ]
                }
                first: $first
                orderBy: updatedAt
            ) {
                nodes {
                    id
                    identifier
                    title
                    description
                    state { name }
                    assignee { name email }
                    estimate
                    url
                    labels { nodes { name } }
                }
            }
        }
        """
        data = self._graphql(query, {
            "teamId": self.team_id,
            "search": query_text,
            "first": max_results
        })

        if not data:
            return []

        return [
            self._parse_issue(node)
            for node in data.get("issues", {}).get("nodes", [])
        ]

    def get_labels(self) -> List[Dict]:
        """Get available labels for the team."""
        if not self.enabled or not self.team_id:
            return []

        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                labels {
                    nodes {
                        id
                        name
                        color
                    }
                }
            }
        }
        """
        data = self._graphql(query, {"teamId": self.team_id})

        if not data:
            return []

        return [
            {
                "id": l["id"],
                "name": l["name"],
                "color": l.get("color", "")
            }
            for l in data.get("team", {}).get("labels", {}).get("nodes", [])
        ]

    def add_labels(self, issue_key: str, label_ids: List[str]) -> bool:
        """Add labels to an issue."""
        if not self.enabled:
            return False

        issue_id = self._get_issue_id(issue_key)
        if not issue_id:
            return False

        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
            }
        }
        """

        data = self._graphql(mutation, {
            "id": issue_id,
            "input": {"labelIds": label_ids}
        })

        return data and data.get("issueUpdate", {}).get("success", False)

    def set_estimate(self, issue_key: str, points: int) -> bool:
        """Set estimate (story points) for an issue."""
        if not self.enabled:
            return False

        issue_id = self._get_issue_id(issue_key)
        if not issue_id:
            return False

        mutation = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
            }
        }
        """

        data = self._graphql(mutation, {
            "id": issue_id,
            "input": {"estimate": points}
        })

        return data and data.get("issueUpdate", {}).get("success", False)

    def create_issue_with_parent(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "task",
        parent_key: str = None,
        story_points: Optional[float] = None,
        labels: List[str] = None,
        assignee_id: str = None
    ) -> Optional[Issue]:
        """Create an issue with optional parent."""
        if not self.enabled or not self.team_id:
            return None

        mutation = """
        mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                }
            }
        }
        """

        input_data = {
            "teamId": self.team_id,
            "title": summary,
        }

        if description:
            input_data["description"] = description

        if story_points is not None:
            input_data["estimate"] = int(story_points)

        if assignee_id:
            input_data["assigneeId"] = assignee_id
        elif self._me:
            input_data["assigneeId"] = self._me["id"]

        if parent_key:
            parent_id = self._get_issue_id(parent_key)
            if parent_id:
                input_data["parentId"] = parent_id

        if labels:
            # Get label IDs from names
            all_labels = self.get_labels()
            label_ids = []
            for label_name in labels:
                for l in all_labels:
                    if l["name"].lower() == label_name.lower():
                        label_ids.append(l["id"])
                        break
            if label_ids:
                input_data["labelIds"] = label_ids

        # Add to active cycle
        cycle = self.get_active_sprint()
        if cycle:
            input_data["cycleId"] = cycle.id

        data = self._graphql(mutation, {"input": input_data})

        if data and data.get("issueCreate", {}).get("success"):
            issue_data = data["issueCreate"]["issue"]
            return self.get_issue(issue_data["identifier"])

        return None

    def link_issues(self, source_key: str, target_key: str, link_type: str = "blocks") -> bool:
        """Create a relation between two issues."""
        if not self.enabled:
            return False

        source_id = self._get_issue_id(source_key)
        target_id = self._get_issue_id(target_key)

        if not source_id or not target_id:
            return False

        mutation = """
        mutation($input: IssueRelationCreateInput!) {
            issueRelationCreate(input: $input) {
                success
            }
        }
        """

        # Map link types
        relation_type = "blocks"  # Default
        if link_type.lower() in ["related", "relates"]:
            relation_type = "related"
        elif link_type.lower() in ["duplicate", "duplicates"]:
            relation_type = "duplicate"

        data = self._graphql(mutation, {
            "input": {
                "issueId": source_id,
                "relatedIssueId": target_id,
                "type": relation_type
            }
        })

        return data and data.get("issueRelationCreate", {}).get("success", False)

    def get_issue_relations(self, issue_key: str) -> List[Dict]:
        """Get relations for an issue."""
        if not self.enabled:
            return []

        issue_id = self._get_issue_id(issue_key)
        if not issue_id:
            return []

        query = """
        query($id: String!) {
            issue(id: $id) {
                relations {
                    nodes {
                        type
                        relatedIssue {
                            identifier
                            title
                            state { name }
                        }
                    }
                }
            }
        }
        """
        data = self._graphql(query, {"id": issue_id})

        if not data:
            return []

        relations = []
        for r in data.get("issue", {}).get("relations", {}).get("nodes", []):
            related = r.get("relatedIssue", {})
            relations.append({
                "type": r.get("type", ""),
                "issue_key": related.get("identifier", ""),
                "summary": related.get("title", ""),
                "status": related.get("state", {}).get("name", "")
            })

        return relations

    def get_child_issues(self, parent_key: str) -> List[Issue]:
        """Get child issues (sub-issues) of a parent."""
        if not self.enabled:
            return []

        parent_id = self._get_issue_id(parent_key)
        if not parent_id:
            return []

        query = """
        query($id: String!) {
            issue(id: $id) {
                children {
                    nodes {
                        id
                        identifier
                        title
                        description
                        state { name }
                        assignee { name email }
                        estimate
                        url
                        labels { nodes { name } }
                    }
                }
            }
        }
        """
        data = self._graphql(query, {"id": parent_id})

        if not data:
            return []

        return [
            self._parse_issue(node)
            for node in data.get("issue", {}).get("children", {}).get("nodes", [])
        ]

    # ==================== Hooks ====================

    def on_commit(self, group: dict, context: dict):
        """Add comment to Linear issue after commit."""
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

    # ==================== Internal Helpers ====================

    def _get_issue_id(self, issue_key: str) -> Optional[str]:
        """Get Linear internal ID from issue identifier."""
        query = """
        query($filter: IssueFilter!) {
            issues(filter: $filter, first: 1) {
                nodes {
                    id
                }
            }
        }
        """
        data = self._graphql(query, {
            "filter": {"identifier": {"eq": issue_key}}
        })

        if data:
            nodes = data.get("issues", {}).get("nodes", [])
            if nodes:
                return nodes[0]["id"]
        return None

    def _get_state_id(self, status_name: str) -> Optional[str]:
        """Get state ID from status name."""
        states = self.get_workflow_states()

        # Try exact match first
        for state in states:
            if state["name"].lower() == status_name.lower():
                return state["id"]

        # Try mapped status
        status_lower = status_name.lower().replace(" ", "_")
        if status_lower in self.status_map:
            for mapped_name in self.status_map[status_lower]:
                for state in states:
                    if state["name"].lower() == mapped_name.lower():
                        return state["id"]

        # Try partial match
        for state in states:
            if status_name.lower() in state["name"].lower():
                return state["id"]

        return None

    def _parse_issue(self, data: dict) -> Issue:
        """Parse Linear API response to Issue object."""
        assignee = None
        assignee_data = data.get("assignee")
        if assignee_data:
            assignee = assignee_data.get("name") or assignee_data.get("email")

        labels = []
        labels_data = data.get("labels", {}).get("nodes", [])
        for l in labels_data:
            labels.append(l.get("name", ""))

        # Get cycle/sprint name
        sprint = None
        cycle_data = data.get("cycle")
        if cycle_data:
            sprint = cycle_data.get("name")

        return Issue(
            key=data.get("identifier", ""),
            summary=data.get("title", ""),
            description=data.get("description", "") or "",
            status=data.get("state", {}).get("name", "Unknown"),
            issue_type="issue",  # Linear doesn't have explicit types like Jira
            assignee=assignee,
            url=data.get("url", ""),
            sprint=sprint,
            story_points=data.get("estimate"),
            labels=labels if labels else None
        )

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Hook called after Linear integration install."""
        import typer

        api_key = config_values.get("api_key", "")
        team_key = config_values.get("team_key", "")

        if not api_key:
            return config_values

        typer.echo("\n   Verifying Linear connection...")

        # Create temp instance to verify
        temp = LinearIntegration()
        temp.api_key = api_key

        me = temp._get_me()
        if me:
            typer.secho(f"   Logged in as: {me.get('name', 'Unknown')}", fg=typer.colors.GREEN)

            # List available teams if no team_key
            if not team_key:
                teams = temp.get_teams()
                if teams:
                    typer.echo("\n   Available teams:")
                    for t in teams:
                        typer.echo(f"     - {t['key']}: {t['name']}")
                    typer.echo("\n   Set 'team_key' in config to use a specific team")
        else:
            typer.secho("   Failed to verify API key", fg=typer.colors.RED)

        return config_values