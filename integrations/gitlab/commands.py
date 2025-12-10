"""
GitLab CLI commands for RedGit.

Commands:
- rg gitlab status   : Show connection status
- rg gitlab projects : List projects
- rg gitlab mrs      : List merge requests
- rg gitlab mr       : Create merge request
- rg gitlab branches : List branches
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
gitlab_app = typer.Typer(help="GitLab repository management")


def _get_gitlab():
    """Get configured GitLab integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    gitlab = get_code_hosting(config, "gitlab")

    if not gitlab:
        console.print("[red]GitLab integration not configured.[/red]")
        console.print("[dim]Run 'rg install gitlab' to set up[/dim]")
        raise typer.Exit(1)

    return gitlab


@gitlab_app.command("status")
def status_cmd():
    """Show GitLab connection status."""
    gitlab = _get_gitlab()

    console.print("\n[bold cyan]GitLab Status[/bold cyan]\n")

    user = gitlab.get_user()
    if user:
        console.print(f"   [green]Connected[/green]")
        console.print(f"   User: {user.get('username')}")
        console.print(f"   Name: {user.get('name', '-')}")
        console.print(f"   Host: {gitlab.host}")
    else:
        console.print(f"   [red]Not connected[/red]")
        return

    console.print(f"\n   Project: {gitlab.project_id}")

    project = gitlab.get_project_info()
    if project:
        console.print(f"   Default branch: {project.get('default_branch')}")
        console.print(f"   Visibility: {project.get('visibility')}")
    else:
        console.print(f"   [yellow]Project not found or no access[/yellow]")


@gitlab_app.command("projects")
def list_projects():
    """List your projects."""
    gitlab = _get_gitlab()

    console.print("\n[bold cyan]Your Projects[/bold cyan]\n")

    projects = gitlab.list_projects()
    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Project", style="cyan")
    table.add_column("Description")
    table.add_column("Visibility", justify="center")

    for p in projects[:20]:
        table.add_row(
            p["path_with_namespace"],
            (p.get("description") or "-")[:40],
            p.get("visibility", "-")
        )

    console.print(table)
    console.print(f"\n[dim]Showing {min(20, len(projects))} of {len(projects)} projects[/dim]")


@gitlab_app.command("info")
def project_info():
    """Show project information."""
    gitlab = _get_gitlab()

    console.print("\n[bold cyan]Project Info[/bold cyan]\n")

    project = gitlab.get_project_info()
    if not project:
        console.print("[red]Project not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Name: {project['path_with_namespace']}")
    console.print(f"   Description: {project.get('description') or '-'}")
    console.print(f"   Default branch: {project.get('default_branch')}")
    console.print(f"   Visibility: {project.get('visibility')}")
    console.print(f"   Stars: {project.get('star_count', 0)}")
    console.print(f"   Forks: {project.get('forks_count', 0)}")
    console.print(f"   URL: {project.get('web_url')}")


@gitlab_app.command("mrs")
def list_mrs(
    state: str = typer.Option("opened", "--state", "-s", help="MR state: opened, closed, merged, all")
):
    """List merge requests."""
    gitlab = _get_gitlab()

    console.print(f"\n[bold cyan]Merge Requests ({state})[/bold cyan]\n")

    mrs = gitlab.list_merge_requests(state)
    if not mrs:
        console.print("[yellow]No merge requests found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("!", style="cyan", width=5)
    table.add_column("Title")
    table.add_column("Author", style="dim")
    table.add_column("Branch")

    for mr in mrs[:20]:
        table.add_row(
            f"!{mr['iid']}",
            mr["title"][:40] + ("..." if len(mr["title"]) > 40 else ""),
            mr["author"]["username"],
            mr["source_branch"]
        )

    console.print(table)


@gitlab_app.command("mr")
def create_mr(
    title: str = typer.Argument(..., help="MR title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="MR description"),
    base: Optional[str] = typer.Option(None, "--base", help="Target branch")
):
    """Create a merge request from current branch."""
    import subprocess
    gitlab = _get_gitlab()

    # Get current branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        console.print("[red]Not in a git repository.[/red]")
        raise typer.Exit(1)

    head_branch = result.stdout.strip()
    base_branch = base or gitlab.default_branch

    if head_branch == base_branch:
        console.print(f"[red]Cannot create MR from {base_branch} to itself.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Creating Merge Request[/bold cyan]\n")
    console.print(f"   From: {head_branch}")
    console.print(f"   To: {base_branch}")

    # Push branch first
    console.print(f"\n   Pushing branch...")
    if not gitlab.push_branch(head_branch):
        console.print("[yellow]   Push failed, branch may already exist[/yellow]")

    # Create MR
    mr_url = gitlab.create_pull_request(
        title=title,
        body=body or "",
        head_branch=head_branch,
        base_branch=base_branch
    )

    if mr_url:
        console.print(f"\n[green]Merge request created![/green]")
        console.print(f"   {mr_url}")
    else:
        console.print("[red]Failed to create merge request.[/red]")
        raise typer.Exit(1)


@gitlab_app.command("branches")
def list_branches():
    """List repository branches."""
    gitlab = _get_gitlab()

    console.print("\n[bold cyan]Branches[/bold cyan]\n")

    branches = gitlab.list_branches()
    if not branches:
        console.print("[yellow]No branches found.[/yellow]")
        return

    default = gitlab.get_default_branch()

    for b in branches:
        name = b["name"]
        marker = " *" if name == default else ""
        protected = " [protected]" if b.get("protected") else ""
        console.print(f"   {name}{marker}{protected}")

    console.print(f"\n[dim]* = default branch[/dim]")


@gitlab_app.command("branch")
def create_branch(
    name: str = typer.Argument(..., help="Branch name"),
    from_ref: Optional[str] = typer.Option(None, "--from", "-f", help="Create from this ref")
):
    """Create a new branch."""
    gitlab = _get_gitlab()

    base = from_ref or gitlab.default_branch
    console.print(f"\n[bold cyan]Creating branch[/bold cyan]")
    console.print(f"   Name: {name}")
    console.print(f"   From: {base}")

    if gitlab.create_branch(name, from_ref):
        console.print(f"\n[green]Branch created![/green]")
    else:
        console.print("[red]Failed to create branch.[/red]")
        raise typer.Exit(1)


@gitlab_app.command("delete-branch")
def delete_branch(
    name: str = typer.Argument(..., help="Branch name")
):
    """Delete a branch."""
    gitlab = _get_gitlab()

    if gitlab.delete_branch(name):
        console.print(f"[green]Deleted branch: {name}[/green]")
    else:
        console.print("[red]Failed to delete branch.[/red]")
        raise typer.Exit(1)


@gitlab_app.command("merge")
def merge_mr(
    mr_iid: int = typer.Argument(..., help="MR IID (internal ID)"),
    squash: bool = typer.Option(False, "--squash", help="Squash commits")
):
    """Merge a merge request."""
    gitlab = _get_gitlab()

    mr = gitlab.get_merge_request(mr_iid)
    if not mr:
        console.print(f"[red]MR !{mr_iid} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Merging MR !{mr_iid}[/bold cyan]")
    console.print(f"   Title: {mr['title']}")
    if squash:
        console.print(f"   Squash: Yes")

    if gitlab.merge_merge_request(mr_iid, squash):
        console.print(f"\n[green]Merge request merged![/green]")
    else:
        console.print("[red]Failed to merge request.[/red]")
        raise typer.Exit(1)