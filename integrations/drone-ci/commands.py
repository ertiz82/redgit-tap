"""
Drone CI CLI commands for RedGit.

Commands:
- rg drone-ci status  : Show status overview
- rg drone-ci builds  : List builds
- rg drone-ci trigger : Trigger a build
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
drone_ci_app = typer.Typer(help="Drone CI management")


def _get_drone():
    """Get configured Drone CI integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    drone = get_cicd(config, "drone-ci")

    if not drone:
        console.print("[red]Drone CI integration not configured.[/red]")
        console.print("[dim]Run 'rg install drone-ci' to set up[/dim]")
        raise typer.Exit(1)

    return drone


def _status_icon(status: str) -> str:
    """Get icon for status."""
    icons = {
        "success": "[green]✓[/green]",
        "failed": "[red]✗[/red]",
        "running": "[yellow]●[/yellow]",
        "pending": "[blue]○[/blue]",
        "cancelled": "[dim]⊘[/dim]",
        "blocked": "[cyan]◐[/cyan]",
        "skipped": "[dim]⊖[/dim]"
    }
    return icons.get(status, "?")


@drone_ci_app.command("status")
def status_cmd():
    """Show Drone CI status overview."""
    drone = _get_drone()

    console.print("\n[bold cyan]Drone CI Status[/bold cyan]\n")
    console.print(f"   Server: {drone.server}")
    console.print(f"   Repository: {drone.owner}/{drone.repo}")

    # Get recent builds
    builds = drone.list_pipelines(limit=5)

    if not builds:
        console.print("\n   [yellow]No recent builds[/yellow]")
        return

    console.print("\n   [bold]Recent Builds:[/bold]")
    for b in builds:
        icon = _status_icon(b.status)
        branch = f" ({b.branch})" if b.branch else ""
        console.print(f"   {icon} {b.name}{branch} - {b.status}")


@drone_ci_app.command("builds")
def list_builds(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Filter by branch"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of builds to show")
):
    """List builds."""
    drone = _get_drone()

    title = "Builds"
    if branch:
        title += f" ({branch})"
    if status:
        title += f" [{status}]"

    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    builds = drone.list_pipelines(branch=branch, status=status, limit=limit)
    if not builds:
        console.print("[yellow]No builds found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Build", style="dim", width=10)
    table.add_column("Status", width=10)
    table.add_column("Branch")
    table.add_column("Duration", style="dim")
    table.add_column("Event", style="dim")

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


@drone_ci_app.command("build")
def show_build(
    build_number: str = typer.Argument(..., help="Build number")
):
    """Show build details."""
    drone = _get_drone()

    console.print(f"\n[bold cyan]Build #{build_number}[/bold cyan]\n")

    build = drone.get_pipeline_status(build_number)
    if not build:
        console.print("[red]Build not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Status: {_status_icon(build.status)} {build.status}")
    console.print(f"   Branch: {build.branch or '-'}")
    console.print(f"   Commit: {build.commit_sha[:7] if build.commit_sha else '-'}")
    console.print(f"   Duration: {build.duration}s" if build.duration else "   Duration: -")
    console.print(f"   Event: {build.trigger or '-'}")
    if build.url:
        console.print(f"\n   URL: {build.url}")


@drone_ci_app.command("stages")
def show_stages(
    build_number: str = typer.Argument(..., help="Build number")
):
    """Show stages for a build."""
    drone = _get_drone()

    console.print(f"\n[bold cyan]Stages for Build #{build_number}[/bold cyan]\n")

    stages = drone.get_pipeline_jobs(build_number)
    if not stages:
        console.print("[yellow]No stages found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Status", width=10)
    table.add_column("Stage")
    table.add_column("Duration", style="dim")

    for stage in stages:
        duration = f"{stage.duration}s" if stage.duration else "-"
        table.add_row(
            stage.id,
            _status_icon(stage.status),
            stage.name,
            duration
        )

    console.print(table)


@drone_ci_app.command("trigger")
def trigger_build(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to build"),
    param: Optional[List[str]] = typer.Option(None, "--param", "-p", help="Parameter KEY=VALUE")
):
    """Trigger a new build."""
    drone = _get_drone()

    console.print("\n[bold cyan]Triggering Build[/bold cyan]\n")

    # Parse parameters
    params = {}
    if param:
        for p in param:
            if "=" in p:
                key, value = p.split("=", 1)
                params[key] = value

    if branch:
        console.print(f"   Branch: {branch}")
    if params:
        console.print(f"   Parameters: {params}")

    build = drone.trigger_pipeline(branch=branch, inputs=params or None)

    if build:
        console.print(f"\n[green]Build triggered![/green]")
        console.print(f"   {build.name}")
        if build.url:
            console.print(f"   URL: {build.url}")
    else:
        console.print("[red]Failed to trigger build.[/red]")
        raise typer.Exit(1)


@drone_ci_app.command("restart")
def restart_build(
    build_number: str = typer.Argument(..., help="Build number")
):
    """Restart a build."""
    drone = _get_drone()

    console.print(f"\n[bold cyan]Restarting Build #{build_number}[/bold cyan]\n")

    build = drone.retry_pipeline(build_number)
    if build:
        console.print("[green]Build restarted![/green]")
        console.print(f"   {build.name}")
    else:
        console.print("[red]Failed to restart build.[/red]")
        raise typer.Exit(1)


@drone_ci_app.command("cancel")
def cancel_build(
    build_number: str = typer.Argument(..., help="Build number")
):
    """Cancel a running build."""
    drone = _get_drone()

    if drone.cancel_pipeline(build_number):
        console.print(f"[green]Cancelled build #{build_number}[/green]")
    else:
        console.print("[red]Failed to cancel build.[/red]")
        raise typer.Exit(1)


@drone_ci_app.command("logs")
def show_logs(
    build_number: str = typer.Argument(..., help="Build number"),
    stage: int = typer.Option(1, "--stage", "-s", help="Stage number"),
    step: int = typer.Option(1, "--step", help="Step number"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show")
):
    """Show build logs."""
    drone = _get_drone()

    console.print(f"\n[bold cyan]Logs for Build #{build_number} (stage {stage}, step {step})[/bold cyan]\n")

    logs = drone.get_build_logs(build_number, stage=stage, step=step)
    if logs:
        lines = logs.strip().split("\n")
        if tail and len(lines) > tail:
            lines = lines[-tail:]
        for line in lines:
            console.print(line)
    else:
        console.print("[yellow]No logs available.[/yellow]")


@drone_ci_app.command("promote")
def promote_build(
    build_number: str = typer.Argument(..., help="Build number"),
    target: str = typer.Option(..., "--target", "-t", help="Target environment"),
    param: Optional[List[str]] = typer.Option(None, "--param", "-p", help="Parameter KEY=VALUE")
):
    """Promote a build to another environment."""
    drone = _get_drone()

    console.print(f"\n[bold cyan]Promoting Build #{build_number} to {target}[/bold cyan]\n")

    # Parse parameters
    params = {}
    if param:
        for p in param:
            if "=" in p:
                key, value = p.split("=", 1)
                params[key] = value

    build = drone.promote_build(build_number, target, params or None)

    if build:
        console.print("[green]Build promoted![/green]")
        console.print(f"   {build.name}")
    else:
        console.print("[red]Failed to promote build.[/red]")
        raise typer.Exit(1)


@drone_ci_app.command("approve")
def approve_stage(
    build_number: str = typer.Argument(..., help="Build number"),
    stage: int = typer.Option(..., "--stage", "-s", help="Stage number to approve")
):
    """Approve a blocked stage."""
    drone = _get_drone()

    if drone.approve_build(build_number, stage):
        console.print(f"[green]Approved stage {stage} for build #{build_number}[/green]")
    else:
        console.print("[red]Failed to approve stage.[/red]")
        raise typer.Exit(1)


@drone_ci_app.command("decline")
def decline_stage(
    build_number: str = typer.Argument(..., help="Build number"),
    stage: int = typer.Option(..., "--stage", "-s", help="Stage number to decline")
):
    """Decline a blocked stage."""
    drone = _get_drone()

    if drone.decline_build(build_number, stage):
        console.print(f"[green]Declined stage {stage} for build #{build_number}[/green]")
    else:
        console.print("[red]Failed to decline stage.[/red]")
        raise typer.Exit(1)