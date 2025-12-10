"""
Azure Pipelines CLI commands for RedGit.

Commands:
- rg azure-pipelines status   : Show status overview
- rg azure-pipelines builds   : List builds
- rg azure-pipelines trigger  : Trigger a pipeline
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
azure_pipelines_app = typer.Typer(help="Azure Pipelines management")


def _get_azure():
    """Get configured Azure Pipelines integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    azure = get_cicd(config, "azure-pipelines")

    if not azure:
        console.print("[red]Azure Pipelines integration not configured.[/red]")
        console.print("[dim]Run 'rg install azure-pipelines' to set up[/dim]")
        raise typer.Exit(1)

    return azure


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


@azure_pipelines_app.command("status")
def status_cmd():
    """Show Azure Pipelines status overview."""
    azure = _get_azure()

    console.print("\n[bold cyan]Azure Pipelines Status[/bold cyan]\n")
    console.print(f"   Organization: {azure.organization}")
    console.print(f"   Project: {azure.project}")

    # Get recent builds
    builds = azure.list_pipelines(limit=5)

    if not builds:
        console.print("\n   [yellow]No recent builds[/yellow]")
        return

    console.print("\n   [bold]Recent Builds:[/bold]")
    for b in builds:
        icon = _status_icon(b.status)
        branch = f" ({b.branch})" if b.branch else ""
        console.print(f"   {icon} #{b.id} {b.name}{branch} - {b.status}")


@azure_pipelines_app.command("pipelines")
def list_pipeline_definitions():
    """List pipeline definitions."""
    azure = _get_azure()

    console.print("\n[bold cyan]Pipelines[/bold cyan]\n")

    pipelines = azure.list_workflows()
    if not pipelines:
        console.print("[yellow]No pipelines found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Name")
    table.add_column("Folder", style="dim")

    for p in pipelines:
        table.add_row(
            str(p["id"]),
            p["name"],
            p["folder"] or "-"
        )

    console.print(table)


@azure_pipelines_app.command("builds")
def list_builds(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Filter by branch"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of builds to show")
):
    """List recent builds."""
    azure = _get_azure()

    title = "Builds"
    if branch:
        title += f" ({branch})"
    if status:
        title += f" [{status}]"

    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    builds = azure.list_pipelines(branch=branch, status=status, limit=limit)
    if not builds:
        console.print("[yellow]No builds found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Status", width=10)
    table.add_column("Pipeline")
    table.add_column("Branch")
    table.add_column("Trigger", style="dim")

    for b in builds:
        table.add_row(
            f"#{b.id}",
            _status_icon(b.status),
            b.name[:25],
            b.branch or "-",
            b.trigger or "-"
        )

    console.print(table)


@azure_pipelines_app.command("build")
def show_build(
    build_id: str = typer.Argument(..., help="Build ID")
):
    """Show build details."""
    azure = _get_azure()

    console.print(f"\n[bold cyan]Build #{build_id}[/bold cyan]\n")

    build = azure.get_pipeline_status(build_id)
    if not build:
        console.print("[red]Build not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Pipeline: {build.name}")
    console.print(f"   Status: {_status_icon(build.status)} {build.status}")
    console.print(f"   Branch: {build.branch or '-'}")
    console.print(f"   Commit: {build.commit_sha[:7] if build.commit_sha else '-'}")
    console.print(f"   Trigger: {build.trigger or '-'}")
    console.print(f"   Started: {build.started_at or '-'}")
    if build.url:
        console.print(f"\n   URL: {build.url}")


@azure_pipelines_app.command("timeline")
def show_timeline(
    build_id: str = typer.Argument(..., help="Build ID")
):
    """Show stages/jobs for a build."""
    azure = _get_azure()

    console.print(f"\n[bold cyan]Timeline for Build #{build_id}[/bold cyan]\n")

    jobs = azure.get_pipeline_jobs(build_id)
    if not jobs:
        console.print("[yellow]No timeline records found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Status", width=8)
    table.add_column("Name")
    table.add_column("Started", style="dim")

    for job in jobs:
        table.add_row(
            _status_icon(job.status),
            job.name,
            job.started_at[:16] if job.started_at else "-"
        )

    console.print(table)


@azure_pipelines_app.command("trigger")
def trigger_build(
    pipeline: Optional[str] = typer.Option(None, "--pipeline", "-p", help="Pipeline ID"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to build"),
    param: Optional[List[str]] = typer.Option(None, "--param", help="Parameter KEY=VALUE")
):
    """Trigger a new pipeline run."""
    azure = _get_azure()

    console.print("\n[bold cyan]Triggering Pipeline[/bold cyan]\n")

    # Parse parameters
    params = {}
    if param:
        for p in param:
            if "=" in p:
                key, value = p.split("=", 1)
                params[key] = value

    if pipeline:
        console.print(f"   Pipeline: {pipeline}")
    if branch:
        console.print(f"   Branch: {branch}")
    if params:
        console.print(f"   Parameters: {params}")

    build = azure.trigger_pipeline(branch=branch, workflow=pipeline, inputs=params or None)

    if build:
        console.print(f"\n[green]Pipeline triggered![/green]")
        console.print(f"   Build ID: #{build.id}")
        if build.url:
            console.print(f"   URL: {build.url}")
    else:
        console.print("[red]Failed to trigger pipeline.[/red]")
        raise typer.Exit(1)


@azure_pipelines_app.command("retry")
def retry_build(
    build_id: str = typer.Argument(..., help="Build ID")
):
    """Rebuild a pipeline."""
    azure = _get_azure()

    console.print(f"\n[bold cyan]Rebuilding #{build_id}[/bold cyan]\n")

    build = azure.retry_pipeline(build_id)
    if build:
        console.print("[green]Build queued![/green]")
        console.print(f"   New build ID: #{build.id}")
    else:
        console.print("[red]Failed to rebuild.[/red]")
        raise typer.Exit(1)


@azure_pipelines_app.command("cancel")
def cancel_build(
    build_id: str = typer.Argument(..., help="Build ID")
):
    """Cancel a running build."""
    azure = _get_azure()

    if azure.cancel_pipeline(build_id):
        console.print(f"[green]Cancelled build #{build_id}[/green]")
    else:
        console.print("[red]Failed to cancel build.[/red]")
        raise typer.Exit(1)


@azure_pipelines_app.command("logs")
def show_logs(
    build_id: str = typer.Argument(..., help="Build ID"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show")
):
    """Show build logs."""
    azure = _get_azure()

    console.print(f"\n[bold cyan]Logs for Build #{build_id}[/bold cyan]\n")

    logs = azure.get_build_logs(build_id)
    if logs:
        lines = logs.strip().split("\n")
        if tail and len(lines) > tail:
            lines = lines[-tail:]
        for line in lines:
            console.print(line)
    else:
        console.print("[yellow]No logs available.[/yellow]")