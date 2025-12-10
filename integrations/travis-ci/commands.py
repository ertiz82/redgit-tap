"""
Travis CI CLI commands for RedGit.

Commands:
- rg travis-ci status : Show status overview
- rg travis-ci builds : List builds
- rg travis-ci trigger: Trigger a build
"""

import typer
from rich.console import Console
from rich.table import Table
from typing import Optional

try:
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import get_cicd
except ImportError:
    ConfigManager = None
    get_cicd = None

console = Console()
travis_ci_app = typer.Typer(help="Travis CI management")


def _get_travis():
    """Get configured Travis CI integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    travis = get_cicd(config, "travis-ci")

    if not travis:
        console.print("[red]Travis CI integration not configured.[/red]")
        console.print("[dim]Run 'rg install travis-ci' to set up[/dim]")
        raise typer.Exit(1)

    return travis


def _status_icon(status: str) -> str:
    """Get icon for status."""
    icons = {
        "success": "[green]✓[/green]",
        "failed": "[red]✗[/red]",
        "running": "[yellow]●[/yellow]",
        "pending": "[blue]○[/blue]",
        "cancelled": "[dim]⊘[/dim]"
    }
    return icons.get(status, "?")


@travis_ci_app.command("status")
def status_cmd():
    """Show Travis CI status overview."""
    travis = _get_travis()

    console.print("\n[bold cyan]Travis CI Status[/bold cyan]\n")
    console.print(f"   Repository: {travis.repo_slug}")

    # Get recent builds
    builds = travis.list_pipelines(limit=5)

    if not builds:
        console.print("\n   [yellow]No recent builds[/yellow]")
        return

    console.print("\n   [bold]Recent Builds:[/bold]")
    for b in builds:
        icon = _status_icon(b.status)
        branch = f" ({b.branch})" if b.branch else ""
        console.print(f"   {icon} {b.name}{branch} - {b.status}")


@travis_ci_app.command("builds")
def list_builds(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Filter by branch"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of builds to show")
):
    """List builds."""
    travis = _get_travis()

    title = "Builds"
    if branch:
        title += f" ({branch})"
    if status:
        title += f" [{status}]"

    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    builds = travis.list_pipelines(branch=branch, status=status, limit=limit)
    if not builds:
        console.print("[yellow]No builds found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Build", style="dim", width=12)
    table.add_column("Status", width=10)
    table.add_column("Branch")
    table.add_column("Duration", style="dim")
    table.add_column("Trigger", style="dim")

    for b in builds:
        duration = f"{b.duration}s" if b.duration else "-"
        table.add_row(
            b.name,
            _status_icon(b.status),
            b.branch or "-",
            duration,
            b.trigger or "-"
        )

    console.print(table)


@travis_ci_app.command("build")
def show_build(
    build_id: str = typer.Argument(..., help="Build ID")
):
    """Show build details."""
    travis = _get_travis()

    console.print(f"\n[bold cyan]Build #{build_id}[/bold cyan]\n")

    build = travis.get_pipeline_status(build_id)
    if not build:
        console.print("[red]Build not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Status: {_status_icon(build.status)} {build.status}")
    console.print(f"   Branch: {build.branch or '-'}")
    console.print(f"   Commit: {build.commit_sha[:7] if build.commit_sha else '-'}")
    console.print(f"   Duration: {build.duration}s" if build.duration else "   Duration: -")
    console.print(f"   Trigger: {build.trigger or '-'}")
    if build.url:
        console.print(f"\n   URL: {build.url}")


@travis_ci_app.command("jobs")
def show_jobs(
    build_id: str = typer.Argument(..., help="Build ID")
):
    """Show jobs for a build."""
    travis = _get_travis()

    console.print(f"\n[bold cyan]Jobs for Build #{build_id}[/bold cyan]\n")

    jobs = travis.get_pipeline_jobs(build_id)
    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Job", style="dim", width=10)
    table.add_column("Status", width=10)
    table.add_column("Stage")
    table.add_column("Duration", style="dim")

    for job in jobs:
        duration = f"{job.duration}s" if job.duration else "-"
        table.add_row(
            job.name,
            _status_icon(job.status),
            job.stage or "-",
            duration
        )

    console.print(table)


@travis_ci_app.command("trigger")
def trigger_build(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to build")
):
    """Trigger a new build."""
    travis = _get_travis()

    console.print("\n[bold cyan]Triggering Build[/bold cyan]\n")

    if branch:
        console.print(f"   Branch: {branch}")

    build = travis.trigger_pipeline(branch=branch)

    if build:
        console.print(f"\n[green]Build requested![/green]")
        console.print(f"   Request ID: {build.id}")
    else:
        console.print("[red]Failed to trigger build.[/red]")
        raise typer.Exit(1)


@travis_ci_app.command("restart")
def restart_build(
    build_id: str = typer.Argument(..., help="Build ID")
):
    """Restart a build."""
    travis = _get_travis()

    console.print(f"\n[bold cyan]Restarting Build #{build_id}[/bold cyan]\n")

    build = travis.retry_pipeline(build_id)
    if build:
        console.print("[green]Build restarted![/green]")
    else:
        console.print("[red]Failed to restart build.[/red]")
        raise typer.Exit(1)


@travis_ci_app.command("cancel")
def cancel_build(
    build_id: str = typer.Argument(..., help="Build ID")
):
    """Cancel a running build."""
    travis = _get_travis()

    if travis.cancel_pipeline(build_id):
        console.print(f"[green]Cancelled build #{build_id}[/green]")
    else:
        console.print("[red]Failed to cancel build.[/red]")
        raise typer.Exit(1)


@travis_ci_app.command("logs")
def show_logs(
    job_id: str = typer.Argument(..., help="Job ID"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show")
):
    """Show job logs."""
    travis = _get_travis()

    console.print(f"\n[bold cyan]Logs for Job #{job_id}[/bold cyan]\n")

    logs = travis.get_job_log(job_id)
    if logs:
        lines = logs.strip().split("\n")
        if tail and len(lines) > tail:
            lines = lines[-tail:]
        for line in lines:
            console.print(line)
    else:
        console.print("[yellow]No logs available.[/yellow]")