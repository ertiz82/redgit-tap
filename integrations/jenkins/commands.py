"""
Jenkins CLI commands for RedGit.

Commands:
- rg jenkins status  : Show status overview
- rg jenkins jobs    : List jobs
- rg jenkins builds  : List builds
- rg jenkins trigger : Trigger a build
"""

import typer
from rich.console import Console
from rich.table import Table
from typing import Optional, List

try:
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import get_cicd
except ImportError:
    ConfigManager = None
    get_cicd = None

console = Console()
jenkins_app = typer.Typer(help="Jenkins CI/CD management")


def _get_jenkins():
    """Get configured Jenkins integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    jenkins = get_cicd(config, "jenkins")

    if not jenkins:
        console.print("[red]Jenkins integration not configured.[/red]")
        console.print("[dim]Run 'rg install jenkins' to set up[/dim]")
        raise typer.Exit(1)

    return jenkins


def _status_icon(status: str) -> str:
    """Get icon for status."""
    icons = {
        "success": "[green]✓[/green]",
        "failed": "[red]✗[/red]",
        "unstable": "[yellow]⚠[/yellow]",
        "running": "[yellow]●[/yellow]",
        "pending": "[blue]○[/blue]",
        "cancelled": "[dim]⊘[/dim]",
        "disabled": "[dim]⊖[/dim]"
    }
    return icons.get(status, "?")


@jenkins_app.command("status")
def status_cmd():
    """Show Jenkins status overview."""
    jenkins = _get_jenkins()

    console.print("\n[bold cyan]Jenkins Status[/bold cyan]\n")
    console.print(f"   Server: {jenkins.url}")
    if jenkins.job_name:
        console.print(f"   Default Job: {jenkins.job_name}")

    # Get recent builds
    builds = jenkins.list_pipelines(limit=5)

    if not builds:
        console.print("\n   [yellow]No recent builds[/yellow]")
        return

    console.print("\n   [bold]Recent Builds:[/bold]")
    for b in builds:
        icon = _status_icon(b.status)
        duration = f" ({b.duration}s)" if b.duration else ""
        console.print(f"   {icon} #{b.id} - {b.status}{duration}")


@jenkins_app.command("jobs")
def list_jobs():
    """List available jobs."""
    jenkins = _get_jenkins()

    console.print("\n[bold cyan]Jenkins Jobs[/bold cyan]\n")

    jobs = jenkins.list_jobs()
    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Name")
    table.add_column("Status", width=10)
    table.add_column("Last Build", style="dim")

    for job in jobs:
        table.add_row(
            job["name"],
            _status_icon(job["status"]),
            f"#{job['last_build']}" if job["last_build"] else "-"
        )

    console.print(table)


@jenkins_app.command("builds")
def list_builds(
    job: Optional[str] = typer.Option(None, "--job", "-j", help="Job name"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of builds to show")
):
    """List recent builds."""
    jenkins = _get_jenkins()

    if job:
        jenkins.job_name = job

    title = f"Builds ({jenkins.job_name})" if jenkins.job_name else "Builds"
    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    builds = jenkins.list_pipelines(status=status, limit=limit)
    if not builds:
        console.print("[yellow]No builds found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Build", style="dim", width=8)
    table.add_column("Status", width=10)
    table.add_column("Duration", style="dim")
    table.add_column("Trigger", style="dim")

    for b in builds:
        duration = f"{b.duration}s" if b.duration else "-"
        table.add_row(
            f"#{b.id}",
            _status_icon(b.status),
            duration,
            b.trigger or "-"
        )

    console.print(table)


@jenkins_app.command("build")
def show_build(
    build_number: str = typer.Argument(..., help="Build number"),
    job: Optional[str] = typer.Option(None, "--job", "-j", help="Job name")
):
    """Show build details."""
    jenkins = _get_jenkins()

    if job:
        jenkins.job_name = job

    console.print(f"\n[bold cyan]Build #{build_number}[/bold cyan]\n")

    build = jenkins.get_pipeline_status(build_number)
    if not build:
        console.print("[red]Build not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Job: {build.name}")
    console.print(f"   Status: {_status_icon(build.status)} {build.status}")
    if build.duration:
        console.print(f"   Duration: {build.duration}s")
    if build.branch:
        console.print(f"   Branch: {build.branch}")
    if build.trigger:
        console.print(f"   Trigger: {build.trigger}")
    if build.url:
        console.print(f"\n   URL: {build.url}")


@jenkins_app.command("trigger")
def trigger_build(
    job: Optional[str] = typer.Option(None, "--job", "-j", help="Job name"),
    param: Optional[List[str]] = typer.Option(None, "--param", "-p", help="Parameter KEY=VALUE")
):
    """Trigger a new build."""
    jenkins = _get_jenkins()

    if job:
        jenkins.job_name = job

    console.print(f"\n[bold cyan]Triggering {jenkins.job_name}[/bold cyan]\n")

    # Parse parameters
    params = {}
    if param:
        for p in param:
            if "=" in p:
                key, value = p.split("=", 1)
                params[key] = value

    if params:
        console.print(f"   Parameters: {params}")

    build = jenkins.trigger_pipeline(inputs=params or None)

    if build:
        console.print(f"\n[green]Build triggered![/green]")
        console.print(f"   Build: #{build.id}")
        if build.url:
            console.print(f"   URL: {build.url}")
    else:
        console.print("[yellow]Build queued.[/yellow]")
        console.print("[dim]Check Jenkins for the new build.[/dim]")


@jenkins_app.command("cancel")
def cancel_build(
    build_number: str = typer.Argument(..., help="Build number"),
    job: Optional[str] = typer.Option(None, "--job", "-j", help="Job name")
):
    """Stop a running build."""
    jenkins = _get_jenkins()

    if job:
        jenkins.job_name = job

    if jenkins.cancel_pipeline(build_number):
        console.print(f"[green]Stopped build #{build_number}[/green]")
    else:
        console.print("[red]Failed to stop build.[/red]")
        raise typer.Exit(1)


@jenkins_app.command("logs")
def show_logs(
    build_number: str = typer.Argument(..., help="Build number"),
    job: Optional[str] = typer.Option(None, "--job", "-j", help="Job name"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show")
):
    """Show build console output."""
    jenkins = _get_jenkins()

    if job:
        jenkins.job_name = job

    console.print(f"\n[bold cyan]Console Output - Build #{build_number}[/bold cyan]\n")

    logs = jenkins.get_pipeline_logs(build_number)
    if logs:
        lines = logs.strip().split("\n")
        if tail and len(lines) > tail:
            lines = lines[-tail:]
        for line in lines:
            console.print(line)
    else:
        console.print("[yellow]No logs available.[/yellow]")


@jenkins_app.command("queue")
def show_queue():
    """Show build queue."""
    jenkins = _get_jenkins()

    console.print("\n[bold cyan]Build Queue[/bold cyan]\n")

    queue = jenkins.get_queue()
    if not queue:
        console.print("[green]Queue is empty.[/green]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Job")
    table.add_column("Reason", style="dim")
    table.add_column("Stuck")

    for item in queue:
        stuck = "[red]Yes[/red]" if item["stuck"] else "[green]No[/green]"
        table.add_row(
            str(item["id"]),
            item["task"] or "-",
            (item["why"] or "-")[:40],
            stuck
        )

    console.print(table)