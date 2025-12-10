"""
Azure Repos CLI commands for RedGit.

Commands:
- rg azure-repos status   : Show connection status
- rg azure-repos projects : List projects
- rg azure-repos repos    : List repositories
- rg azure-repos prs      : List pull requests
- rg azure-repos pr       : Create pull request
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
azure_repos_app = typer.Typer(help="Azure Repos repository management")


def _get_azure_repos():
    """Get configured Azure Repos integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    azure = get_code_hosting(config, "azure-repos")

    if not azure:
        console.print("[red]Azure Repos integration not configured.[/red]")
        console.print("[dim]Run 'rg install azure-repos' to set up[/dim]")
        raise typer.Exit(1)

    return azure


@azure_repos_app.command("status")
def status_cmd():
    """Show Azure Repos connection status."""
    azure = _get_azure_repos()

    console.print("\n[bold cyan]Azure Repos Status[/bold cyan]\n")

    user = azure.get_user()
    if user:
        console.print(f"   [green]Connected[/green]")
        console.print(f"   User: {user.get('providerDisplayName', user.get('id', '-'))}")
        console.print(f"   Organization: {azure.organization}")
    else:
        console.print(f"   [red]Not connected[/red]")
        return

    console.print(f"\n   Project: {azure.project}")
    console.print(f"   Repository: {azure.repository}")

    repo = azure.get_repo_info()
    if repo:
        default_branch = repo.get("defaultBranch", "").replace("refs/heads/", "")
        console.print(f"   Default branch: {default_branch}")
    else:
        console.print(f"   [yellow]Repository not found or no access[/yellow]")


@azure_repos_app.command("projects")
def list_projects():
    """List organization projects."""
    azure = _get_azure_repos()

    console.print(f"\n[bold cyan]Projects in {azure.organization}[/bold cyan]\n")

    projects = azure.list_projects()
    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Project", style="cyan")
    table.add_column("Description")
    table.add_column("State")

    for p in projects:
        is_current = " *" if p.get("name") == azure.project else ""
        table.add_row(
            p.get("name", "-") + is_current,
            (p.get("description") or "-")[:40],
            p.get("state", "-")
        )

    console.print(table)


@azure_repos_app.command("repos")
def list_repos():
    """List project repositories."""
    azure = _get_azure_repos()

    console.print(f"\n[bold cyan]Repositories in {azure.project}[/bold cyan]\n")

    repos = azure.list_repositories()
    if not repos:
        console.print("[yellow]No repositories found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Repository", style="cyan")
    table.add_column("Default Branch")
    table.add_column("Size", justify="right")

    for r in repos:
        is_current = " *" if r.get("name") == azure.repository else ""
        default_branch = r.get("defaultBranch", "").replace("refs/heads/", "")
        size_mb = r.get("size", 0) / (1024 * 1024)
        table.add_row(
            r.get("name", "-") + is_current,
            default_branch or "-",
            f"{size_mb:.1f} MB"
        )

    console.print(table)


@azure_repos_app.command("info")
def repo_info():
    """Show repository information."""
    azure = _get_azure_repos()

    console.print("\n[bold cyan]Repository Info[/bold cyan]\n")

    repo = azure.get_repo_info()
    if not repo:
        console.print("[red]Repository not found.[/red]")
        raise typer.Exit(1)

    default_branch = repo.get("defaultBranch", "").replace("refs/heads/", "")
    size_mb = repo.get("size", 0) / (1024 * 1024)

    console.print(f"   Name: {repo.get('name')}")
    console.print(f"   Project: {repo.get('project', {}).get('name', '-')}")
    console.print(f"   Default branch: {default_branch}")
    console.print(f"   Size: {size_mb:.1f} MB")
    console.print(f"   URL: {repo.get('webUrl', '-')}")


@azure_repos_app.command("prs")
def list_prs(
    status: str = typer.Option("active", "--status", "-s", help="PR status: active, completed, abandoned, all")
):
    """List pull requests."""
    azure = _get_azure_repos()

    console.print(f"\n[bold cyan]Pull Requests ({status})[/bold cyan]\n")

    prs = azure.list_pull_requests(status)
    if not prs:
        console.print("[yellow]No pull requests found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="cyan", width=6)
    table.add_column("Title")
    table.add_column("Author", style="dim")
    table.add_column("Branch")

    for pr in prs[:20]:
        source = pr.get("sourceRefName", "").replace("refs/heads/", "")
        table.add_row(
            f"#{pr.get('pullRequestId', '-')}",
            pr.get("title", "-")[:40] + ("..." if len(pr.get("title", "")) > 40 else ""),
            pr.get("createdBy", {}).get("displayName", "-"),
            source
        )

    console.print(table)


@azure_repos_app.command("pr")
def create_pr(
    title: str = typer.Argument(..., help="PR title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="PR description"),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch")
):
    """Create a pull request from current branch."""
    import subprocess
    azure = _get_azure_repos()

    # Get current branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        console.print("[red]Not in a git repository.[/red]")
        raise typer.Exit(1)

    head_branch = result.stdout.strip()
    base_branch = base or azure.default_branch

    if head_branch == base_branch:
        console.print(f"[red]Cannot create PR from {base_branch} to itself.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Creating Pull Request[/bold cyan]\n")
    console.print(f"   From: {head_branch}")
    console.print(f"   To: {base_branch}")

    # Push branch first
    console.print(f"\n   Pushing branch...")
    if not azure.push_branch(head_branch):
        console.print("[yellow]   Push failed, branch may already exist[/yellow]")

    # Create PR
    pr_url = azure.create_pull_request(
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


@azure_repos_app.command("branches")
def list_branches():
    """List repository branches."""
    azure = _get_azure_repos()

    console.print("\n[bold cyan]Branches[/bold cyan]\n")

    branches = azure.list_branches()
    if not branches:
        console.print("[yellow]No branches found.[/yellow]")
        return

    default = azure.get_default_branch()

    for b in branches:
        name = b.get("name", "").replace("refs/heads/", "")
        marker = " *" if name == default else ""
        console.print(f"   {name}{marker}")

    console.print(f"\n[dim]* = default branch[/dim]")


@azure_repos_app.command("complete")
def complete_pr(
    pr_id: int = typer.Argument(..., help="PR ID"),
    delete_source: bool = typer.Option(False, "--delete-source", "-d", help="Delete source branch"),
    squash: bool = typer.Option(False, "--squash", help="Squash merge")
):
    """Complete (merge) a pull request."""
    azure = _get_azure_repos()

    pr = azure.get_pull_request(pr_id)
    if not pr:
        console.print(f"[red]PR #{pr_id} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Completing PR #{pr_id}[/bold cyan]")
    console.print(f"   Title: {pr.get('title')}")
    if squash:
        console.print(f"   Squash: Yes")
    if delete_source:
        console.print(f"   Delete source: Yes")

    if azure.complete_pull_request(pr_id, delete_source, squash):
        console.print(f"\n[green]Pull request completed![/green]")
    else:
        console.print("[red]Failed to complete pull request.[/red]")
        raise typer.Exit(1)


@azure_repos_app.command("abandon")
def abandon_pr(
    pr_id: int = typer.Argument(..., help="PR ID")
):
    """Abandon a pull request."""
    azure = _get_azure_repos()

    if azure.abandon_pull_request(pr_id):
        console.print(f"[green]PR #{pr_id} abandoned.[/green]")
    else:
        console.print("[red]Failed to abandon pull request.[/red]")
        raise typer.Exit(1)