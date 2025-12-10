"""
Asana CLI commands for RedGit.

Commands:
- rg asana workspaces : List workspaces
- rg asana projects   : List projects
- rg asana issues     : List my tasks
- rg asana sections   : List project sections
- rg asana team       : List workspace members
- rg asana create     : Create a new task
- rg asana assign     : Assign task
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
asana_app = typer.Typer(help="Asana task management")


def _get_asana():
    """Get configured Asana integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    asana = get_task_management(config, "asana")

    if not asana:
        console.print("[red]Asana integration not configured.[/red]")
        console.print("[dim]Run 'rg install asana' to set up[/dim]")
        raise typer.Exit(1)

    return asana


@asana_app.command("workspaces")
def list_workspaces():
    """List user's workspaces."""
    asana = _get_asana()

    console.print("\n[bold cyan]Asana Workspaces[/bold cyan]\n")

    workspaces = asana.get_workspaces()
    if not workspaces:
        console.print("[yellow]No workspaces found.[/yellow]")
        return

    for w in workspaces:
        is_current = " *" if w["id"] == asana.workspace_id else ""
        console.print(f"  {w['name']} ({w['id']}){is_current}")

    console.print(f"\n[dim]Current: {asana.workspace_id}[/dim]")


@asana_app.command("projects")
def list_projects():
    """List projects in workspace."""
    asana = _get_asana()

    console.print("\n[bold cyan]Asana Projects[/bold cyan]\n")

    projects = asana.get_projects()
    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name")

    for p in projects:
        is_current = " *" if p["id"] == asana.project_id else ""
        table.add_row(p["id"], p["name"] + is_current)

    console.print(table)
    console.print(f"\n[dim]Current project: {asana.project_id}[/dim]")


@asana_app.command("sections")
def list_sections():
    """List sections in current project (statuses)."""
    asana = _get_asana()

    console.print("\n[bold cyan]Project Sections[/bold cyan]\n")

    sections = asana.get_sections()
    if not sections:
        console.print("[yellow]No sections found.[/yellow]")
        return

    for s in sections:
        console.print(f"  * {s['name']}")


@asana_app.command("issues")
def list_issues(
    all_issues: bool = typer.Option(False, "--all", "-a", help="Show all project tasks")
):
    """List my active tasks."""
    asana = _get_asana()

    console.print(f"\n[bold cyan]Asana Tasks[/bold cyan]\n")

    if all_issues:
        issues = asana.search_issues("", 50)
        title = "All Tasks"
    else:
        issues = asana.get_my_active_issues()
        title = "My Active Tasks"

    if not issues:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    table = Table(title=title, show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Task")
    table.add_column("Section")
    table.add_column("Assignee", style="dim")

    for issue in issues:
        table.add_row(
            issue.key.split("-")[-1][:8] + "...",
            issue.summary[:35] + ("..." if len(issue.summary) > 35 else ""),
            issue.status,
            issue.assignee or "-"
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(issues)} tasks[/dim]")


@asana_app.command("team")
def list_team():
    """List workspace members."""
    asana = _get_asana()

    console.print("\n[bold cyan]Workspace Members[/bold cyan]\n")

    members = asana.get_team_members()
    if not members:
        console.print("[yellow]No members found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name")
    table.add_column("Email", style="dim")

    for i, m in enumerate(members, 1):
        table.add_row(str(i), m["name"], m.get("email", "-"))

    console.print(table)


@asana_app.command("unassigned")
def list_unassigned():
    """List unassigned tasks."""
    asana = _get_asana()

    console.print("\n[bold cyan]Unassigned Tasks[/bold cyan]\n")

    issues = asana.get_unassigned_issues()
    if not issues:
        console.print("[green]No unassigned tasks![/green]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Task")
    table.add_column("Section")

    for i, issue in enumerate(issues, 1):
        table.add_row(
            str(i),
            issue.summary[:40],
            issue.status
        )

    console.print(table)


@asana_app.command("create")
def create_task(
    name: str = typer.Argument(..., help="Task name"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Task notes/description"),
    section: Optional[str] = typer.Option(None, "--section", "-s", help="Section name")
):
    """Create a new task."""
    asana = _get_asana()

    console.print("\n[bold cyan]Creating task...[/bold cyan]\n")

    issue_key = asana.create_issue(
        summary=name,
        description=notes or ""
    )

    if issue_key:
        console.print(f"[green]Created {issue_key}[/green]")
        console.print(f"  {name}")

        if section:
            if asana.transition_issue(issue_key, section):
                console.print(f"  [dim]Moved to: {section}[/dim]")
    else:
        console.print("[red]Failed to create task.[/red]")
        raise typer.Exit(1)


@asana_app.command("assign")
def assign_task(
    issue_key: str = typer.Argument(..., help="Task ID"),
    user: Optional[str] = typer.Argument(None, help="User name or number")
):
    """Assign task to member."""
    asana = _get_asana()

    issue = asana.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Task not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{issue_key}[/bold]: {issue.summary}")

    members = asana.get_team_members()
    if not members:
        console.print("[red]No members found.[/red]")
        raise typer.Exit(1)

    if not user:
        console.print("\n[bold]Members:[/bold]")
        for i, m in enumerate(members, 1):
            console.print(f"  [{i}] {m['name']}")
        user = typer.prompt("\nSelect member")

    user_id = None
    display_name = None
    try:
        idx = int(user) - 1
        if 0 <= idx < len(members):
            user_id = members[idx]["id"]
            display_name = members[idx]["name"]
    except ValueError:
        for m in members:
            if user.lower() in m["name"].lower():
                user_id = m["id"]
                display_name = m["name"]
                break

    if not user_id:
        console.print(f"[red]User not found.[/red]")
        raise typer.Exit(1)

    if asana.assign_issue(issue_key, user_id):
        console.print(f"\n[green]Assigned to {display_name}[/green]")
    else:
        console.print("[red]Failed to assign.[/red]")
        raise typer.Exit(1)


@asana_app.command("move")
def move_task(
    issue_key: str = typer.Argument(..., help="Task ID"),
    section: str = typer.Argument(..., help="Target section name")
):
    """Move task to section."""
    asana = _get_asana()

    if asana.transition_issue(issue_key, section):
        console.print(f"[green]Moved {issue_key} to {section}[/green]")
    else:
        console.print("[red]Failed to move task.[/red]")
        console.print("[dim]Use 'rg asana sections' to see available sections[/dim]")
        raise typer.Exit(1)


@asana_app.command("complete")
def complete_task(
    issue_key: str = typer.Argument(..., help="Task ID")
):
    """Mark task as complete."""
    asana = _get_asana()

    if asana.complete_task(issue_key):
        console.print(f"[green]Completed {issue_key}[/green]")
    else:
        console.print("[red]Failed to complete task.[/red]")
        raise typer.Exit(1)


@asana_app.command("subtasks")
def show_subtasks(
    issue_key: str = typer.Argument(..., help="Parent task ID")
):
    """Show subtasks of a task."""
    asana = _get_asana()

    issue = asana.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Task not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Subtasks of {issue_key}[/bold cyan]")
    console.print(f"[dim]{issue.summary}[/dim]\n")

    subtasks = asana.get_subtasks(issue_key)
    if not subtasks:
        console.print("[yellow]No subtasks.[/yellow]")
        return

    for st in subtasks:
        status_icon = "[green]*[/green]" if "done" in st.status.lower() else "[yellow]o[/yellow]"
        console.print(f"  {status_icon} {st.summary}")


@asana_app.command("add-subtask")
def add_subtask(
    parent_key: str = typer.Argument(..., help="Parent task ID"),
    name: str = typer.Argument(..., help="Subtask name")
):
    """Add a subtask."""
    asana = _get_asana()

    subtask_key = asana.create_subtask(parent_key, name)
    if subtask_key:
        console.print(f"[green]Created subtask: {subtask_key}[/green]")
    else:
        console.print("[red]Failed to create subtask.[/red]")
        raise typer.Exit(1)


@asana_app.command("tag")
def add_tag(
    issue_key: str = typer.Argument(..., help="Task ID"),
    tag: str = typer.Argument(..., help="Tag name")
):
    """Add tag to task."""
    asana = _get_asana()

    if asana.add_tag(issue_key, tag):
        console.print(f"[green]Added tag '{tag}' to {issue_key}[/green]")
    else:
        console.print("[red]Failed to add tag.[/red]")
        raise typer.Exit(1)


@asana_app.command("search")
def search_tasks(
    query: str = typer.Argument(..., help="Search query")
):
    """Search tasks by name."""
    asana = _get_asana()

    console.print(f"\n[bold cyan]Search: {query}[/bold cyan]\n")

    issues = asana.search_issues(query)
    if not issues:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Task")
    table.add_column("Section")
    table.add_column("Assignee", style="dim")

    for issue in issues:
        table.add_row(
            issue.summary[:40],
            issue.status,
            issue.assignee or "-"
        )

    console.print(table)


@asana_app.command("status")
def status_cmd():
    """Show Asana integration status."""
    asana = _get_asana()

    console.print("\n[bold cyan]Asana Status[/bold cyan]\n")
    console.print(f"   Workspace: {asana.workspace_id}")
    console.print(f"   Project: {asana.project_id or 'Not set'}")
    console.print(f"   [green]Connected[/green]")

    if asana._me:
        console.print(f"   User: {asana._me.get('name', 'Unknown')}")

    my_tasks = asana.get_my_active_issues()
    console.print(f"   My Active Tasks: {len(my_tasks)}")