"""
GitHub Actions CLI commands for RedGit.

Commands:
- rg github-actions status    : Show status overview
- rg github-actions workflows : List workflows
- rg github-actions runs      : List workflow runs
- rg github-actions trigger   : Trigger a workflow
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
github_actions_app = typer.Typer(help="GitHub Actions CI/CD management")


def _get_github_actions():
    """Get configured GitHub Actions integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    gha = get_cicd(config, "github-actions")

    if not gha:
        console.print("[red]GitHub Actions integration not configured.[/red]")
        console.print("[dim]Run 'rg install github-actions' to set up[/dim]")
        raise typer.Exit(1)

    return gha


def _status_color(status: str) -> str:
    """Get color for status."""
    colors = {
        "success": "green",
        "failed": "red",
        "running": "yellow",
        "pending": "blue",
        "cancelled": "dim"
    }
    return colors.get(status, "white")


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


@github_actions_app.command("status")
def status_cmd():
    """Show GitHub Actions status overview."""
    gha = _get_github_actions()

    console.print("\n[bold cyan]GitHub Actions Status[/bold cyan]\n")
    console.print(f"   Repository: {gha.owner}/{gha.repo}")

    # Get recent runs
    runs = gha.list_pipelines(limit=5)

    if not runs:
        console.print("\n   [yellow]No recent workflow runs[/yellow]")
        return

    console.print("\n   [bold]Recent Runs:[/bold]")
    for run in runs:
        icon = _status_icon(run.status)
        console.print(f"   {icon} {run.name} ({run.branch}) - {run.status}")


@github_actions_app.command("workflows")
def list_workflows():
    """List repository workflows."""
    gha = _get_github_actions()

    console.print("\n[bold cyan]Workflows[/bold cyan]\n")

    workflows = gha.list_workflows()
    if not workflows:
        console.print("[yellow]No workflows found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Name")
    table.add_column("File", style="dim")
    table.add_column("State")

    for w in workflows:
        state_color = "green" if w["state"] == "active" else "dim"
        table.add_row(
            w["name"],
            w["path"].replace(".github/workflows/", ""),
            f"[{state_color}]{w['state']}[/{state_color}]"
        )

    console.print(table)


@github_actions_app.command("runs")
def list_runs(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Filter by branch"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of runs to show")
):
    """List workflow runs."""
    gha = _get_github_actions()

    title = "Workflow Runs"
    if branch:
        title += f" ({branch})"
    if status:
        title += f" [{status}]"

    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    runs = gha.list_pipelines(branch=branch, status=status, limit=limit)
    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Status", width=8)
    table.add_column("Workflow")
    table.add_column("Branch")
    table.add_column("Trigger", style="dim")

    for run in runs:
        table.add_row(
            run.id[:10],
            _status_icon(run.status),
            run.name[:30],
            run.branch or "-",
            run.trigger or "-"
        )

    console.print(table)


@github_actions_app.command("run")
def show_run(
    run_id: str = typer.Argument(..., help="Run ID")
):
    """Show workflow run details."""
    gha = _get_github_actions()

    console.print(f"\n[bold cyan]Run {run_id}[/bold cyan]\n")

    run = gha.get_pipeline_status(run_id)
    if not run:
        console.print("[red]Run not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Workflow: {run.name}")
    console.print(f"   Status: {_status_icon(run.status)} {run.status}")
    console.print(f"   Branch: {run.branch}")
    console.print(f"   Commit: {run.commit_sha[:7] if run.commit_sha else '-'}")
    console.print(f"   Trigger: {run.trigger}")
    console.print(f"   Started: {run.started_at or '-'}")
    if run.url:
        console.print(f"\n   URL: {run.url}")


@github_actions_app.command("jobs")
def show_jobs(
    run_id: str = typer.Argument(..., help="Run ID")
):
    """Show jobs for a workflow run."""
    gha = _get_github_actions()

    console.print(f"\n[bold cyan]Jobs for Run {run_id}[/bold cyan]\n")

    jobs = gha.get_pipeline_jobs(run_id)
    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Status", width=8)
    table.add_column("Job")
    table.add_column("Duration", style="dim")

    for job in jobs:
        duration = "-"
        if job.started_at and job.finished_at:
            # Format duration if available
            duration = "..."

        table.add_row(
            _status_icon(job.status),
            job.name,
            duration
        )

    console.print(table)


@github_actions_app.command("trigger")
def trigger_workflow(
    workflow: str = typer.Argument(..., help="Workflow file (e.g., ci.yml)"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to run on"),
    inputs: Optional[List[str]] = typer.Option(None, "--input", "-i", help="Input key=value")
):
    """Trigger a workflow run."""
    gha = _get_github_actions()

    console.print(f"\n[bold cyan]Triggering {workflow}[/bold cyan]\n")

    # Parse inputs
    input_dict = {}
    if inputs:
        for inp in inputs:
            if "=" in inp:
                key, value = inp.split("=", 1)
                input_dict[key] = value

    if branch:
        console.print(f"   Branch: {branch}")
    if input_dict:
        console.print(f"   Inputs: {input_dict}")

    run = gha.trigger_pipeline(branch=branch, workflow=workflow, inputs=input_dict or None)

    if run:
        console.print(f"\n[green]Workflow triggered![/green]")
        console.print(f"   Run ID: {run.id}")
        if run.url:
            console.print(f"   URL: {run.url}")
    else:
        console.print("[yellow]Workflow dispatch sent.[/yellow]")
        console.print("[dim]Check GitHub for the new run.[/dim]")


@github_actions_app.command("rerun")
def rerun_workflow(
    run_id: str = typer.Argument(..., help="Run ID"),
    failed_only: bool = typer.Option(False, "--failed-only", "-f", help="Re-run only failed jobs")
):
    """Re-run a workflow."""
    gha = _get_github_actions()

    console.print(f"\n[bold cyan]Re-running {run_id}[/bold cyan]\n")

    if failed_only:
        success = gha.retry_failed_jobs(run_id)
        if success:
            console.print("[green]Failed jobs re-run started![/green]")
        else:
            console.print("[red]Failed to re-run.[/red]")
            raise typer.Exit(1)
    else:
        run = gha.retry_pipeline(run_id)
        if run:
            console.print("[green]Workflow re-run started![/green]")
        else:
            console.print("[red]Failed to re-run.[/red]")
            raise typer.Exit(1)


@github_actions_app.command("cancel")
def cancel_run(
    run_id: str = typer.Argument(..., help="Run ID")
):
    """Cancel a running workflow."""
    gha = _get_github_actions()

    if gha.cancel_pipeline(run_id):
        console.print(f"[green]Cancelled run {run_id}[/green]")
    else:
        console.print("[red]Failed to cancel run.[/red]")
        raise typer.Exit(1)