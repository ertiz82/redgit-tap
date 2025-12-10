"""
AWS CodeCommit CLI commands for RedGit.

Commands:
- rg codecommit status   : Show connection status
- rg codecommit repos    : List repositories
- rg codecommit prs      : List pull requests
- rg codecommit pr       : Create pull request
- rg codecommit branches : List branches
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
codecommit_app = typer.Typer(help="AWS CodeCommit repository management")


def _get_codecommit():
    """Get configured CodeCommit integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    codecommit = get_code_hosting(config, "codecommit")

    if not codecommit:
        console.print("[red]CodeCommit integration not configured.[/red]")
        console.print("[dim]Run 'rg install codecommit' to set up[/dim]")
        raise typer.Exit(1)

    return codecommit


@codecommit_app.command("status")
def status_cmd():
    """Show CodeCommit connection status."""
    codecommit = _get_codecommit()

    console.print("\n[bold cyan]AWS CodeCommit Status[/bold cyan]\n")

    repo = codecommit.get_repo_info()
    if repo:
        console.print(f"   [green]Connected[/green]")
        console.print(f"   Repository: {repo.get('repositoryName')}")
        console.print(f"   Region: {codecommit.region}")
        console.print(f"   Default branch: {repo.get('defaultBranch', '-')}")
        console.print(f"   ARN: {repo.get('Arn', '-')}")
    else:
        console.print(f"   [red]Not connected[/red]")
        console.print(f"   [dim]Check AWS credentials and repository name[/dim]")


@codecommit_app.command("repos")
def list_repos():
    """List repositories."""
    codecommit = _get_codecommit()

    console.print("\n[bold cyan]CodeCommit Repositories[/bold cyan]\n")

    repos = codecommit.list_repositories()
    if not repos:
        console.print("[yellow]No repositories found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Repository", style="cyan")
    table.add_column("ID", style="dim")

    for r in repos:
        is_current = " *" if r.get("repositoryName") == codecommit.repository_name else ""
        table.add_row(
            r.get("repositoryName", "-") + is_current,
            r.get("repositoryId", "-")[:12]
        )

    console.print(table)


@codecommit_app.command("info")
def repo_info():
    """Show repository information."""
    codecommit = _get_codecommit()

    console.print("\n[bold cyan]Repository Info[/bold cyan]\n")

    repo = codecommit.get_repo_info()
    if not repo:
        console.print("[red]Repository not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Name: {repo.get('repositoryName')}")
    console.print(f"   Description: {repo.get('repositoryDescription') or '-'}")
    console.print(f"   Default branch: {repo.get('defaultBranch', '-')}")
    console.print(f"   Clone URL (HTTPS): {repo.get('cloneUrlHttp', '-')}")
    console.print(f"   Clone URL (SSH): {repo.get('cloneUrlSsh', '-')}")


@codecommit_app.command("prs")
def list_prs(
    status: str = typer.Option("OPEN", "--status", "-s", help="PR status: OPEN, CLOSED")
):
    """List pull requests."""
    codecommit = _get_codecommit()

    console.print(f"\n[bold cyan]Pull Requests ({status})[/bold cyan]\n")

    prs = codecommit.list_pull_requests(status.upper())
    if not prs:
        console.print("[yellow]No pull requests found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan", width=12)
    table.add_column("Title")
    table.add_column("Status", style="dim")

    for pr in prs:
        table.add_row(
            pr.get("pullRequestId", "-"),
            pr.get("title", "-")[:40],
            pr.get("pullRequestStatus", "-")
        )

    console.print(table)


@codecommit_app.command("pr")
def create_pr(
    title: str = typer.Argument(..., help="PR title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="PR description"),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch")
):
    """Create a pull request from current branch."""
    import subprocess
    codecommit = _get_codecommit()

    # Get current branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        console.print("[red]Not in a git repository.[/red]")
        raise typer.Exit(1)

    head_branch = result.stdout.strip()
    base_branch = base or codecommit.default_branch

    if head_branch == base_branch:
        console.print(f"[red]Cannot create PR from {base_branch} to itself.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Creating Pull Request[/bold cyan]\n")
    console.print(f"   From: {head_branch}")
    console.print(f"   To: {base_branch}")

    # Push branch first
    console.print(f"\n   Pushing branch...")
    if not codecommit.push_branch(head_branch):
        console.print("[yellow]   Push failed, branch may already exist[/yellow]")

    # Create PR
    pr_url = codecommit.create_pull_request(
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


@codecommit_app.command("branches")
def list_branches():
    """List repository branches."""
    codecommit = _get_codecommit()

    console.print("\n[bold cyan]Branches[/bold cyan]\n")

    branches = codecommit.list_branches()
    if not branches:
        console.print("[yellow]No branches found.[/yellow]")
        return

    default = codecommit.get_default_branch()

    for name in branches:
        marker = " *" if name == default else ""
        console.print(f"   {name}{marker}")

    console.print(f"\n[dim]* = default branch[/dim]")


@codecommit_app.command("branch")
def create_branch(
    name: str = typer.Argument(..., help="Branch name")
):
    """Create a new branch."""
    codecommit = _get_codecommit()

    console.print(f"\n[bold cyan]Creating branch: {name}[/bold cyan]")

    if codecommit.create_branch(name):
        console.print(f"\n[green]Branch created![/green]")
    else:
        console.print("[red]Failed to create branch.[/red]")
        raise typer.Exit(1)


@codecommit_app.command("delete-branch")
def delete_branch(
    name: str = typer.Argument(..., help="Branch name")
):
    """Delete a branch."""
    codecommit = _get_codecommit()

    if codecommit.delete_branch(name):
        console.print(f"[green]Deleted branch: {name}[/green]")
    else:
        console.print("[red]Failed to delete branch.[/red]")
        raise typer.Exit(1)


@codecommit_app.command("merge")
def merge_pr(
    pr_id: str = typer.Argument(..., help="PR ID"),
    squash: bool = typer.Option(True, "--squash/--no-squash", help="Squash merge")
):
    """Merge a pull request."""
    codecommit = _get_codecommit()

    pr = codecommit.get_pull_request(pr_id)
    if not pr:
        console.print(f"[red]PR {pr_id} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Merging PR {pr_id}[/bold cyan]")
    console.print(f"   Title: {pr.get('title')}")
    console.print(f"   Squash: {'Yes' if squash else 'No'}")

    merge_option = "SQUASH_MERGE" if squash else "FAST_FORWARD_MERGE"
    if codecommit.merge_pull_request(pr_id, merge_option):
        console.print(f"\n[green]Pull request merged![/green]")
    else:
        console.print("[red]Failed to merge pull request.[/red]")
        raise typer.Exit(1)