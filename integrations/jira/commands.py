"""
Jira CLI commands - Project, team, and issue management.

Commands:
- rg jira projects     : List accessible projects
- rg jira issues       : List my active issues
- rg jira team         : List project team members
- rg jira assign       : Assign issue to team member
- rg jira unassigned   : List unassigned issues
- rg jira create       : Create a new issue
- rg jira link         : Link two issues
- rg jira epic         : Show epic and its children
- rg jira move-sprint  : Move issues to sprint
"""

import typer
from rich.console import Console
from rich.table import Table
from typing import Optional

try:
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import get_task_management
except ImportError:
    ConfigManager = None
    get_task_management = None

console = Console()
jira_app = typer.Typer(help="Jira project and team management")


def _get_jira():
    """Get configured Jira integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    jira = get_task_management(config, "jira")

    if not jira:
        console.print("[red]Jira integration not configured.[/red]")
        console.print("[dim]Run 'rg install jira' to set up[/dim]")
        raise typer.Exit(1)

    return jira


@jira_app.command("projects")
def list_projects():
    """List all accessible Jira projects."""
    jira = _get_jira()

    console.print("\n[bold cyan]Jira Projects[/bold cyan]\n")

    projects = jira.get_projects()
    if not projects:
        console.print("[yellow]No projects found or access denied.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Key", style="cyan")
    table.add_column("Name")
    table.add_column("Lead", style="dim")
    table.add_column("Type", style="dim")

    for p in projects:
        is_current = " *" if p["key"] == jira.project_key else ""
        table.add_row(
            p["key"] + is_current,
            p["name"],
            p.get("lead", "-"),
            p.get("style", "-")
        )

    console.print(table)
    console.print(f"\n[dim]* = Current project ({jira.project_key})[/dim]")


@jira_app.command("issues")
def list_issues(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status: active, done, or specific status"),
    all_issues: bool = typer.Option(False, "--all", "-a", help="Show all project issues, not just mine")
):
    """List my active issues in the current project."""
    jira = _get_jira()

    console.print(f"\n[bold cyan]Issues in {jira.project_key}[/bold cyan]\n")

    if all_issues:
        jql = f'project = "{jira.project_key}" ORDER BY updated DESC'
        issues = jira.search_issues(jql, 50)
        title = "All Issues"
    elif status:
        issues = jira.get_user_issues(status=status)
        title = f"My Issues ({status})"
    else:
        issues = jira.get_my_active_issues()
        title = "My Active Issues"

    if not issues:
        console.print(f"[yellow]No issues found.[/yellow]")
        return

    table = Table(title=title, show_header=True)
    table.add_column("Key", style="cyan")
    table.add_column("Type", style="dim", width=8)
    table.add_column("Summary")
    table.add_column("Status")
    table.add_column("Assignee", style="dim")

    for issue in issues:
        status_color = "green" if "progress" in issue.status.lower() else "yellow"
        table.add_row(
            issue.key,
            issue.issue_type[:8],
            issue.summary[:50] + ("..." if len(issue.summary) > 50 else ""),
            f"[{status_color}]{issue.status}[/{status_color}]",
            issue.assignee or "-"
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(issues)} issues[/dim]")


@jira_app.command("team")
def list_team():
    """List team members assignable to the current project."""
    jira = _get_jira()

    console.print(f"\n[bold cyan]Team - {jira.project_key}[/bold cyan]\n")

    users = jira.get_project_users()
    if not users:
        console.print("[yellow]No team members found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name")
    table.add_column("Email", style="dim")
    table.add_column("Status")

    for i, user in enumerate(users, 1):
        status = "[green]Active[/green]" if user.get("active") else "[red]Inactive[/red]"
        table.add_row(
            str(i),
            user.get("display_name", "-"),
            user.get("email", "-"),
            status
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(users)} members[/dim]")


@jira_app.command("unassigned")
def list_unassigned():
    """List unassigned issues in the current project."""
    jira = _get_jira()

    console.print(f"\n[bold cyan]Unassigned Issues - {jira.project_key}[/bold cyan]\n")

    issues = jira.get_unassigned_issues()
    if not issues:
        console.print("[green]No unassigned issues![/green]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Key", style="cyan")
    table.add_column("Type", style="dim", width=8)
    table.add_column("Summary")
    table.add_column("Status")

    for i, issue in enumerate(issues, 1):
        table.add_row(
            str(i),
            issue.key,
            issue.issue_type[:8],
            issue.summary[:50] + ("..." if len(issue.summary) > 50 else ""),
            issue.status
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(issues)} unassigned[/dim]")
    console.print("[dim]Use 'rg jira assign <issue> <user>' to assign[/dim]")


@jira_app.command("assign")
def assign_issue(
    issue_key: str = typer.Argument(..., help="Issue key (e.g., PROJ-123)"),
    user: Optional[str] = typer.Argument(None, help="User name or number from team list")
):
    """Assign an issue to a team member."""
    jira = _get_jira()

    # Get issue info
    issue = jira.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Issue {issue_key} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{issue_key}[/bold]: {issue.summary}")
    console.print(f"[dim]Type: {issue.issue_type} | Status: {issue.status}[/dim]")

    if issue.assignee:
        console.print(f"[yellow]Currently assigned to: {issue.assignee}[/yellow]")

    # Get team members
    users = jira.get_project_users()
    if not users:
        console.print("[red]No team members found.[/red]")
        raise typer.Exit(1)

    # If user not specified, show list and ask
    if not user:
        console.print("\n[bold]Team Members:[/bold]")
        for i, u in enumerate(users, 1):
            console.print(f"  [{i}] {u.get('display_name')}")

        user = typer.prompt("\nSelect team member (number or name)")

    # Find user by number or name
    account_id = None
    display_name = None
    try:
        idx = int(user) - 1
        if 0 <= idx < len(users):
            account_id = users[idx].get("account_id")
            display_name = users[idx].get("display_name")
    except ValueError:
        # Search by name
        user_lower = user.lower()
        for u in users:
            if user_lower in u.get("display_name", "").lower():
                account_id = u.get("account_id")
                display_name = u.get("display_name")
                break

    if not account_id:
        console.print(f"[red]User '{user}' not found.[/red]")
        raise typer.Exit(1)

    # Assign
    if jira.assign_issue(issue_key, account_id):
        console.print(f"\n[green]Assigned {issue_key} to {display_name}[/green]")
    else:
        console.print(f"[red]Failed to assign issue.[/red]")
        raise typer.Exit(1)


@jira_app.command("unassign")
def unassign_issue(
    issue_key: str = typer.Argument(..., help="Issue key (e.g., PROJ-123)")
):
    """Remove assignee from an issue."""
    jira = _get_jira()

    issue = jira.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Issue {issue_key} not found.[/red]")
        raise typer.Exit(1)

    if not issue.assignee:
        console.print(f"[yellow]{issue_key} is already unassigned.[/yellow]")
        return

    if jira.unassign_issue(issue_key):
        console.print(f"[green]Removed assignee from {issue_key}[/green]")
    else:
        console.print(f"[red]Failed to unassign issue.[/red]")
        raise typer.Exit(1)


@jira_app.command("sprint")
def show_sprint():
    """Show active sprint information."""
    jira = _get_jira()

    if not jira.supports_sprints():
        console.print("[yellow]Sprints not supported (board_type is not 'scrum')[/yellow]")
        return

    sprint = jira.get_active_sprint()
    if not sprint:
        console.print("[yellow]No active sprint found.[/yellow]")
        return

    console.print(f"\n[bold cyan]Active Sprint: {sprint.name}[/bold cyan]")
    if sprint.goal:
        console.print(f"[dim]Goal: {sprint.goal}[/dim]")
    console.print(f"[dim]{sprint.start_date} -> {sprint.end_date}[/dim]\n")

    # Get sprint issues
    issues = jira.get_sprint_issues(sprint.id)

    # Group by status
    by_status = {}
    for issue in issues:
        status = issue.status
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(issue)

    for status, status_issues in by_status.items():
        console.print(f"[bold]{status}[/bold] ({len(status_issues)})")
        for issue in status_issues:
            assignee = f" -> {issue.assignee}" if issue.assignee else ""
            console.print(f"  {issue.key}: {issue.summary[:40]}{assignee}")
        console.print("")


@jira_app.command("backlog")
def show_backlog(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum issues to show")
):
    """Show backlog issues."""
    jira = _get_jira()

    console.print(f"\n[bold cyan]Backlog - {jira.project_key}[/bold cyan]\n")

    issues = jira.get_backlog_issues(limit)
    if not issues:
        console.print("[green]Backlog is empty![/green]")
        return

    table = Table(show_header=True)
    table.add_column("Key", style="cyan")
    table.add_column("Type", style="dim", width=8)
    table.add_column("Summary")
    table.add_column("Points", style="dim", width=6)

    for issue in issues:
        points = str(issue.story_points) if issue.story_points else "-"
        table.add_row(
            issue.key,
            issue.issue_type[:8],
            issue.summary[:50] + ("..." if len(issue.summary) > 50 else ""),
            points
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(issues)} of backlog[/dim]")


@jira_app.command("create")
def create_issue(
    summary: str = typer.Argument(..., help="Issue summary/title"),
    issue_type: str = typer.Option("task", "--type", "-t", help="Issue type: epic, story, task, bug"),
    epic: Optional[str] = typer.Option(None, "--epic", "-e", help="Parent epic key"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Issue description"),
    points: Optional[float] = typer.Option(None, "--points", "-p", help="Story points"),
    labels: Optional[str] = typer.Option(None, "--labels", "-l", help="Comma-separated labels"),
    assignee: Optional[str] = typer.Option(None, "--assignee", "-a", help="Assignee name or number"),
    sprint: bool = typer.Option(False, "--sprint", "-s", help="Add to active sprint")
):
    """Create a new issue."""
    jira = _get_jira()

    console.print(f"\n[bold cyan]Creating {issue_type}...[/bold cyan]\n")

    # Parse labels
    label_list = [l.strip() for l in labels.split(",")] if labels else None

    # Find assignee account_id
    assignee_id = None
    if assignee:
        users = jira.get_project_users()
        try:
            idx = int(assignee) - 1
            if 0 <= idx < len(users):
                assignee_id = users[idx].get("account_id")
        except ValueError:
            for u in users:
                if assignee.lower() in u.get("display_name", "").lower():
                    assignee_id = u.get("account_id")
                    break

    # Create issue
    issue = jira.create_issue_with_parent(
        summary=summary,
        description=description or "",
        issue_type=issue_type,
        parent_key=epic,
        story_points=points,
        labels=label_list,
        assignee_id=assignee_id
    )

    if issue:
        console.print(f"[green]Created {issue.key}[/green]")
        console.print(f"  {issue.summary}")
        console.print(f"  [dim]{issue.url}[/dim]")

        # Add to sprint if requested
        if sprint:
            if jira.add_issue_to_active_sprint(issue.key):
                console.print(f"  [green]Added to active sprint[/green]")
            else:
                console.print(f"  [yellow]Could not add to sprint[/yellow]")
    else:
        console.print("[red]Failed to create issue.[/red]")
        raise typer.Exit(1)


@jira_app.command("link")
def link_issues_cmd(
    source: str = typer.Argument(..., help="Source issue key (e.g., PROJ-123)"),
    target: str = typer.Argument(..., help="Target issue key (e.g., PROJ-456)"),
    link_type: str = typer.Option("Blocks", "--type", "-t", help="Link type: Blocks, Relates, Duplicate, Clones")
):
    """Link two issues together."""
    jira = _get_jira()

    # Verify both issues exist
    source_issue = jira.get_issue(source)
    target_issue = jira.get_issue(target)

    if not source_issue:
        console.print(f"[red]Issue {source} not found.[/red]")
        raise typer.Exit(1)

    if not target_issue:
        console.print(f"[red]Issue {target} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Linking issues:[/bold]")
    console.print(f"  {source}: {source_issue.summary[:50]}")
    console.print(f"  {link_type.lower()}")
    console.print(f"  {target}: {target_issue.summary[:50]}")

    if jira.link_issues(source, target, link_type):
        console.print(f"\n[green]Link created successfully[/green]")
    else:
        console.print(f"[red]Failed to create link.[/red]")
        console.print("[dim]Check link type with 'rg jira link-types'[/dim]")
        raise typer.Exit(1)


@jira_app.command("link-types")
def show_link_types():
    """Show available issue link types."""
    jira = _get_jira()

    link_types = jira.get_link_types()
    if not link_types:
        console.print("[yellow]No link types found.[/yellow]")
        return

    console.print("\n[bold cyan]Available Link Types[/bold cyan]\n")

    table = Table(show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Outward")
    table.add_column("Inward")

    for lt in link_types:
        table.add_row(
            lt.get("name", ""),
            lt.get("outward", ""),
            lt.get("inward", "")
        )

    console.print(table)


@jira_app.command("epic")
def show_epic(
    epic_key: str = typer.Argument(..., help="Epic issue key (e.g., PROJ-100)")
):
    """Show epic and its child issues."""
    jira = _get_jira()

    # Get epic info
    epic = jira.get_issue(epic_key)
    if not epic:
        console.print(f"[red]Epic {epic_key} not found.[/red]")
        raise typer.Exit(1)

    if epic.issue_type.lower() != "epic":
        console.print(f"[yellow]{epic_key} is a {epic.issue_type}, not an Epic.[/yellow]")

    console.print(f"\n[bold cyan]Epic: {epic_key}[/bold cyan]")
    console.print(f"[bold]{epic.summary}[/bold]")
    console.print(f"[dim]Status: {epic.status}[/dim]\n")

    # Get child issues
    children = jira.get_epic_issues(epic_key)
    if not children:
        console.print("[yellow]No child issues found.[/yellow]")
        return

    # Group by type
    by_type = {}
    for issue in children:
        t = issue.issue_type
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(issue)

    total_points = 0
    for issue_type, issues in by_type.items():
        console.print(f"[bold]{issue_type}s[/bold] ({len(issues)})")
        for issue in issues:
            status_color = "green" if "done" in issue.status.lower() else "yellow"
            points = f" [{issue.story_points}p]" if issue.story_points else ""
            if issue.story_points:
                total_points += issue.story_points
            console.print(f"  [{status_color}]o[/{status_color}] {issue.key}: {issue.summary[:40]}{points}")
        console.print("")

    console.print(f"[dim]Total: {len(children)} issues, {total_points} story points[/dim]")


@jira_app.command("links")
def show_issue_links(
    issue_key: str = typer.Argument(..., help="Issue key (e.g., PROJ-123)")
):
    """Show issue links/dependencies."""
    jira = _get_jira()

    issue = jira.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Issue {issue_key} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Links for {issue_key}[/bold cyan]")
    console.print(f"[dim]{issue.summary}[/dim]\n")

    links = jira.get_issue_links(issue_key)
    if not links:
        console.print("[yellow]No links found.[/yellow]")
        return

    # Group by relation
    by_relation = {}
    for link in links:
        rel = link.get("relation", "related")
        if rel not in by_relation:
            by_relation[rel] = []
        by_relation[rel].append(link)

    for relation, rel_links in by_relation.items():
        console.print(f"[bold]{relation}[/bold]")
        for link in rel_links:
            console.print(f"  {link['issue_key']}: {link['issue_summary'][:40]}")
        console.print("")


@jira_app.command("move-sprint")
def move_to_sprint(
    issues: str = typer.Argument(..., help="Issue keys (comma-separated, e.g., PROJ-1,PROJ-2)"),
    sprint_id: Optional[str] = typer.Option(None, "--sprint", "-s", help="Target sprint ID (default: active)"),
    future: bool = typer.Option(False, "--future", "-f", help="Move to next future sprint")
):
    """Move issues to a sprint."""
    jira = _get_jira()

    if not jira.supports_sprints():
        console.print("[yellow]Sprints not supported (board_type is not 'scrum')[/yellow]")
        raise typer.Exit(1)

    # Parse issue keys
    issue_keys = [k.strip() for k in issues.split(",")]

    # Determine target sprint
    target_sprint = None
    sprint_name = None
    if sprint_id:
        target_sprint = sprint_id
        sprint_name = f"Sprint {sprint_id}"
    elif future:
        sprints = jira.get_future_sprints()
        if sprints:
            target_sprint = sprints[0].id
            sprint_name = sprints[0].name
        else:
            console.print("[yellow]No future sprints found.[/yellow]")
            raise typer.Exit(1)
    else:
        sprint = jira.get_active_sprint()
        if sprint:
            target_sprint = sprint.id
            sprint_name = sprint.name
        else:
            console.print("[yellow]No active sprint found.[/yellow]")
            raise typer.Exit(1)

    console.print(f"\n[bold]Moving {len(issue_keys)} issues to {sprint_name}[/bold]\n")

    if jira.move_issues_to_sprint(issue_keys, target_sprint):
        console.print(f"[green]Moved {len(issue_keys)} issues to sprint[/green]")
        for key in issue_keys:
            console.print(f"  {key}")
    else:
        console.print("[red]Failed to move issues.[/red]")
        raise typer.Exit(1)


@jira_app.command("sprints")
def list_sprints():
    """List all sprints (active and future)."""
    jira = _get_jira()

    if not jira.supports_sprints():
        console.print("[yellow]Sprints not supported (board_type is not 'scrum')[/yellow]")
        return

    console.print(f"\n[bold cyan]Sprints - {jira.project_key}[/bold cyan]\n")

    # Active sprint
    active = jira.get_active_sprint()
    if active:
        console.print("[bold green]* Active Sprint[/bold green]")
        console.print(f"  {active.name} (ID: {active.id})")
        if active.goal:
            console.print(f"  [dim]Goal: {active.goal}[/dim]")
        console.print(f"  [dim]{active.start_date} -> {active.end_date}[/dim]\n")

    # Future sprints
    future = jira.get_future_sprints()
    if future:
        console.print("[bold yellow]o Future Sprints[/bold yellow]")
        for sprint in future:
            console.print(f"  {sprint.name} (ID: {sprint.id})")
            if sprint.start_date:
                console.print(f"  [dim]{sprint.start_date} -> {sprint.end_date}[/dim]")


@jira_app.command("create-sprint")
def create_sprint_cmd(
    name: str = typer.Argument(..., help="Sprint name"),
    goal: Optional[str] = typer.Option(None, "--goal", "-g", help="Sprint goal"),
    start: Optional[str] = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, "--end", help="End date (YYYY-MM-DD)")
):
    """Create a new sprint."""
    jira = _get_jira()

    if not jira.supports_sprints():
        console.print("[yellow]Sprints not supported (board_type is not 'scrum')[/yellow]")
        raise typer.Exit(1)

    sprint = jira.create_sprint(name, start, end, goal)
    if sprint:
        console.print(f"\n[green]Created sprint: {sprint.name}[/green]")
        console.print(f"  [dim]ID: {sprint.id}[/dim]")
        console.print(f"  [dim]State: {sprint.state}[/dim]")
    else:
        console.print("[red]Failed to create sprint.[/red]")
        raise typer.Exit(1)