"""
GitLab CI CLI commands for RedGit.

Commands:
- rg gitlab-ci status    : Show status overview
- rg gitlab-ci pipelines : List pipelines
- rg gitlab-ci trigger   : Trigger a pipeline
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
gitlab_ci_app = typer.Typer(help="GitLab CI/CD management")


def _get_gitlab_ci():
    """Get configured GitLab CI integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    gitlab = get_cicd(config, "gitlab-ci")

    if not gitlab:
        console.print("[red]GitLab CI integration not configured.[/red]")
        console.print("[dim]Run 'rg install gitlab-ci' to set up[/dim]")
        raise typer.Exit(1)

    return gitlab


def _status_icon(status: str) -> str:
    """Get icon for status."""
    icons = {
        "success": "[green]✓[/green]",
        "failed": "[red]✗[/red]",
        "running": "[yellow]●[/yellow]",
        "pending": "[blue]○[/blue]",
        "cancelled": "[dim]⊘[/dim]",
        "skipped": "[dim]⊖[/dim]",
        "manual": "[cyan]▶[/cyan]"
    }
    return icons.get(status, "?")


@gitlab_ci_app.command("status")
def status_cmd():
    """Show GitLab CI status overview."""
    gitlab = _get_gitlab_ci()

    console.print("\n[bold cyan]GitLab CI Status[/bold cyan]\n")
    console.print(f"   Project: {gitlab.project_id.replace('%2F', '/')}")

    # Get recent pipelines
    pipelines = gitlab.list_pipelines(limit=5)

    if not pipelines:
        console.print("\n   [yellow]No recent pipelines[/yellow]")
        return

    console.print("\n   [bold]Recent Pipelines:[/bold]")
    for p in pipelines:
        icon = _status_icon(p.status)
        console.print(f"   {icon} #{p.id} ({p.branch}) - {p.status}")


@gitlab_ci_app.command("pipelines")
def list_pipelines(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Filter by branch"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of pipelines to show")
):
    """List pipelines."""
    gitlab = _get_gitlab_ci()

    title = "Pipelines"
    if branch:
        title += f" ({branch})"
    if status:
        title += f" [{status}]"

    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    pipelines = gitlab.list_pipelines(branch=branch, status=status, limit=limit)
    if not pipelines:
        console.print("[yellow]No pipelines found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Status", width=8)
    table.add_column("Branch")
    table.add_column("Trigger", style="dim")
    table.add_column("Duration", style="dim")

    for p in pipelines:
        duration = f"{p.duration}s" if p.duration else "-"
        table.add_row(
            f"#{p.id}",
            _status_icon(p.status),
            p.branch or "-",
            p.trigger or "-",
            duration
        )

    console.print(table)


@gitlab_ci_app.command("pipeline")
def show_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID")
):
    """Show pipeline details."""
    gitlab = _get_gitlab_ci()

    console.print(f"\n[bold cyan]Pipeline #{pipeline_id}[/bold cyan]\n")

    pipeline = gitlab.get_pipeline_status(pipeline_id)
    if not pipeline:
        console.print("[red]Pipeline not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Status: {_status_icon(pipeline.status)} {pipeline.status}")
    console.print(f"   Branch: {pipeline.branch}")
    console.print(f"   Commit: {pipeline.commit_sha[:7] if pipeline.commit_sha else '-'}")
    console.print(f"   Trigger: {pipeline.trigger}")
    console.print(f"   Duration: {pipeline.duration}s" if pipeline.duration else "   Duration: -")
    if pipeline.url:
        console.print(f"\n   URL: {pipeline.url}")


@gitlab_ci_app.command("jobs")
def show_jobs(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID")
):
    """Show jobs for a pipeline."""
    gitlab = _get_gitlab_ci()

    console.print(f"\n[bold cyan]Jobs for Pipeline #{pipeline_id}[/bold cyan]\n")

    jobs = gitlab.get_pipeline_jobs(pipeline_id)
    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Status", width=8)
    table.add_column("Stage")
    table.add_column("Job")
    table.add_column("Duration", style="dim")

    for job in jobs:
        duration = f"{job.duration}s" if job.duration else "-"
        table.add_row(
            str(job.id),
            _status_icon(job.status),
            job.stage or "-",
            job.name,
            duration
        )

    console.print(table)


@gitlab_ci_app.command("trigger")
def trigger_pipeline(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to run on"),
    var: Optional[List[str]] = typer.Option(None, "--var", "-v", help="Variable KEY=VALUE")
):
    """Trigger a new pipeline."""
    gitlab = _get_gitlab_ci()

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
    if variables:
        console.print(f"   Variables: {variables}")

    pipeline = gitlab.trigger_pipeline(branch=branch, inputs=variables or None)

    if pipeline:
        console.print(f"\n[green]Pipeline triggered![/green]")
        console.print(f"   ID: #{pipeline.id}")
        if pipeline.url:
            console.print(f"   URL: {pipeline.url}")
    else:
        console.print("[red]Failed to trigger pipeline.[/red]")
        raise typer.Exit(1)


@gitlab_ci_app.command("retry")
def retry_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID")
):
    """Retry a failed pipeline."""
    gitlab = _get_gitlab_ci()

    console.print(f"\n[bold cyan]Retrying Pipeline #{pipeline_id}[/bold cyan]\n")

    pipeline = gitlab.retry_pipeline(pipeline_id)
    if pipeline:
        console.print("[green]Pipeline retry started![/green]")
        if pipeline.url:
            console.print(f"   URL: {pipeline.url}")
    else:
        console.print("[red]Failed to retry pipeline.[/red]")
        raise typer.Exit(1)


@gitlab_ci_app.command("retry-job")
def retry_job(
    job_id: str = typer.Argument(..., help="Job ID")
):
    """Retry a specific job."""
    gitlab = _get_gitlab_ci()

    if gitlab.retry_job(job_id):
        console.print(f"[green]Job {job_id} retry started![/green]")
    else:
        console.print("[red]Failed to retry job.[/red]")
        raise typer.Exit(1)


@gitlab_ci_app.command("play")
def play_job(
    job_id: str = typer.Argument(..., help="Job ID")
):
    """Play a manual job."""
    gitlab = _get_gitlab_ci()

    if gitlab.play_job(job_id):
        console.print(f"[green]Job {job_id} started![/green]")
    else:
        console.print("[red]Failed to play job.[/red]")
        raise typer.Exit(1)


@gitlab_ci_app.command("cancel")
def cancel_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID")
):
    """Cancel a running pipeline."""
    gitlab = _get_gitlab_ci()

    if gitlab.cancel_pipeline(pipeline_id):
        console.print(f"[green]Cancelled pipeline #{pipeline_id}[/green]")
    else:
        console.print("[red]Failed to cancel pipeline.[/red]")
        raise typer.Exit(1)


@gitlab_ci_app.command("logs")
def show_logs(
    job_id: str = typer.Argument(..., help="Job ID"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show")
):
    """Show job logs."""
    gitlab = _get_gitlab_ci()

    console.print(f"\n[bold cyan]Logs for Job {job_id}[/bold cyan]\n")

    logs = gitlab.get_job_logs(job_id)
    if logs:
        lines = logs.strip().split("\n")
        if tail and len(lines) > tail:
            lines = lines[-tail:]
        for line in lines:
            console.print(line)
    else:
        console.print("[yellow]No logs available.[/yellow]")


@gitlab_ci_app.command("schedules")
def list_schedules():
    """List pipeline schedules."""
    gitlab = _get_gitlab_ci()

    console.print("\n[bold cyan]Pipeline Schedules[/bold cyan]\n")

    schedules = gitlab.list_pipeline_schedules()
    if not schedules:
        console.print("[yellow]No schedules found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Description")
    table.add_column("Branch")
    table.add_column("Cron")
    table.add_column("Active")
    table.add_column("Next Run", style="dim")

    for s in schedules:
        active = "[green]Yes[/green]" if s["active"] else "[dim]No[/dim]"
        table.add_row(
            str(s["id"]),
            s["description"][:30] if s["description"] else "-",
            s["ref"] or "-",
            s["cron"] or "-",
            active,
            s["next_run_at"][:16] if s["next_run_at"] else "-"
        )

    console.print(table)