"""
CircleCI CLI commands for RedGit.

Commands:
- rg circleci status    : Show status overview
- rg circleci pipelines : List pipelines
- rg circleci trigger   : Trigger a pipeline
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
circleci_app = typer.Typer(help="CircleCI management")


def _get_circleci():
    """Get configured CircleCI integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    circleci = get_cicd(config, "circleci")

    if not circleci:
        console.print("[red]CircleCI integration not configured.[/red]")
        console.print("[dim]Run 'rg install circleci' to set up[/dim]")
        raise typer.Exit(1)

    return circleci


def _status_icon(status: str) -> str:
    """Get icon for status."""
    icons = {
        "success": "[green]✓[/green]",
        "failed": "[red]✗[/red]",
        "running": "[yellow]●[/yellow]",
        "pending": "[blue]○[/blue]",
        "cancelled": "[dim]⊘[/dim]",
        "on_hold": "[cyan]◐[/cyan]"
    }
    return icons.get(status, "?")


@circleci_app.command("status")
def status_cmd():
    """Show CircleCI status overview."""
    circleci = _get_circleci()

    console.print("\n[bold cyan]CircleCI Status[/bold cyan]\n")
    console.print(f"   Project: {circleci.project_slug}")

    # Get recent pipelines
    pipelines = circleci.list_pipelines(limit=5)

    if not pipelines:
        console.print("\n   [yellow]No recent pipelines[/yellow]")
        return

    console.print("\n   [bold]Recent Pipelines:[/bold]")
    for p in pipelines:
        icon = _status_icon(p.status)
        branch = f" ({p.branch})" if p.branch else ""
        console.print(f"   {icon} {p.id[:8]}{branch} - {p.status}")


@circleci_app.command("pipelines")
def list_pipelines(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Filter by branch"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of pipelines to show")
):
    """List pipelines."""
    circleci = _get_circleci()

    title = "Pipelines"
    if branch:
        title += f" ({branch})"

    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    pipelines = circleci.list_project_pipelines(limit=limit)

    # Filter by branch if specified
    if branch:
        pipelines = [p for p in pipelines if p.get("branch") == branch]

    if not pipelines:
        console.print("[yellow]No pipelines found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Number", style="dim", width=8)
    table.add_column("Status", width=10)
    table.add_column("Branch")
    table.add_column("Commit", style="dim", width=10)
    table.add_column("Trigger", style="dim")

    for p in pipelines:
        table.add_row(
            f"#{p['number']}",
            _status_icon(circleci._map_status(p["state"])),
            p["branch"] or "-",
            p["commit"] or "-",
            p["trigger"] or "-"
        )

    console.print(table)


@circleci_app.command("pipeline")
def show_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID")
):
    """Show pipeline details."""
    circleci = _get_circleci()

    console.print(f"\n[bold cyan]Pipeline {pipeline_id[:8]}[/bold cyan]\n")

    pipeline = circleci.get_pipeline_status(pipeline_id)
    if not pipeline:
        console.print("[red]Pipeline not found.[/red]")
        raise typer.Exit(1)

    console.print(f"   Status: {_status_icon(pipeline.status)} {pipeline.status}")
    console.print(f"   Branch: {pipeline.branch or '-'}")
    console.print(f"   Commit: {pipeline.commit_sha[:7] if pipeline.commit_sha else '-'}")
    console.print(f"   Trigger: {pipeline.trigger or '-'}")
    console.print(f"   Started: {pipeline.started_at or '-'}")

    # Show workflows
    console.print("\n   [bold]Workflows:[/bold]")
    workflows = circleci.get_pipeline_workflows(pipeline_id)
    for wf in workflows:
        icon = _status_icon(wf.status)
        console.print(f"   {icon} {wf.name} ({wf.id[:8]})")


@circleci_app.command("workflows")
def list_workflows(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID")
):
    """List workflows for a pipeline."""
    circleci = _get_circleci()

    console.print(f"\n[bold cyan]Workflows for Pipeline {pipeline_id[:8]}[/bold cyan]\n")

    workflows = circleci.get_pipeline_workflows(pipeline_id)
    if not workflows:
        console.print("[yellow]No workflows found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Status", width=10)
    table.add_column("Name")
    table.add_column("Started", style="dim")

    for wf in workflows:
        table.add_row(
            wf.id[:12],
            _status_icon(wf.status),
            wf.name,
            wf.started_at[:16] if wf.started_at else "-"
        )

    console.print(table)


@circleci_app.command("jobs")
def show_jobs(
    workflow_id: str = typer.Argument(..., help="Workflow ID")
):
    """Show jobs for a workflow."""
    circleci = _get_circleci()

    console.print(f"\n[bold cyan]Jobs for Workflow {workflow_id[:8]}[/bold cyan]\n")

    jobs = circleci.get_pipeline_jobs(workflow_id)
    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Status", width=8)
    table.add_column("Job")
    table.add_column("Started", style="dim")

    for job in jobs:
        table.add_row(
            _status_icon(job.status),
            job.name,
            job.started_at[:16] if job.started_at else "-"
        )

    console.print(table)


@circleci_app.command("trigger")
def trigger_pipeline(
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to run on"),
    param: Optional[List[str]] = typer.Option(None, "--param", "-p", help="Parameter KEY=VALUE")
):
    """Trigger a new pipeline."""
    circleci = _get_circleci()

    console.print("\n[bold cyan]Triggering Pipeline[/bold cyan]\n")

    # Parse parameters
    params = {}
    if param:
        for p in param:
            if "=" in p:
                key, value = p.split("=", 1)
                # Try to convert to appropriate type
                if value.lower() == "true":
                    params[key] = True
                elif value.lower() == "false":
                    params[key] = False
                elif value.isdigit():
                    params[key] = int(value)
                else:
                    params[key] = value

    if branch:
        console.print(f"   Branch: {branch}")
    if params:
        console.print(f"   Parameters: {params}")

    pipeline = circleci.trigger_pipeline(branch=branch, inputs=params or None)

    if pipeline:
        console.print(f"\n[green]Pipeline triggered![/green]")
        console.print(f"   ID: {pipeline.id[:8]}")
    else:
        console.print("[red]Failed to trigger pipeline.[/red]")
        raise typer.Exit(1)


@circleci_app.command("rerun")
def rerun_workflow(
    workflow_id: str = typer.Argument(..., help="Workflow ID"),
    from_failed: bool = typer.Option(False, "--from-failed", "-f", help="Rerun from failed jobs only")
):
    """Rerun a workflow."""
    circleci = _get_circleci()

    action = "from failed" if from_failed else "entire workflow"
    console.print(f"\n[bold cyan]Rerunning {action}[/bold cyan]\n")

    new_workflow_id = circleci.rerun_workflow(workflow_id, from_failed=from_failed)

    if new_workflow_id:
        console.print("[green]Workflow rerun started![/green]")
        console.print(f"   New workflow ID: {new_workflow_id[:8]}")
    else:
        console.print("[red]Failed to rerun workflow.[/red]")
        raise typer.Exit(1)


@circleci_app.command("cancel")
def cancel_workflow(
    workflow_id: str = typer.Argument(..., help="Workflow ID")
):
    """Cancel a running workflow."""
    circleci = _get_circleci()

    if circleci.cancel_workflow(workflow_id):
        console.print(f"[green]Cancelled workflow {workflow_id[:8]}[/green]")
    else:
        console.print("[red]Failed to cancel workflow.[/red]")
        raise typer.Exit(1)


@circleci_app.command("artifacts")
def list_artifacts(
    job_number: str = typer.Argument(..., help="Job number")
):
    """List artifacts for a job."""
    circleci = _get_circleci()

    console.print(f"\n[bold cyan]Artifacts for Job #{job_number}[/bold cyan]\n")

    artifacts = circleci.get_job_artifacts(job_number)
    if not artifacts:
        console.print("[yellow]No artifacts found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Path")
    table.add_column("Node", style="dim", width=6)

    for a in artifacts:
        table.add_row(
            a["path"],
            str(a.get("node_index", "-"))
        )

    console.print(table)