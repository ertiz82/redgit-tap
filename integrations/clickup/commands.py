"""
ClickUp CLI commands.

Commands:
- rg clickup status     : Show integration status
- rg clickup issues     : List my active tasks
- rg clickup task       : Show single task detail
- rg clickup create     : Create a new task
- rg clickup assign     : Assign task to team member
- rg clickup team       : List workspace members
- rg clickup lists      : List available lists
- rg clickup statuses   : Show available statuses for current list
- rg clickup search     : Search tasks
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
clickup_app = typer.Typer(help="ClickUp task management")


def _get_clickup():
    """Get configured ClickUp integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    clickup = get_task_management(config, "clickup")

    if not clickup:
        console.print("[red]ClickUp integration not configured.[/red]")
        console.print("[dim]Run 'rg install clickup' to set up[/dim]")
        raise typer.Exit(1)

    return clickup


@clickup_app.command("status")
def status_cmd():
    """Show ClickUp integration status."""
    clickup = _get_clickup()

    console.print("\n[bold cyan]ClickUp Status[/bold cyan]\n")

    if clickup._me:
        console.print(f"   User: {clickup._me.get('username', 'Unknown')}")
        console.print(f"   Email: {clickup._me.get('email', '-')}")

    console.print(f"   Workspace ID: {clickup.team_id}")
    console.print(f"   List ID: {clickup.list_id}")
    console.print(f"   [green]Connected[/green]")

    # Count my active tasks
    my_tasks = clickup.get_my_active_issues()
    console.print(f"   My Active Tasks: {len(my_tasks)}")


@clickup_app.command("issues")
def list_issues(
    all_tasks: bool = typer.Option(False, "--all", "-a", help="Show all tasks in list")
):
    """List my active tasks."""
    clickup = _get_clickup()

    console.print("\n[bold cyan]ClickUp Tasks[/bold cyan]\n")

    if all_tasks:
        tasks = clickup.get_list_tasks()
        title = "All Tasks"
    else:
        tasks = clickup.get_my_active_issues()
        title = "My Active Tasks"

    if not tasks:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    table = Table(title=title, show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Summary")
    table.add_column("Status")
    table.add_column("Assignee", style="dim")

    for task in tasks:
        status_color = "green" if "progress" in task.status.lower() else "yellow"
        table.add_row(
            task.key,
            task.summary[:45] + ("..." if len(task.summary) > 45 else ""),
            f"[{status_color}]{task.status}[/{status_color}]",
            task.assignee or "-"
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(tasks)} tasks[/dim]")


@clickup_app.command("task")
def show_task(
    task_id: str = typer.Argument(..., help="Task ID")
):
    """Show task details."""
    clickup = _get_clickup()

    task = clickup.get_issue(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]{task.key}[/bold cyan]")
    console.print(f"[bold]{task.summary}[/bold]")
    console.print(f"[dim]Status:[/dim] {task.status}")

    if task.assignee:
        console.print(f"[dim]Assignee:[/dim] {task.assignee}")

    if task.url:
        console.print(f"[dim]URL:[/dim] {task.url}")

    if task.description:
        console.print(f"\n[dim]{task.description[:200]}[/dim]")


@clickup_app.command("create")
def create_task(
    summary: str = typer.Argument(..., help="Task title"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Task description"),
    parent: Optional[str] = typer.Option(None, "--parent", "-p", help="Parent task ID")
):
    """Create a new task."""
    clickup = _get_clickup()

    console.print("\n[bold cyan]Creating task...[/bold cyan]\n")

    task_id = clickup.create_issue(
        summary=summary,
        description=description or "",
        parent_key=parent
    )

    if task_id:
        console.print(f"[green]Created task: {task_id}[/green]")
        task = clickup.get_issue(task_id)
        if task:
            console.print(f"  {task.summary}")
            if task.url:
                console.print(f"  [dim]{task.url}[/dim]")
    else:
        console.print("[red]Failed to create task.[/red]")
        raise typer.Exit(1)


@clickup_app.command("team")
def list_team():
    """List workspace members."""
    clickup = _get_clickup()

    console.print("\n[bold cyan]Workspace Members[/bold cyan]\n")

    members = clickup.get_team_members()
    if not members:
        console.print("[yellow]No members found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name")
    table.add_column("Email", style="dim")

    for i, m in enumerate(members, 1):
        table.add_row(
            str(i),
            m.get("name", "-"),
            m.get("email", "-")
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(members)} members[/dim]")


@clickup_app.command("assign")
def assign_task(
    task_id: str = typer.Argument(..., help="Task ID"),
    user: Optional[str] = typer.Argument(None, help="User name or number from team list")
):
    """Assign a task to a team member."""
    clickup = _get_clickup()

    task = clickup.get_issue(task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{task_id}[/bold]: {task.summary}")
    if task.assignee:
        console.print(f"[yellow]Currently assigned to: {task.assignee}[/yellow]")

    members = clickup.get_team_members()
    if not members:
        console.print("[red]No team members found.[/red]")
        raise typer.Exit(1)

    if not user:
        console.print("\n[bold]Workspace Members:[/bold]")
        for i, m in enumerate(members, 1):
            console.print(f"  [{i}] {m.get('name')}")
        user = typer.prompt("\nSelect member (number or name)")

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

    if clickup.assign_issue(task_id, user_id):
        console.print(f"\n[green]Assigned {task_id} to {display_name}[/green]")
    else:
        console.print("[red]Failed to assign task.[/red]")
        raise typer.Exit(1)


@clickup_app.command("lists")
def show_lists():
    """Show available lists in the workspace."""
    clickup = _get_clickup()

    console.print("\n[bold cyan]ClickUp Lists[/bold cyan]\n")

    spaces = clickup.get_spaces()
    if not spaces:
        console.print("[yellow]No spaces found.[/yellow]")
        return

    for space in spaces:
        lists = clickup.get_lists(space["id"])
        if lists:
            console.print(f"[bold]{space['name']}[/bold]")
            for lst in lists:
                marker = " *" if lst["id"] == clickup.list_id else ""
                console.print(f"  * {lst['name']}{marker} [dim](ID: {lst['id']})[/dim]")
            console.print("")


@clickup_app.command("statuses")
def show_statuses(
    list_id: Optional[str] = typer.Option(None, "--list", "-l", help="List ID (default: configured list)")
):
    """Show available statuses for the current list."""
    clickup = _get_clickup()

    console.print("\n[bold cyan]ClickUp Statuses[/bold cyan]\n")

    statuses = clickup.get_statuses(list_id)
    if not statuses:
        console.print("[yellow]No statuses found.[/yellow]")
        return

    for s in statuses:
        console.print(f"  * {s['status']} [dim](type: {s.get('type', '-')})[/dim]")


@clickup_app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    list_id: Optional[str] = typer.Option(None, "--list", "-l", help="List ID to search in")
):
    """Search tasks by text."""
    clickup = _get_clickup()

    console.print(f"\n[bold cyan]Search: {query}[/bold cyan]\n")

    tasks = clickup.search_tasks(query, list_id)
    if not tasks:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Summary")
    table.add_column("Status")
    table.add_column("Assignee", style="dim")

    for task in tasks:
        table.add_row(
            task.key,
            task.summary[:45] + ("..." if len(task.summary) > 45 else ""),
            task.status,
            task.assignee or "-"
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(tasks)} tasks[/dim]")


@clickup_app.command("workspaces")
def show_workspaces():
    """List all accessible workspaces."""
    clickup = _get_clickup()

    console.print("\n[bold cyan]ClickUp Workspaces[/bold cyan]\n")

    workspaces = clickup.get_workspaces()
    if not workspaces:
        console.print("[yellow]No workspaces found.[/yellow]")
        return

    for ws in workspaces:
        marker = " *" if ws["id"] == clickup.team_id else ""
        console.print(f"  * {ws['name']}{marker} [dim](ID: {ws['id']})[/dim]")