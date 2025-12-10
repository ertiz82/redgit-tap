"""
Linear CLI commands - Team, cycle, and issue management.

Commands:
- rg linear teams      : List accessible teams
- rg linear issues     : List my active issues
- rg linear team       : List team members
- rg linear assign     : Assign issue to team member
- rg linear unassigned : List unassigned issues
- rg linear create     : Create a new issue
- rg linear link       : Link two issues
- rg linear cycle      : Show active cycle
- rg linear cycles     : List all cycles
- rg linear backlog    : Show backlog issues
- rg linear states     : Show workflow states
- rg linear labels     : Show available labels
"""

import typer
from rich.console import Console
from rich.table import Table
from typing import Optional, List

try:
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import get_task_management
except ImportError:
    # Fallback for standalone testing
    ConfigManager = None
    get_task_management = None

console = Console()
linear_app = typer.Typer(help="Linear issue tracking management")


def _get_linear():
    """Get configured Linear integration"""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    linear = get_task_management(config, "linear")

    if not linear:
        console.print("[red]Linear integration not configured.[/red]")
        console.print("[dim]Run 'rg install linear' to set up[/dim]")
        raise typer.Exit(1)

    return linear


@linear_app.command("teams")
def list_teams():
    """List all accessible Linear teams."""
    linear = _get_linear()

    console.print("\n[bold cyan]Linear Teams[/bold cyan]\n")

    teams = linear.get_teams()
    if not teams:
        console.print("[yellow]No teams found or access denied.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Key", style="cyan")
    table.add_column("Name")
    table.add_column("Description", style="dim")

    for t in teams:
        is_current = " *" if t["key"] == linear.team_key else ""
        table.add_row(
            t["key"] + is_current,
            t["name"],
            (t.get("description", "") or "-")[:50]
        )

    console.print(table)
    console.print(f"\n[dim]Current team: {linear.team_key}[/dim]")


@linear_app.command("issues")
def list_issues(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    all_issues: bool = typer.Option(False, "--all", "-a", help="Show all team issues")
):
    """List my active issues in the current team."""
    linear = _get_linear()

    console.print(f"\n[bold cyan]Issues - {linear.team_key}[/bold cyan]\n")

    if all_issues:
        issues = linear.search_issues("", 50)
        title = "All Issues"
    else:
        issues = linear.get_my_active_issues()
        title = "My Active Issues"

    if not issues:
        console.print("[yellow]No issues found.[/yellow]")
        return

    table = Table(title=title, show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Summary")
    table.add_column("Status")
    table.add_column("Assignee", style="dim")
    table.add_column("Est", style="dim", width=4)

    for issue in issues:
        status_color = "green" if "progress" in issue.status.lower() else "yellow"
        est = str(issue.story_points) if issue.story_points else "-"
        table.add_row(
            issue.key,
            issue.summary[:45] + ("..." if len(issue.summary) > 45 else ""),
            f"[{status_color}]{issue.status}[/{status_color}]",
            issue.assignee or "-",
            est
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(issues)} issues[/dim]")


@linear_app.command("team")
def list_team_members():
    """List team members."""
    linear = _get_linear()

    console.print(f"\n[bold cyan]Team Members - {linear.team_key}[/bold cyan]\n")

    members = linear.get_team_members()
    if not members:
        console.print("[yellow]No team members found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name")
    table.add_column("Email", style="dim")
    table.add_column("Status")

    for i, member in enumerate(members, 1):
        status = "[green]Active[/green]" if member.get("active") else "[red]Inactive[/red]"
        table.add_row(
            str(i),
            member.get("name", "-"),
            member.get("email", "-"),
            status
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(members)} members[/dim]")


@linear_app.command("unassigned")
def list_unassigned():
    """List unassigned issues in the team."""
    linear = _get_linear()

    console.print(f"\n[bold cyan]Unassigned Issues - {linear.team_key}[/bold cyan]\n")

    issues = linear.get_unassigned_issues()
    if not issues:
        console.print("[green]No unassigned issues![/green]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("ID", style="cyan")
    table.add_column("Summary")
    table.add_column("Status")
    table.add_column("Est", style="dim", width=4)

    for i, issue in enumerate(issues, 1):
        est = str(issue.story_points) if issue.story_points else "-"
        table.add_row(
            str(i),
            issue.key,
            issue.summary[:40] + ("..." if len(issue.summary) > 40 else ""),
            issue.status,
            est
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(issues)} unassigned[/dim]")
    console.print("[dim]Use 'rg linear assign <issue> <user>' to assign[/dim]")


@linear_app.command("assign")
def assign_issue(
    issue_key: str = typer.Argument(..., help="Issue ID (e.g., ENG-123)"),
    user: Optional[str] = typer.Argument(None, help="User name or number from team list")
):
    """Assign an issue to a team member."""
    linear = _get_linear()

    # Get issue info
    issue = linear.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Issue {issue_key} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{issue_key}[/bold]: {issue.summary}")
    console.print(f"[dim]Status: {issue.status}[/dim]")

    if issue.assignee:
        console.print(f"[yellow]Currently assigned to: {issue.assignee}[/yellow]")

    # Get team members
    members = linear.get_team_members()
    if not members:
        console.print("[red]No team members found.[/red]")
        raise typer.Exit(1)

    # If user not specified, show list
    if not user:
        console.print("\n[bold]Team Members:[/bold]")
        for i, m in enumerate(members, 1):
            console.print(f"  [{i}] {m.get('name')}")
        user = typer.prompt("\nSelect team member (number or name)")

    # Find user
    user_id = None
    display_name = None
    try:
        idx = int(user) - 1
        if 0 <= idx < len(members):
            user_id = members[idx].get("id")
            display_name = members[idx].get("name")
    except ValueError:
        user_lower = user.lower()
        for m in members:
            if user_lower in m.get("name", "").lower():
                user_id = m.get("id")
                display_name = m.get("name")
                break

    if not user_id:
        console.print(f"[red]User '{user}' not found.[/red]")
        raise typer.Exit(1)

    # Assign
    if linear.assign_issue(issue_key, user_id):
        console.print(f"\n[green]Assigned {issue_key} to {display_name}[/green]")
    else:
        console.print("[red]Failed to assign issue.[/red]")
        raise typer.Exit(1)


@linear_app.command("unassign")
def unassign_issue(
    issue_key: str = typer.Argument(..., help="Issue ID (e.g., ENG-123)")
):
    """Remove assignee from an issue."""
    linear = _get_linear()

    issue = linear.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Issue {issue_key} not found.[/red]")
        raise typer.Exit(1)

    if not issue.assignee:
        console.print(f"[yellow]{issue_key} is already unassigned.[/yellow]")
        return

    if linear.unassign_issue(issue_key):
        console.print(f"[green]Removed assignee from {issue_key}[/green]")
    else:
        console.print("[red]Failed to unassign issue.[/red]")
        raise typer.Exit(1)


@linear_app.command("cycle")
def show_cycle():
    """Show active cycle information."""
    linear = _get_linear()

    cycle = linear.get_active_sprint()
    if not cycle:
        console.print("[yellow]No active cycle found.[/yellow]")
        return

    console.print(f"\n[bold cyan]Active Cycle: {cycle.name}[/bold cyan]")
    console.print(f"[dim]{cycle.start_date} -> {cycle.end_date}[/dim]\n")

    # Get cycle issues
    issues = linear.get_sprint_issues(cycle.id)

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
            est = f" [{issue.story_points}p]" if issue.story_points else ""
            console.print(f"  * {issue.key}: {issue.summary[:35]}{est}{assignee}")
        console.print("")


@linear_app.command("cycles")
def list_cycles():
    """List all cycles for the team."""
    linear = _get_linear()

    console.print(f"\n[bold cyan]Cycles - {linear.team_key}[/bold cyan]\n")

    cycles = linear.get_cycles()
    if not cycles:
        console.print("[yellow]No cycles found.[/yellow]")
        return

    for cycle in cycles:
        if cycle.state == "active":
            console.print(f"[bold green]* {cycle.name}[/bold green] (Active)")
        else:
            console.print(f"  {cycle.name}")
        if cycle.start_date:
            console.print(f"    [dim]{cycle.start_date} -> {cycle.end_date}[/dim]")


@linear_app.command("backlog")
def show_backlog(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum issues to show")
):
    """Show backlog issues (not in any cycle)."""
    linear = _get_linear()

    console.print(f"\n[bold cyan]Backlog - {linear.team_key}[/bold cyan]\n")

    issues = linear.get_backlog_issues(limit)
    if not issues:
        console.print("[green]Backlog is empty![/green]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Summary")
    table.add_column("Status")
    table.add_column("Est", style="dim", width=4)

    for issue in issues:
        est = str(issue.story_points) if issue.story_points else "-"
        table.add_row(
            issue.key,
            issue.summary[:45] + ("..." if len(issue.summary) > 45 else ""),
            issue.status,
            est
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(issues)} backlog issues[/dim]")


@linear_app.command("create")
def create_issue(
    summary: str = typer.Argument(..., help="Issue title"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Issue description"),
    points: Optional[int] = typer.Option(None, "--points", "-p", help="Estimate points"),
    labels: Optional[str] = typer.Option(None, "--labels", "-l", help="Comma-separated labels"),
    parent: Optional[str] = typer.Option(None, "--parent", help="Parent issue ID"),
    assignee: Optional[str] = typer.Option(None, "--assignee", "-a", help="Assignee name or number"),
    cycle: bool = typer.Option(False, "--cycle", "-c", help="Add to active cycle")
):
    """Create a new issue."""
    linear = _get_linear()

    console.print("\n[bold cyan]Creating issue...[/bold cyan]\n")

    # Parse labels
    label_list = [l.strip() for l in labels.split(",")] if labels else None

    # Find assignee ID
    assignee_id = None
    if assignee:
        members = linear.get_team_members()
        try:
            idx = int(assignee) - 1
            if 0 <= idx < len(members):
                assignee_id = members[idx].get("id")
        except ValueError:
            for m in members:
                if assignee.lower() in m.get("name", "").lower():
                    assignee_id = m.get("id")
                    break

    # Create issue
    issue = linear.create_issue_with_parent(
        summary=summary,
        description=description or "",
        parent_key=parent,
        story_points=points,
        labels=label_list,
        assignee_id=assignee_id
    )

    if issue:
        console.print(f"[green]Created {issue.key}[/green]")
        console.print(f"  {issue.summary}")
        console.print(f"  [dim]{issue.url}[/dim]")
    else:
        console.print("[red]Failed to create issue.[/red]")
        raise typer.Exit(1)


@linear_app.command("link")
def link_issues_cmd(
    source: str = typer.Argument(..., help="Source issue ID (e.g., ENG-123)"),
    target: str = typer.Argument(..., help="Target issue ID (e.g., ENG-456)"),
    link_type: str = typer.Option("blocks", "--type", "-t", help="Link type: blocks, related, duplicate")
):
    """Link two issues together."""
    linear = _get_linear()

    # Verify both issues
    source_issue = linear.get_issue(source)
    target_issue = linear.get_issue(target)

    if not source_issue:
        console.print(f"[red]Issue {source} not found.[/red]")
        raise typer.Exit(1)

    if not target_issue:
        console.print(f"[red]Issue {target} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Linking issues:[/bold]")
    console.print(f"  {source}: {source_issue.summary[:40]}")
    console.print(f"  {link_type}")
    console.print(f"  {target}: {target_issue.summary[:40]}")

    if linear.link_issues(source, target, link_type):
        console.print(f"\n[green]Link created successfully[/green]")
    else:
        console.print("[red]Failed to create link.[/red]")
        raise typer.Exit(1)


@linear_app.command("links")
def show_issue_links(
    issue_key: str = typer.Argument(..., help="Issue ID (e.g., ENG-123)")
):
    """Show issue links/relations."""
    linear = _get_linear()

    issue = linear.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Issue {issue_key} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Links for {issue_key}[/bold cyan]")
    console.print(f"[dim]{issue.summary}[/dim]\n")

    relations = linear.get_issue_relations(issue_key)
    if not relations:
        console.print("[yellow]No links found.[/yellow]")
        return

    # Group by type
    by_type = {}
    for r in relations:
        t = r.get("type", "related")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r)

    for rel_type, rels in by_type.items():
        console.print(f"[bold]{rel_type}[/bold]")
        for r in rels:
            console.print(f"  * {r['issue_key']}: {r['summary'][:35]} [{r['status']}]")
        console.print("")


@linear_app.command("children")
def show_children(
    issue_key: str = typer.Argument(..., help="Parent issue ID (e.g., ENG-100)")
):
    """Show child issues (sub-issues) of a parent."""
    linear = _get_linear()

    issue = linear.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Issue {issue_key} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Parent: {issue_key}[/bold cyan]")
    console.print(f"[bold]{issue.summary}[/bold]")
    console.print(f"[dim]Status: {issue.status}[/dim]\n")

    children = linear.get_child_issues(issue_key)
    if not children:
        console.print("[yellow]No child issues found.[/yellow]")
        return

    total_points = 0
    for child in children:
        status_color = "green" if "done" in child.status.lower() else "yellow"
        points = f" [{child.story_points}p]" if child.story_points else ""
        if child.story_points:
            total_points += child.story_points
        console.print(f"  [{status_color}]*[/{status_color}] {child.key}: {child.summary[:35]}{points}")

    console.print(f"\n[dim]Total: {len(children)} issues, {total_points} points[/dim]")


@linear_app.command("states")
def show_states():
    """Show workflow states for the team."""
    linear = _get_linear()

    console.print(f"\n[bold cyan]Workflow States - {linear.team_key}[/bold cyan]\n")

    states = linear.get_workflow_states()
    if not states:
        console.print("[yellow]No states found.[/yellow]")
        return

    # Sort by position
    states.sort(key=lambda x: x.get("position", 0))

    # Group by type
    by_type = {}
    for s in states:
        t = s.get("type", "unstarted")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(s)

    type_order = ["backlog", "unstarted", "started", "completed", "canceled"]
    type_colors = {
        "backlog": "dim",
        "unstarted": "yellow",
        "started": "cyan",
        "completed": "green",
        "canceled": "red"
    }

    for state_type in type_order:
        if state_type in by_type:
            color = type_colors.get(state_type, "white")
            console.print(f"[bold {color}]{state_type.upper()}[/bold {color}]")
            for s in by_type[state_type]:
                console.print(f"  * {s['name']}")
            console.print("")


@linear_app.command("labels")
def show_labels():
    """Show available labels for the team."""
    linear = _get_linear()

    console.print(f"\n[bold cyan]Labels - {linear.team_key}[/bold cyan]\n")

    labels = linear.get_labels()
    if not labels:
        console.print("[yellow]No labels found.[/yellow]")
        return

    for label in labels:
        color = label.get("color", "")
        console.print(f"  * {label['name']} [dim]({color})[/dim]")


@linear_app.command("projects")
def list_projects():
    """List projects in the team."""
    linear = _get_linear()

    console.print(f"\n[bold cyan]Projects - {linear.team_key}[/bold cyan]\n")

    projects = linear.get_projects()
    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("State")
    table.add_column("Description", style="dim")

    for p in projects:
        table.add_row(
            p["name"],
            p.get("state", "-"),
            (p.get("description", "") or "-")[:40]
        )

    console.print(table)


@linear_app.command("move-cycle")
def move_to_cycle(
    issues: str = typer.Argument(..., help="Issue IDs (comma-separated, e.g., ENG-1,ENG-2)"),
    cycle_id: Optional[str] = typer.Option(None, "--cycle", "-c", help="Target cycle ID (default: active)")
):
    """Move issues to a cycle."""
    linear = _get_linear()

    # Parse issue keys
    issue_keys = [k.strip() for k in issues.split(",")]

    # Determine target cycle
    if cycle_id:
        target_cycle = cycle_id
        cycle_name = f"Cycle {cycle_id}"
    else:
        cycle = linear.get_active_sprint()
        if cycle:
            target_cycle = cycle.id
            cycle_name = cycle.name
        else:
            console.print("[yellow]No active cycle found.[/yellow]")
            raise typer.Exit(1)

    console.print(f"\n[bold]Moving {len(issue_keys)} issues to {cycle_name}[/bold]\n")

    success_count = 0
    for key in issue_keys:
        if linear.add_issue_to_sprint(key, target_cycle):
            console.print(f"  [green]*[/green] {key}")
            success_count += 1
        else:
            console.print(f"  [red]x[/red] {key}")

    console.print(f"\n[dim]Moved {success_count}/{len(issue_keys)} issues[/dim]")


@linear_app.command("estimate")
def set_estimate_cmd(
    issue_key: str = typer.Argument(..., help="Issue ID (e.g., ENG-123)"),
    points: int = typer.Argument(..., help="Estimate points")
):
    """Set estimate points for an issue."""
    linear = _get_linear()

    if linear.set_estimate(issue_key, points):
        console.print(f"[green]Set {issue_key} estimate to {points} points[/green]")
    else:
        console.print("[red]Failed to set estimate.[/red]")
        raise typer.Exit(1)


@linear_app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results")
):
    """Search issues by text."""
    linear = _get_linear()

    console.print(f"\n[bold cyan]Search: {query}[/bold cyan]\n")

    issues = linear.search_issues(query, limit)
    if not issues:
        console.print("[yellow]No issues found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Summary")
    table.add_column("Status")
    table.add_column("Assignee", style="dim")

    for issue in issues:
        table.add_row(
            issue.key,
            issue.summary[:40] + ("..." if len(issue.summary) > 40 else ""),
            issue.status,
            issue.assignee or "-"
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(issues)} issues[/dim]")


@linear_app.command("status")
def status_cmd():
    """Show Linear integration status."""
    linear = _get_linear()

    console.print("\n[bold cyan]Linear Status[/bold cyan]\n")
    console.print(f"   Team: {linear.team_key}")
    console.print(f"   [green]Connected[/green]")

    if linear._me:
        console.print(f"   User: {linear._me.get('name', 'Unknown')}")

    cycle = linear.get_active_sprint()
    if cycle:
        console.print(f"   Active Cycle: {cycle.name}")

    # Count issues
    my_issues = linear.get_my_active_issues()
    console.print(f"   My Active Issues: {len(my_issues)}")