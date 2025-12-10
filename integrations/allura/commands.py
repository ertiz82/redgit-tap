"""
Apache Allura CLI commands for RedGit.

Commands:
- rg allura status   : Show connection status
- rg allura project  : Show project info
- rg allura mrs      : List merge requests
- rg allura tickets  : List tickets
- rg allura branches : List branches
"""

import typer
import webbrowser
from rich.console import Console
from rich.table import Table
from typing import Optional

try:
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import get_code_hosting
except ImportError:
    ConfigManager = None
    get_code_hosting = None

console = Console()
allura_app = typer.Typer(help="Apache Allura repository management")


def _get_allura():
    """Get configured Allura integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    allura = get_code_hosting(config, "allura")

    if not allura:
        console.print("[red]Allura integration not configured.[/red]")
        console.print("[dim]Run 'rg install allura' to set up[/dim]")
        raise typer.Exit(1)

    return allura


@allura_app.command("status")
def status_cmd():
    """Show Allura connection status."""
    allura = _get_allura()

    console.print("\n[bold cyan]Apache Allura Status[/bold cyan]\n")

    console.print(f"   Instance: {allura.base_url}")
    console.print(f"   Project: {allura.project}")
    console.print(f"   Repository: {allura.mount_point}")
    console.print(f"   Auth: {'Token configured' if allura.bearer_token else 'No token (read-only)'}")

    project = allura.get_project_info()
    if project:
        console.print(f"\n   [green]Connected[/green]")
        console.print(f"   Project name: {project.get('name', '-')}")
    else:
        console.print(f"\n   [yellow]Could not verify (may still work)[/yellow]")


@allura_app.command("project")
def project_info():
    """Show project information."""
    allura = _get_allura()

    console.print("\n[bold cyan]Project Info[/bold cyan]\n")

    project = allura.get_project_info()
    if not project:
        console.print("[yellow]Could not fetch project info.[/yellow]")
        console.print(f"\n   Project URL: {allura.get_project_url()}")
        return

    console.print(f"   Name: {project.get('name', '-')}")
    console.print(f"   Short name: {project.get('shortname', allura.project)}")
    console.print(f"   Summary: {project.get('summary', '-')}")
    console.print(f"\n   URL: {allura.get_project_url()}")

    # List tools
    tools = project.get("tools", [])
    if tools:
        console.print(f"\n   [bold]Tools:[/bold]")
        for tool in tools:
            console.print(f"     - {tool.get('mount_point', '-')}: {tool.get('name', '-')}")


@allura_app.command("info")
def repo_info():
    """Show repository information."""
    allura = _get_allura()

    console.print("\n[bold cyan]Repository Info[/bold cyan]\n")

    repo = allura.get_repo_info()

    console.print(f"   Project: {allura.project}")
    console.print(f"   Mount point: {allura.mount_point}")
    console.print(f"   Default branch: {allura.default_branch}")
    console.print(f"\n   Repository URL: {allura.get_repo_url()}")

    if repo:
        console.print(f"   Status: [green]Available[/green]")
    else:
        console.print(f"   Status: [yellow]Could not verify[/yellow]")


@allura_app.command("branches")
def list_branches():
    """List repository branches."""
    allura = _get_allura()

    console.print("\n[bold cyan]Branches[/bold cyan]\n")

    # Fetch first
    console.print("[dim]Fetching from remote...[/dim]")
    allura.fetch_remote()

    branches = allura.list_branches()
    if not branches:
        console.print("[yellow]No branches found.[/yellow]")
        return

    default = allura.default_branch

    for name in branches:
        marker = " *" if name == default else ""
        console.print(f"   {name}{marker}")

    console.print(f"\n[dim]* = default branch[/dim]")


@allura_app.command("mrs")
def list_mrs(
    status: str = typer.Option("open", "--status", "-s", help="MR status: open, merged, rejected")
):
    """List merge requests."""
    allura = _get_allura()

    console.print(f"\n[bold cyan]Merge Requests ({status})[/bold cyan]\n")

    mrs = allura.list_merge_requests(status)
    if not mrs:
        console.print("[yellow]No merge requests found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="cyan", width=6)
    table.add_column("Summary")
    table.add_column("Source", style="dim")

    for mr in mrs[:20]:
        table.add_row(
            str(mr.get("request_number", "-")),
            mr.get("summary", "-")[:40],
            mr.get("source_branch", "-")
        )

    console.print(table)


@allura_app.command("mr")
def create_mr(
    title: str = typer.Argument(..., help="MR title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="MR description"),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch")
):
    """Create a merge request."""
    import subprocess
    allura = _get_allura()

    # Get current branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        console.print("[red]Not in a git repository.[/red]")
        raise typer.Exit(1)

    head_branch = result.stdout.strip()
    base_branch = base or allura.default_branch

    if head_branch == base_branch:
        console.print(f"[red]Cannot create MR from {base_branch} to itself.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Creating Merge Request[/bold cyan]\n")
    console.print(f"   From: {head_branch}")
    console.print(f"   To: {base_branch}")

    # Push branch first
    console.print(f"\n   Pushing branch...")
    if not allura.push_branch(head_branch):
        console.print("[yellow]   Push failed, branch may already exist[/yellow]")

    # Create MR
    mr_url = allura.create_pull_request(
        title=title,
        body=body or "",
        head_branch=head_branch,
        base_branch=base_branch
    )

    if mr_url:
        console.print(f"\n[green]Merge request URL:[/green]")
        console.print(f"   {mr_url}")

        if "new" in mr_url:
            console.print("\n[dim]Opening web interface for manual creation...[/dim]")
            try:
                webbrowser.open(mr_url)
            except Exception:
                pass
    else:
        console.print("[red]Failed to create merge request.[/red]")
        raise typer.Exit(1)


@allura_app.command("tickets")
def list_tickets(
    status: str = typer.Option("open", "--status", "-s", help="Ticket status: open, closed")
):
    """List project tickets."""
    allura = _get_allura()

    console.print(f"\n[bold cyan]Tickets ({status})[/bold cyan]\n")

    tickets = allura.list_tickets(status)
    if not tickets:
        console.print("[yellow]No tickets found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="cyan", width=6)
    table.add_column("Summary")
    table.add_column("Status", style="dim")

    for ticket in tickets[:20]:
        table.add_row(
            str(ticket.get("ticket_num", "-")),
            ticket.get("summary", "-")[:40],
            ticket.get("status", "-")
        )

    console.print(table)


@allura_app.command("ticket")
def create_ticket(
    summary: str = typer.Argument(..., help="Ticket summary"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Description")
):
    """Create a ticket."""
    allura = _get_allura()

    console.print(f"\n[bold cyan]Creating Ticket[/bold cyan]\n")

    result = allura.create_ticket(summary, description or "")

    if result:
        console.print(f"[green]Ticket created![/green]")
    else:
        console.print("[yellow]Could not create via API, opening web interface...[/yellow]")
        url = f"{allura.get_project_url()}tickets/new"
        try:
            webbrowser.open(url)
        except Exception:
            console.print(f"   {url}")


@allura_app.command("push")
def push_branch(
    branch: Optional[str] = typer.Argument(None, help="Branch name")
):
    """Push branch to remote."""
    import subprocess
    allura = _get_allura()

    if not branch:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            console.print("[red]Not in a git repository.[/red]")
            raise typer.Exit(1)
        branch = result.stdout.strip()

    console.print(f"\n[bold cyan]Pushing {branch}[/bold cyan]\n")

    if allura.push_branch(branch):
        console.print(f"[green]Pushed successfully![/green]")
    else:
        console.print("[red]Failed to push.[/red]")
        raise typer.Exit(1)


@allura_app.command("fetch")
def fetch_remote():
    """Fetch from remote."""
    allura = _get_allura()

    console.print("\n[bold cyan]Fetching from remote[/bold cyan]\n")

    if allura.fetch_remote():
        console.print(f"[green]Fetched successfully![/green]")
    else:
        console.print("[red]Failed to fetch.[/red]")
        raise typer.Exit(1)


@allura_app.command("open")
def open_project():
    """Open project page in browser."""
    allura = _get_allura()

    url = allura.get_project_url()
    console.print(f"   Opening: {url}")

    try:
        webbrowser.open(url)
        console.print("[green]Opened in browser![/green]")
    except Exception:
        console.print("[yellow]Could not open browser.[/yellow]")