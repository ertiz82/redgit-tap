"""
Notion CLI commands for RedGit.

Commands:
- rg notion databases : List accessible databases
- rg notion issues    : List my tasks
- rg notion team      : List workspace members
- rg notion create    : Create a new task
- rg notion assign    : Assign task to member
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
notion_app = typer.Typer(help="Notion task management")


def _get_notion():
    """Get configured Notion integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    notion = get_task_management(config, "notion")

    if not notion:
        console.print("[red]Notion integration not configured.[/red]")
        console.print("[dim]Run 'rg install notion' to set up[/dim]")
        raise typer.Exit(1)

    return notion


@notion_app.command("databases")
def list_databases():
    """List accessible Notion databases."""
    notion = _get_notion()

    console.print("\n[bold cyan]Notion Databases[/bold cyan]\n")

    databases = notion.get_databases()
    if not databases:
        console.print("[yellow]No databases found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Title")

    for db in databases:
        is_current = " *" if db["id"].replace("-", "") == notion.database_id.replace("-", "") else ""
        table.add_row(
            db["id"][:8] + "..." + is_current,
            db["title"]
        )

    console.print(table)
    console.print(f"\n[dim]Current database: {notion.database_id[:8]}...[/dim]")


@notion_app.command("issues")
def list_issues(
    all_issues: bool = typer.Option(False, "--all", "-a", help="Show all issues")
):
    """List my active tasks."""
    notion = _get_notion()

    console.print(f"\n[bold cyan]Notion Tasks[/bold cyan]\n")

    if all_issues:
        issues = notion.search_issues("", 50)
        title = "All Tasks"
    else:
        issues = notion.get_my_active_issues()
        title = "My Active Tasks"

    if not issues:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    table = Table(title=title, show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Assignee", style="dim")

    for issue in issues:
        status_color = "green" if "progress" in issue.status.lower() else "yellow"
        table.add_row(
            issue.key,
            issue.summary[:40] + ("..." if len(issue.summary) > 40 else ""),
            f"[{status_color}]{issue.status}[/{status_color}]",
            issue.assignee or "-"
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(issues)} tasks[/dim]")


@notion_app.command("team")
def list_team():
    """List workspace members."""
    notion = _get_notion()

    console.print("\n[bold cyan]Notion Members[/bold cyan]\n")

    members = notion.get_team_members()
    if not members:
        console.print("[yellow]No members found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name")
    table.add_column("Email", style="dim")

    for i, member in enumerate(members, 1):
        table.add_row(
            str(i),
            member.get("name", "-"),
            member.get("email", "-")
        )

    console.print(table)


@notion_app.command("unassigned")
def list_unassigned():
    """List unassigned tasks."""
    notion = _get_notion()

    console.print("\n[bold cyan]Unassigned Tasks[/bold cyan]\n")

    issues = notion.get_unassigned_issues()
    if not issues:
        console.print("[green]No unassigned tasks![/green]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Status")

    for i, issue in enumerate(issues, 1):
        table.add_row(
            str(i),
            issue.key,
            issue.summary[:35] + ("..." if len(issue.summary) > 35 else ""),
            issue.status
        )

    console.print(table)


@notion_app.command("create")
def create_task(
    title: str = typer.Argument(..., help="Task title"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Description"),
    points: Optional[int] = typer.Option(None, "--points", "-p", help="Story points")
):
    """Create a new task."""
    notion = _get_notion()

    console.print("\n[bold cyan]Creating task...[/bold cyan]\n")

    issue_key = notion.create_issue(
        summary=title,
        description=description or "",
        story_points=points
    )

    if issue_key:
        console.print(f"[green]Created {issue_key}[/green]")
        console.print(f"  {title}")
    else:
        console.print("[red]Failed to create task.[/red]")
        raise typer.Exit(1)


@notion_app.command("assign")
def assign_task(
    issue_key: str = typer.Argument(..., help="Task ID"),
    user: Optional[str] = typer.Argument(None, help="User name or number")
):
    """Assign task to a member."""
    notion = _get_notion()

    issue = notion.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Task {issue_key} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{issue_key}[/bold]: {issue.summary}")

    members = notion.get_team_members()
    if not members:
        console.print("[red]No members found.[/red]")
        raise typer.Exit(1)

    if not user:
        console.print("\n[bold]Members:[/bold]")
        for i, m in enumerate(members, 1):
            console.print(f"  [{i}] {m.get('name')}")
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
            if user.lower() in m.get("name", "").lower():
                user_id = m["id"]
                display_name = m["name"]
                break

    if not user_id:
        console.print(f"[red]User '{user}' not found.[/red]")
        raise typer.Exit(1)

    if notion.assign_issue(issue_key, user_id):
        console.print(f"\n[green]Assigned to {display_name}[/green]")
    else:
        console.print("[red]Failed to assign.[/red]")
        raise typer.Exit(1)


@notion_app.command("unassign")
def unassign_task(
    issue_key: str = typer.Argument(..., help="Task ID")
):
    """Remove assignee from task."""
    notion = _get_notion()

    if notion.unassign_issue(issue_key):
        console.print(f"[green]Removed assignee from {issue_key}[/green]")
    else:
        console.print("[red]Failed to unassign.[/red]")
        raise typer.Exit(1)


@notion_app.command("search")
def search_tasks(
    query: str = typer.Argument(..., help="Search query")
):
    """Search tasks by title."""
    notion = _get_notion()

    console.print(f"\n[bold cyan]Search: {query}[/bold cyan]\n")

    issues = notion.search_issues(query)
    if not issues:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Status")

    for issue in issues:
        table.add_row(
            issue.key,
            issue.summary[:40],
            issue.status
        )

    console.print(table)


@notion_app.command("status")
def status_cmd():
    """Show Notion integration status."""
    notion = _get_notion()

    console.print("\n[bold cyan]Notion Status[/bold cyan]\n")
    console.print(f"   Database: {notion.database_id[:8]}...")
    console.print(f"   [green]Connected[/green]")

    if notion._me:
        console.print(f"   User: {notion._me.get('name', 'Unknown')}")

    my_issues = notion.get_my_active_issues()
    console.print(f"   My Active Tasks: {len(my_issues)}")