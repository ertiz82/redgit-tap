"""
Trello CLI commands for RedGit.

Commands:
- rg trello boards    : List boards
- rg trello lists     : List board lists
- rg trello issues    : List my cards
- rg trello team      : List board members
- rg trello create    : Create a new card
- rg trello move      : Move card to list
- rg trello assign    : Assign card to member
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
trello_app = typer.Typer(help="Trello board management")


def _get_trello():
    """Get configured Trello integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    trello = get_task_management(config, "trello")

    if not trello:
        console.print("[red]Trello integration not configured.[/red]")
        console.print("[dim]Run 'rg install trello' to set up[/dim]")
        raise typer.Exit(1)

    return trello


@trello_app.command("boards")
def list_boards():
    """List your Trello boards."""
    trello = _get_trello()

    console.print("\n[bold cyan]Trello Boards[/bold cyan]\n")

    boards = trello.get_boards()
    if not boards:
        console.print("[yellow]No boards found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("URL", style="dim")

    for b in boards:
        is_current = " *" if b["id"] == trello.board_id else ""
        table.add_row(
            b["id"][:8] + "...",
            b["name"] + is_current,
            b["url"]
        )

    console.print(table)
    console.print(f"\n[dim]Current board: {trello.board_id}[/dim]")


@trello_app.command("lists")
def list_lists():
    """List board columns (lists)."""
    trello = _get_trello()

    console.print("\n[bold cyan]Board Lists[/bold cyan]\n")

    lists = trello.get_lists()
    if not lists:
        console.print("[yellow]No lists found.[/yellow]")
        return

    for l in lists:
        console.print(f"  * {l['name']}")


@trello_app.command("issues")
def list_issues(
    all_issues: bool = typer.Option(False, "--all", "-a", help="Show all board cards")
):
    """List my cards."""
    trello = _get_trello()

    console.print(f"\n[bold cyan]Trello Cards[/bold cyan]\n")

    if all_issues:
        issues = trello.search_issues("", 50)
        title = "All Cards"
    else:
        issues = trello.get_my_active_issues()
        title = "My Cards"

    if not issues:
        console.print("[yellow]No cards found.[/yellow]")
        return

    table = Table(title=title, show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Card")
    table.add_column("List")
    table.add_column("Assignee", style="dim")

    for issue in issues:
        short_id = issue.key.split("-")[-1][:8] + "..."
        table.add_row(
            short_id,
            issue.summary[:35] + ("..." if len(issue.summary) > 35 else ""),
            issue.status,
            issue.assignee or "-"
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(issues)} cards[/dim]")


@trello_app.command("team")
def list_team():
    """List board members."""
    trello = _get_trello()

    console.print("\n[bold cyan]Board Members[/bold cyan]\n")

    members = trello.get_team_members()
    if not members:
        console.print("[yellow]No members found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name")
    table.add_column("Username", style="dim")

    for i, m in enumerate(members, 1):
        table.add_row(str(i), m["name"], m.get("username", "-"))

    console.print(table)


@trello_app.command("unassigned")
def list_unassigned():
    """List unassigned cards."""
    trello = _get_trello()

    console.print("\n[bold cyan]Unassigned Cards[/bold cyan]\n")

    issues = trello.get_unassigned_issues()
    if not issues:
        console.print("[green]No unassigned cards![/green]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Card")
    table.add_column("List")

    for i, issue in enumerate(issues, 1):
        table.add_row(
            str(i),
            issue.summary[:40],
            issue.status
        )

    console.print(table)


@trello_app.command("create")
def create_card(
    name: str = typer.Argument(..., help="Card name"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Card description"),
    list_name: Optional[str] = typer.Option(None, "--list", "-l", help="Target list name")
):
    """Create a new card."""
    trello = _get_trello()

    console.print("\n[bold cyan]Creating card...[/bold cyan]\n")

    issue_key = trello.create_issue(
        summary=name,
        description=description or ""
    )

    if issue_key:
        console.print(f"[green]Created card[/green]")
        console.print(f"  {name}")

        if list_name:
            if trello.transition_issue(issue_key, list_name):
                console.print(f"  [dim]Moved to: {list_name}[/dim]")
    else:
        console.print("[red]Failed to create card.[/red]")
        raise typer.Exit(1)


@trello_app.command("move")
def move_card(
    issue_key: str = typer.Argument(..., help="Card ID"),
    list_name: str = typer.Argument(..., help="Target list name")
):
    """Move card to a list."""
    trello = _get_trello()

    if trello.transition_issue(issue_key, list_name):
        console.print(f"[green]Moved to {list_name}[/green]")
    else:
        console.print("[red]Failed to move card.[/red]")
        console.print("[dim]Use 'rg trello lists' to see available lists[/dim]")
        raise typer.Exit(1)


@trello_app.command("assign")
def assign_card(
    issue_key: str = typer.Argument(..., help="Card ID"),
    user: Optional[str] = typer.Argument(None, help="User name or number")
):
    """Assign card to member."""
    trello = _get_trello()

    issue = trello.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Card not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{issue_key}[/bold]: {issue.summary}")

    members = trello.get_team_members()
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

    if trello.assign_issue(issue_key, user_id):
        console.print(f"\n[green]Assigned to {display_name}[/green]")
    else:
        console.print("[red]Failed to assign.[/red]")
        raise typer.Exit(1)


@trello_app.command("unassign")
def unassign_card(
    issue_key: str = typer.Argument(..., help="Card ID")
):
    """Remove all members from card."""
    trello = _get_trello()

    if trello.unassign_issue(issue_key):
        console.print(f"[green]Removed members from card[/green]")
    else:
        console.print("[red]Failed to unassign.[/red]")
        raise typer.Exit(1)


@trello_app.command("archive")
def archive_card(
    issue_key: str = typer.Argument(..., help="Card ID")
):
    """Archive a card."""
    trello = _get_trello()

    if trello.archive_card(issue_key):
        console.print(f"[green]Archived card[/green]")
    else:
        console.print("[red]Failed to archive.[/red]")
        raise typer.Exit(1)


@trello_app.command("labels")
def list_labels():
    """List board labels."""
    trello = _get_trello()

    console.print("\n[bold cyan]Board Labels[/bold cyan]\n")

    labels = trello.get_labels()
    if not labels:
        console.print("[yellow]No labels found.[/yellow]")
        return

    for l in labels:
        name = l["name"] or "(no name)"
        console.print(f"  * {name} [{l['color']}]")


@trello_app.command("add-label")
def add_label(
    issue_key: str = typer.Argument(..., help="Card ID"),
    label: str = typer.Argument(..., help="Label name or ID")
):
    """Add label to card."""
    trello = _get_trello()

    # Find label ID
    labels = trello.get_labels()
    label_id = None

    for l in labels:
        if l["id"] == label or (l["name"] and label.lower() in l["name"].lower()):
            label_id = l["id"]
            break

    if not label_id:
        console.print(f"[red]Label not found.[/red]")
        console.print("[dim]Use 'rg trello labels' to see available labels[/dim]")
        raise typer.Exit(1)

    if trello.add_label(issue_key, label_id):
        console.print(f"[green]Added label to card[/green]")
    else:
        console.print("[red]Failed to add label.[/red]")
        raise typer.Exit(1)


@trello_app.command("checklists")
def show_checklists(
    issue_key: str = typer.Argument(..., help="Card ID")
):
    """Show card checklists."""
    trello = _get_trello()

    issue = trello.get_issue(issue_key)
    if not issue:
        console.print(f"[red]Card not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Checklists: {issue.summary[:40]}[/bold cyan]\n")

    checklists = trello.get_checklists(issue_key)
    if not checklists:
        console.print("[yellow]No checklists.[/yellow]")
        return

    for cl in checklists:
        console.print(f"[bold]{cl['name']}[/bold]")
        for item in cl["items"]:
            icon = "[green]x[/green]" if item["complete"] else "[yellow]o[/yellow]"
            console.print(f"  {icon} {item['name']}")
        console.print("")


@trello_app.command("add-checklist")
def add_checklist(
    issue_key: str = typer.Argument(..., help="Card ID"),
    name: str = typer.Argument(..., help="Checklist name"),
    items: Optional[str] = typer.Option(None, "--items", "-i", help="Comma-separated items")
):
    """Create a checklist on card."""
    trello = _get_trello()

    item_list = [i.strip() for i in items.split(",")] if items else None

    if trello.create_checklist(issue_key, name, item_list):
        console.print(f"[green]Created checklist: {name}[/green]")
        if item_list:
            console.print(f"  {len(item_list)} items added")
    else:
        console.print("[red]Failed to create checklist.[/red]")
        raise typer.Exit(1)


@trello_app.command("search")
def search_cards(
    query: str = typer.Argument(..., help="Search query")
):
    """Search cards by name."""
    trello = _get_trello()

    console.print(f"\n[bold cyan]Search: {query}[/bold cyan]\n")

    issues = trello.search_issues(query)
    if not issues:
        console.print("[yellow]No cards found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Card")
    table.add_column("List")
    table.add_column("Assignee", style="dim")

    for issue in issues:
        table.add_row(
            issue.summary[:40],
            issue.status,
            issue.assignee or "-"
        )

    console.print(table)


@trello_app.command("status")
def status_cmd():
    """Show Trello integration status."""
    trello = _get_trello()

    console.print("\n[bold cyan]Trello Status[/bold cyan]\n")
    console.print(f"   Board: {trello.board_id}")
    console.print(f"   [green]Connected[/green]")

    if trello._me:
        console.print(f"   User: {trello._me.get('fullName', trello._me.get('username', 'Unknown'))}")

    my_cards = trello.get_my_active_issues()
    console.print(f"   My Cards: {len(my_cards)}")