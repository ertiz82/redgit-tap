"""
Bitbucket CLI commands for RedGit.

Commands:
- rg bitbucket status     : Show connection status
- rg bitbucket workspaces : List workspaces
- rg bitbucket repos      : List repositories
- rg bitbucket prs        : List pull requests
- rg bitbucket pr         : Create pull request
"""

import typer
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
bitbucket_app = typer.Typer(help="Bitbucket repository management")


def _get_bitbucket():
    """Get configured Bitbucket integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    bitbucket = get_code_hosting(config, "bitbucket")

    if not bitbucket:
        console.print("[red]Bitbucket integration not configured.[/red]")
        console.print("[dim]Run 'rg install bitbucket' to set up[/dim]")
        raise typer.Exit(1)

    return bitbucket


@bitbucket_app.command("status")
def status_cmd():
    """Show Bitbucket connection status."""
    bitbucket = _get_bitbucket()

    console.print("\n[bold cyan]Bitbucket Status[/bold cyan]\n")

    user = bitbucket.get_user()
    if user:
        console.print(f"   [green]Connected[/green]")
        console.print(f"   User: {user.get('username')}")
        console.print(f"   Name: {user.get('display_name', '-')}")
    else:
        console.print(f"   [red]Not connected[/red]")
        return

    console.print(f"\n   Workspace: {bitbucket.workspace}")
    console.print(f"   Repository: {bitbucket.repo_slug}")

    repo = bitbucket.get_repo_info()
    if repo:
        console.print(f"   Default branch: {repo.get('mainbranch', {}).get('name', '-')}")
        console.print(f"   Private: {'Yes' if repo.get('is_private') else 'No'}")
    else:
        console.print(f"   [yellow]Repository not found or no access[/yellow]")


@bitbucket_app.command("workspaces")
def list_workspaces():
    """List your workspaces."""
    bitbucket = _get_bitbucket()

    console.print("\n[bold cyan]Your Workspaces[/bold cyan]\n")

    workspaces = bitbucket.list_workspaces()
    if not workspaces:
        console.print("[yellow]No workspaces found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Slug", style="cyan")
    table.add_column("Name")

    for w in workspaces:
        is_current = " *" if w.get("slug") == bitbucket.workspace else ""
        table.add_row(
            w.get("slug", "-") + is_current,
            w.get("name", "-")
        )

    console.print(table)


@bitbucket_app.command("repos")
def list_repos():
    """List workspace repositories."""
    bitbucket = _get_bitbucket()

    console.print(f"\n[bold cyan]Repositories in {bitbucket.workspace}[/bold cyan]\n")

    repos = bitbucket.list_repos()
    if not repos:
        console.print("[yellow]No repositories found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Repository", style="cyan")
    table.add_column("Description")
    table.add_column("Private", justify="center")

    for r in repos[:20]:
        is_current = " *" if r.get("slug") == bitbucket.repo_slug else ""
        table.add_row(
            r.get("slug", "-") + is_current,
            (r.get("description") or "-")[:40],
            "Yes" if r.get("is_private") else "No"
        )

    console.print(table)


@bitbucket_app.command("info")
def repo_info():
    """Show repository information."""
    bitbucket = _get_bitbucket()

    console.print("\n[bold cyan]Repository Info[/bold cyan]\n")

    repo = bitbucket.get_repo_info()
    if not repo:
        console.print("[red]Repository not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Name: {repo.get('full_name')}")
    console.print(f"   Description: {repo.get('description') or '-'}")
    console.print(f"   Default branch: {repo.get('mainbranch', {}).get('name', '-')}")
    console.print(f"   Private: {'Yes' if repo.get('is_private') else 'No'}")
    console.print(f"   Language: {repo.get('language') or '-'}")
    console.print(f"   URL: {repo.get('links', {}).get('html', {}).get('href', '-')}")


@bitbucket_app.command("prs")
def list_prs(
    state: str = typer.Option("OPEN", "--state", "-s", help="PR state: OPEN, MERGED, DECLINED, SUPERSEDED")
):
    """List pull requests."""
    bitbucket = _get_bitbucket()

    console.print(f"\n[bold cyan]Pull Requests ({state})[/bold cyan]\n")

    prs = bitbucket.list_pull_requests(state.upper())
    if not prs:
        console.print("[yellow]No pull requests found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="cyan", width=6)
    table.add_column("Title")
    table.add_column("Author", style="dim")
    table.add_column("Branch")

    for pr in prs[:20]:
        table.add_row(
            f"#{pr['id']}",
            pr["title"][:40] + ("..." if len(pr["title"]) > 40 else ""),
            pr.get("author", {}).get("display_name", "-"),
            pr.get("source", {}).get("branch", {}).get("name", "-")
        )

    console.print(table)


@bitbucket_app.command("pr")
def create_pr(
    title: str = typer.Argument(..., help="PR title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="PR description"),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch")
):
    """Create a pull request from current branch."""
    import subprocess
    bitbucket = _get_bitbucket()

    # Get current branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        console.print("[red]Not in a git repository.[/red]")
        raise typer.Exit(1)

    head_branch = result.stdout.strip()
    base_branch = base or bitbucket.default_branch

    if head_branch == base_branch:
        console.print(f"[red]Cannot create PR from {base_branch} to itself.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Creating Pull Request[/bold cyan]\n")
    console.print(f"   From: {head_branch}")
    console.print(f"   To: {base_branch}")

    # Push branch first
    console.print(f"\n   Pushing branch...")
    if not bitbucket.push_branch(head_branch):
        console.print("[yellow]   Push failed, branch may already exist[/yellow]")

    # Create PR
    pr_url = bitbucket.create_pull_request(
        title=title,
        body=body or "",
        head_branch=head_branch,
        base_branch=base_branch
    )

    if pr_url:
        console.print(f"\n[green]Pull request created![/green]")
        console.print(f"   {pr_url}")
    else:
        console.print("[red]Failed to create pull request.[/red]")
        raise typer.Exit(1)


@bitbucket_app.command("branches")
def list_branches():
    """List repository branches."""
    bitbucket = _get_bitbucket()

    console.print("\n[bold cyan]Branches[/bold cyan]\n")

    branches = bitbucket.list_branches()
    if not branches:
        console.print("[yellow]No branches found.[/yellow]")
        return

    default = bitbucket.get_default_branch()

    for b in branches:
        name = b.get("name", "-")
        marker = " *" if name == default else ""
        console.print(f"   {name}{marker}")

    console.print(f"\n[dim]* = default branch[/dim]")


@bitbucket_app.command("merge")
def merge_pr(
    pr_id: int = typer.Argument(..., help="PR ID")
):
    """Merge a pull request."""
    bitbucket = _get_bitbucket()

    pr = bitbucket.get_pull_request(pr_id)
    if not pr:
        console.print(f"[red]PR #{pr_id} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Merging PR #{pr_id}[/bold cyan]")
    console.print(f"   Title: {pr['title']}")

    if bitbucket.merge_pull_request(pr_id):
        console.print(f"\n[green]Pull request merged![/green]")
    else:
        console.print("[red]Failed to merge pull request.[/red]")
        raise typer.Exit(1)


@bitbucket_app.command("decline")
def decline_pr(
    pr_id: int = typer.Argument(..., help="PR ID")
):
    """Decline a pull request."""
    bitbucket = _get_bitbucket()

    if bitbucket.decline_pull_request(pr_id):
        console.print(f"[green]PR #{pr_id} declined.[/green]")
    else:
        console.print("[red]Failed to decline pull request.[/red]")
        raise typer.Exit(1)