"""
GitHub CLI commands for RedGit.

Commands:
- rg github status   : Show connection status
- rg github repos    : List repositories
- rg github prs      : List pull requests
- rg github pr       : Create pull request
- rg github branches : List branches
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
github_app = typer.Typer(help="GitHub repository management")


def _get_github():
    """Get configured GitHub integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    github = get_code_hosting(config, "github")

    if not github:
        console.print("[red]GitHub integration not configured.[/red]")
        console.print("[dim]Run 'rg install github' to set up[/dim]")
        raise typer.Exit(1)

    return github


@github_app.command("status")
def status_cmd():
    """Show GitHub connection status."""
    github = _get_github()

    console.print("\n[bold cyan]GitHub Status[/bold cyan]\n")

    user = github.get_user()
    if user:
        console.print(f"   [green]Connected[/green]")
        console.print(f"   User: {user.get('login')}")
        console.print(f"   Name: {user.get('name', '-')}")
    else:
        console.print(f"   [red]Not connected[/red]")
        return

    console.print(f"\n   Repository: {github.owner}/{github.repo}")

    repo = github.get_repo_info()
    if repo:
        console.print(f"   Default branch: {repo.get('default_branch')}")
        console.print(f"   Private: {'Yes' if repo.get('private') else 'No'}")
    else:
        console.print(f"   [yellow]Repository not found or no access[/yellow]")


@github_app.command("repos")
def list_repos():
    """List your repositories."""
    github = _get_github()

    console.print("\n[bold cyan]Your Repositories[/bold cyan]\n")

    repos = github.list_user_repos()
    if not repos:
        console.print("[yellow]No repositories found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Repository", style="cyan")
    table.add_column("Description")
    table.add_column("Private", justify="center")

    for r in repos[:20]:
        table.add_row(
            r["full_name"],
            (r.get("description") or "-")[:40],
            "Yes" if r.get("private") else "No"
        )

    console.print(table)
    console.print(f"\n[dim]Showing {min(20, len(repos))} of {len(repos)} repos[/dim]")


@github_app.command("info")
def repo_info():
    """Show repository information."""
    github = _get_github()

    console.print("\n[bold cyan]Repository Info[/bold cyan]\n")

    repo = github.get_repo_info()
    if not repo:
        console.print("[red]Repository not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Name: {repo['full_name']}")
    console.print(f"   Description: {repo.get('description') or '-'}")
    console.print(f"   Default branch: {repo.get('default_branch')}")
    console.print(f"   Private: {'Yes' if repo.get('private') else 'No'}")
    console.print(f"   Stars: {repo.get('stargazers_count', 0)}")
    console.print(f"   Forks: {repo.get('forks_count', 0)}")
    console.print(f"   URL: {repo.get('html_url')}")


@github_app.command("prs")
def list_prs(
    state: str = typer.Option("open", "--state", "-s", help="PR state: open, closed, all")
):
    """List pull requests."""
    github = _get_github()

    console.print(f"\n[bold cyan]Pull Requests ({state})[/bold cyan]\n")

    prs = github.list_pull_requests(state)
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
            f"#{pr['number']}",
            pr["title"][:40] + ("..." if len(pr["title"]) > 40 else ""),
            pr["user"]["login"],
            pr["head"]["ref"]
        )

    console.print(table)


@github_app.command("pr")
def create_pr(
    title: str = typer.Argument(..., help="PR title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="PR description"),
    base: Optional[str] = typer.Option(None, "--base", help="Base branch")
):
    """Create a pull request from current branch."""
    import subprocess
    github = _get_github()

    # Get current branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        console.print("[red]Not in a git repository.[/red]")
        raise typer.Exit(1)

    head_branch = result.stdout.strip()
    base_branch = base or github.default_branch

    if head_branch == base_branch:
        console.print(f"[red]Cannot create PR from {base_branch} to itself.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Creating Pull Request[/bold cyan]\n")
    console.print(f"   From: {head_branch}")
    console.print(f"   To: {base_branch}")

    # Push branch first
    console.print(f"\n   Pushing branch...")
    if not github.push_branch(head_branch):
        console.print("[yellow]   Push failed, branch may already exist[/yellow]")

    # Create PR
    pr_url = github.create_pull_request(
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


@github_app.command("branches")
def list_branches():
    """List repository branches."""
    github = _get_github()

    console.print("\n[bold cyan]Branches[/bold cyan]\n")

    branches = github.list_branches()
    if not branches:
        console.print("[yellow]No branches found.[/yellow]")
        return

    default = github.get_default_branch()

    for b in branches:
        name = b["name"]
        marker = " *" if name == default else ""
        console.print(f"   {name}{marker}")

    console.print(f"\n[dim]* = default branch[/dim]")


@github_app.command("branch")
def create_branch(
    name: str = typer.Argument(..., help="Branch name"),
    from_ref: Optional[str] = typer.Option(None, "--from", "-f", help="Create from this ref")
):
    """Create a new branch."""
    github = _get_github()

    base = from_ref or github.default_branch
    console.print(f"\n[bold cyan]Creating branch[/bold cyan]")
    console.print(f"   Name: {name}")
    console.print(f"   From: {base}")

    if github.create_branch(name, from_ref):
        console.print(f"\n[green]Branch created![/green]")
    else:
        console.print("[red]Failed to create branch.[/red]")
        raise typer.Exit(1)


@github_app.command("delete-branch")
def delete_branch(
    name: str = typer.Argument(..., help="Branch name")
):
    """Delete a branch."""
    github = _get_github()

    if github.delete_branch(name):
        console.print(f"[green]Deleted branch: {name}[/green]")
    else:
        console.print("[red]Failed to delete branch.[/red]")
        raise typer.Exit(1)


@github_app.command("merge")
def merge_pr(
    pr_number: int = typer.Argument(..., help="PR number"),
    method: str = typer.Option("merge", "--method", "-m", help="Merge method: merge, squash, rebase")
):
    """Merge a pull request."""
    github = _get_github()

    pr = github.get_pull_request(pr_number)
    if not pr:
        console.print(f"[red]PR #{pr_number} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Merging PR #{pr_number}[/bold cyan]")
    console.print(f"   Title: {pr['title']}")
    console.print(f"   Method: {method}")

    if github.merge_pull_request(pr_number, method):
        console.print(f"\n[green]Pull request merged![/green]")
    else:
        console.print("[red]Failed to merge pull request.[/red]")
        raise typer.Exit(1)