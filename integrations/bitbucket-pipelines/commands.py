"""
Bitbucket Pipelines CLI commands for RedGit.

Commands:
- rg bitbucket-pipelines status    : Show status overview
- rg bitbucket-pipelines pipelines : List pipelines
- rg bitbucket-pipelines trigger   : Trigger a pipeline
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
bitbucket_pipelines_app = typer.Typer(help="Bitbucket Pipelines management")


def _get_bitbucket():
    """Get configured Bitbucket Pipelines integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    bb = get_cicd(config, "bitbucket-pipelines")

    if not bb:
        console.print("[red]Bitbucket Pipelines integration not configured.[/red]")
        console.print("[dim]Run 'rg install bitbucket-pipelines' to set up[/dim]")
        raise typer.Exit(1)

    return bb


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


@bitbucket_pipelines_app.command("status")
def status_cmd():
    """Show Bitbucket Pipelines status overview."""
    bb = _get_bitbucket()

    console.print("\n[bold cyan]Bitbucket Pipelines Status[/bold cyan]\n")
    console.print(f"   Repository: {bb.workspace}/{bb.repo_slug}")

    # Get recent pipelines
    pipelines = bb.list_pipelines(limit=5)

    if not pipelines:
        console.print("\n   [yellow]No recent pipelines[/yellow]")
        return

    console.print("\n   [bold]Recent Pipelines:[/bold]")
    for p in pipelines:
        icon = _status_icon(p.status)
        branch = f" ({p.branch})" if p.branch else ""
        console.print(f"   {icon} {p.name}{branch} - {p.status}")


@bitbucket_pipelines_app.command("pipelines")
def list_pipelines(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Filter by branch"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of pipelines to show")
):
    """List pipelines."""
    bb = _get_bitbucket()

    title = "Pipelines"
    if branch:
        title += f" ({branch})"
    if status:
        title += f" [{status}]"

    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    pipelines = bb.list_pipelines(branch=branch, status=status, limit=limit)
    if not pipelines:
        console.print("[yellow]No pipelines found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Pipeline", width=15)
    table.add_column("Status", width=10)
    table.add_column("Branch")
    table.add_column("Duration", style="dim")
    table.add_column("Trigger", style="dim")

    for p in pipelines:
        duration = f"{p.duration}s" if p.duration else "-"
        table.add_row(
            p.name,
            _status_icon(p.status),
            p.branch or "-",
            duration,
            p.trigger or "-"
        )

    console.print(table)


@bitbucket_pipelines_app.command("pipeline")
def show_pipeline(
    pipeline_uuid: str = typer.Argument(..., help="Pipeline UUID")
):
    """Show pipeline details."""
    bb = _get_bitbucket()

    console.print(f"\n[bold cyan]Pipeline {pipeline_uuid[:8]}[/bold cyan]\n")

    pipeline = bb.get_pipeline_status(pipeline_uuid)
    if not pipeline:
        console.print("[red]Pipeline not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Status: {_status_icon(pipeline.status)} {pipeline.status}")
    console.print(f"   Branch: {pipeline.branch or '-'}")
    console.print(f"   Commit: {pipeline.commit_sha[:7] if pipeline.commit_sha else '-'}")
    console.print(f"   Duration: {pipeline.duration}s" if pipeline.duration else "   Duration: -")
    console.print(f"   Trigger: {pipeline.trigger or '-'}")
    if pipeline.url:
        console.print(f"\n   URL: {pipeline.url}")


@bitbucket_pipelines_app.command("steps")
def show_steps(
    pipeline_uuid: str = typer.Argument(..., help="Pipeline UUID")
):
    """Show steps for a pipeline."""
    bb = _get_bitbucket()

    console.print(f"\n[bold cyan]Steps for Pipeline {pipeline_uuid[:8]}[/bold cyan]\n")

    steps = bb.get_pipeline_jobs(pipeline_uuid)
    if not steps:
        console.print("[yellow]No steps found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Status", width=8)
    table.add_column("Step")
    table.add_column("Duration", style="dim")

    for step in steps:
        duration = f"{step.duration}s" if step.duration else "-"
        table.add_row(
            _status_icon(step.status),
            step.name,
            duration
        )

    console.print(table)


@bitbucket_pipelines_app.command("trigger")
def trigger_pipeline(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to build"),
    custom: Optional[str] = typer.Option(None, "--custom", "-c", help="Custom pipeline name"),
    var: Optional[List[str]] = typer.Option(None, "--var", "-v", help="Variable KEY=VALUE")
):
    """Trigger a new pipeline."""
    bb = _get_bitbucket()

    console.print("\n[bold cyan]Triggering Pipeline[/bold cyan]\n")

    # Parse variables
    variables = {}
    if var:
        for v in var:
            if "=" in v:
                key, value = v.split("=", 1)
                variables[key] = value

    if branch:
        console.print(f"   Branch: {branch}")
    if custom:
        console.print(f"   Custom: {custom}")
    if variables:
        console.print(f"   Variables: {variables}")

    pipeline = bb.trigger_pipeline(branch=branch, workflow=custom, inputs=variables or None)

    if pipeline:
        console.print(f"\n[green]Pipeline triggered![/green]")
        console.print(f"   {pipeline.name}")
        if pipeline.url:
            console.print(f"   URL: {pipeline.url}")
    else:
        console.print("[red]Failed to trigger pipeline.[/red]")
        raise typer.Exit(1)


@bitbucket_pipelines_app.command("stop")
def stop_pipeline(
    pipeline_uuid: str = typer.Argument(..., help="Pipeline UUID")
):
    """Stop a running pipeline."""
    bb = _get_bitbucket()

    if bb.cancel_pipeline(pipeline_uuid):
        console.print(f"[green]Stopped pipeline {pipeline_uuid[:8]}[/green]")
    else:
        console.print("[red]Failed to stop pipeline.[/red]")
        raise typer.Exit(1)


@bitbucket_pipelines_app.command("logs")
def show_logs(
    pipeline_uuid: str = typer.Argument(..., help="Pipeline UUID"),
    step_uuid: str = typer.Argument(..., help="Step UUID"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show")
):
    """Show step logs."""
    bb = _get_bitbucket()

    console.print(f"\n[bold cyan]Logs for Step {step_uuid[:8]}[/bold cyan]\n")

    logs = bb.get_step_log(pipeline_uuid, step_uuid)
    if logs:
        lines = logs.strip().split("\n")
        if tail and len(lines) > tail:
            lines = lines[-tail:]
        for line in lines:
            console.print(line)
    else:
        console.print("[yellow]No logs available.[/yellow]")