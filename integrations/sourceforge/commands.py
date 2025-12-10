"""
SourceForge CLI commands for RedGit.

Commands:
- rg sourceforge status   : Show connection status
- rg sourceforge info     : Show repository info
- rg sourceforge branches : List branches
- rg sourceforge push     : Push current branch
"""

import typer
import webbrowser
from rich.console import Console
from typing import Optional

try:
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import get_code_hosting
except ImportError:
    ConfigManager = None
    get_code_hosting = None

console = Console()
sourceforge_app = typer.Typer(help="SourceForge repository management")


def _get_sourceforge():
    """Get configured SourceForge integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    sf = get_code_hosting(config, "sourceforge")

    if not sf:
        console.print("[red]SourceForge integration not configured.[/red]")
        console.print("[dim]Run 'rg install sourceforge' to set up[/dim]")
        raise typer.Exit(1)

    return sf


@sourceforge_app.command("status")
def status_cmd():
    """Show SourceForge connection status."""
    sf = _get_sourceforge()

    console.print("\n[bold cyan]SourceForge Status[/bold cyan]\n")

    console.print(f"   [green]Configured[/green]")
    console.print(f"   Username: {sf.username}")
    console.print(f"   Project: {sf.project}")
    console.print(f"   Repository: {sf.repo_path}")
    console.print(f"\n   Project URL: {sf.get_project_url()}")


@sourceforge_app.command("info")
def repo_info():
    """Show repository information."""
    sf = _get_sourceforge()

    console.print("\n[bold cyan]Repository Info[/bold cyan]\n")

    info = sf.get_remote_info()

    console.print(f"   Project: {info['project']}")
    console.print(f"   Repository: {info['repo_path']}")
    console.print(f"   Default branch: {sf.default_branch}")
    console.print(f"\n   Project URL: {info['project_url']}")
    console.print(f"   Repository URL: {info['repo_url']}")
    console.print(f"\n   Clone (SSH): {info['clone_ssh']}")
    console.print(f"   Clone (HTTPS): {info['clone_https']}")


@sourceforge_app.command("branches")
def list_branches():
    """List repository branches."""
    sf = _get_sourceforge()

    console.print("\n[bold cyan]Branches[/bold cyan]\n")

    # Fetch first to get latest
    console.print("[dim]Fetching from remote...[/dim]")
    sf.fetch_remote()

    branches = sf.list_branches()
    if not branches:
        console.print("[yellow]No branches found.[/yellow]")
        return

    default = sf.default_branch

    for name in branches:
        marker = " *" if name == default else ""
        console.print(f"   {name}{marker}")

    console.print(f"\n[dim]* = default branch[/dim]")


@sourceforge_app.command("push")
def push_branch(
    branch: Optional[str] = typer.Argument(None, help="Branch name (default: current)")
):
    """Push branch to SourceForge."""
    import subprocess
    sf = _get_sourceforge()

    # Get current branch if not specified
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

    if sf.push_branch(branch):
        console.print(f"[green]Pushed successfully![/green]")
    else:
        console.print("[red]Failed to push.[/red]")
        console.print("[dim]Check SSH key configuration[/dim]")
        raise typer.Exit(1)


@sourceforge_app.command("fetch")
def fetch_remote():
    """Fetch from remote."""
    sf = _get_sourceforge()

    console.print("\n[bold cyan]Fetching from SourceForge[/bold cyan]\n")

    if sf.fetch_remote():
        console.print(f"[green]Fetched successfully![/green]")
    else:
        console.print("[red]Failed to fetch.[/red]")
        raise typer.Exit(1)


@sourceforge_app.command("pr")
def create_pr(
    title: Optional[str] = typer.Argument(None, help="PR title (unused, opens browser)")
):
    """Open merge request page in browser.

    Note: SourceForge merge requests are created through the web interface.
    """
    sf = _get_sourceforge()

    url = sf.create_pull_request(title or "", "", "", "")

    console.print("\n[bold cyan]Creating Merge Request[/bold cyan]\n")
    console.print("[dim]SourceForge merge requests are created via web interface.[/dim]")
    console.print(f"\n   Opening: {url}")

    try:
        webbrowser.open(url)
        console.print("\n[green]Opened in browser![/green]")
    except Exception:
        console.print("\n[yellow]Could not open browser. Visit the URL manually.[/yellow]")


@sourceforge_app.command("open")
def open_project():
    """Open project page in browser."""
    sf = _get_sourceforge()

    url = sf.get_project_url()
    console.print(f"   Opening: {url}")

    try:
        webbrowser.open(url)
        console.print("[green]Opened in browser![/green]")
    except Exception:
        console.print("[yellow]Could not open browser.[/yellow]")