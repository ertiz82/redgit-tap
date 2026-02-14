"""
Sentry CLI commands - Error tracking and monitoring.

Commands:
- rg sentry list      : List recent errors
- rg sentry show      : Show error details
- rg sentry link      : Link commit to error
- rg sentry resolve   : Resolve an error
- rg sentry status    : Show project error statistics
- rg sentry releases  : List recent releases
"""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional

try:
    from redgit.core.common.config import ConfigManager
    from redgit.integrations.registry import get_error_tracking
    from redgit.core.common.gitops import GitOps
except ImportError:
    ConfigManager = None
    get_error_tracking = None
    GitOps = None

console = Console()
sentry_app = typer.Typer(help="Sentry error tracking and monitoring")


def _get_sentry():
    """Get configured Sentry integration."""
    if not ConfigManager:
        console.print("[red]RedGit not properly installed.[/red]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    sentry = get_error_tracking(config, "sentry")

    if not sentry:
        console.print("[red]Sentry integration not configured.[/red]")
        console.print("[dim]Run 'rg install sentry' to set up[/dim]")
        raise typer.Exit(1)

    return sentry


def _format_level(level: str) -> str:
    """Format error level with color."""
    colors = {
        "fatal": "red bold",
        "error": "red",
        "warning": "yellow",
        "info": "blue"
    }
    color = colors.get(level, "white")
    return f"[{color}]{level}[/{color}]"


def _format_count(count: int | str | None) -> str:
    """Format count with appropriate suffix."""
    if count is None:
        return "0"
    count = int(count)
    if count >= 1000000:
        return f"{count / 1000000:.1f}M"
    elif count >= 1000:
        return f"{count / 1000:.1f}K"
    return str(count)


@sentry_app.command("list")
def list_errors(
    status: str = typer.Option("unresolved", "--status", "-s", help="Filter: unresolved, resolved, ignored"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of errors to show"),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Filter by environment")
):
    """List recent errors from Sentry."""
    sentry = _get_sentry()

    console.print(f"\n[bold red]Sentry Errors[/bold red]")
    console.print(f"[dim]Organization: {sentry.organization} | Project: {sentry.project_slug}[/dim]\n")

    with console.status("Fetching errors..."):
        errors = sentry.get_recent_errors(
            limit=limit,
            status=status,
            environment=environment or sentry.default_environment
        )

    if not errors:
        if hasattr(sentry, '_last_error') and sentry._last_error:
            console.print(f"[red]{sentry._last_error}[/red]")
        else:
            console.print(f"[green]No {status} errors found.[/green]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan", width=12)
    table.add_column("Level", width=8)
    table.add_column("Title", width=40)
    table.add_column("Events", justify="right", width=8)
    table.add_column("Users", justify="right", width=6)
    table.add_column("Last Seen", style="dim", width=12)

    for error in errors:
        # Parse last_seen date
        last_seen = error.last_seen[:10] if error.last_seen else "-"

        table.add_row(
            error.short_id or error.id[:10],
            _format_level(error.level),
            error.title[:40] + ("..." if len(error.title) > 40 else ""),
            _format_count(error.count),
            _format_count(error.user_count),
            last_seen
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(errors)} {status} errors | Environment: {environment or sentry.default_environment}[/dim]")


@sentry_app.command("show")
def show_error(
    error_id: str = typer.Argument(..., help="Error ID or short ID (e.g., PROJ-123 or full ID)"),
    events: bool = typer.Option(False, "--events", "-e", help="Show recent events"),
    stacktrace: bool = typer.Option(False, "--stacktrace", "-st", help="Show full stacktrace")
):
    """Show detailed information about an error."""
    sentry = _get_sentry()

    with console.status("Fetching error details..."):
        error = sentry.get_error(error_id)

    if not error:
        console.print(f"[red]Error {error_id} not found.[/red]")
        raise typer.Exit(1)

    # Error header
    console.print(Panel(
        f"[bold]{error.title}[/bold]\n\n"
        f"[dim]ID: {error.short_id or error.id}[/dim]",
        title=f"{_format_level(error.level)} Error",
        border_style="red"
    ))

    # Details table
    details = Table(show_header=False, box=None)
    details.add_column("Field", style="dim")
    details.add_column("Value")

    details.add_row("Status", error.status)
    details.add_row("Platform", error.platform)
    details.add_row("Events", _format_count(error.count))
    details.add_row("Users Affected", _format_count(error.user_count))
    details.add_row("First Seen", error.first_seen[:19] if error.first_seen else "-")
    details.add_row("Last Seen", error.last_seen[:19] if error.last_seen else "-")
    details.add_row("Culprit", error.culprit or "-")

    if error.filename:
        location = f"{error.filename}"
        if error.lineno:
            location += f":{error.lineno}"
        if error.function:
            location += f" in {error.function}"
        details.add_row("Location", location)

    if error.url:
        details.add_row("Link", f"[link={error.url}]{error.url}[/link]")

    console.print(details)

    # Stacktrace
    if stacktrace and error.stacktrace:
        console.print("\n[bold cyan]Stacktrace[/bold cyan]")
        for i, frame in enumerate(reversed(error.stacktrace)):
            prefix = "[green]>[/green]" if frame.in_app else " "
            console.print(f"  {prefix} {frame.filename}:{frame.lineno} in {frame.function}")
            if frame.context_line:
                console.print(f"      [dim]{frame.context_line.strip()}[/dim]")

    # Affected files
    if error.affected_files:
        console.print(f"\n[bold cyan]Affected Files ({len(error.affected_files)})[/bold cyan]")
        for f in error.affected_files[:10]:
            console.print(f"  [dim]{f}[/dim]")
        if len(error.affected_files) > 10:
            console.print(f"  [dim]... and {len(error.affected_files) - 10} more[/dim]")

    # Recent events
    if events:
        console.print("\n[bold cyan]Recent Events[/bold cyan]")
        with console.status("Fetching events..."):
            error_events = sentry.get_error_events(error.id, limit=5)

        if error_events:
            for evt in error_events:
                timestamp = evt.timestamp[:19] if evt.timestamp else "-"
                env = f"[{evt.environment}]" if evt.environment else ""
                user = f"User: {evt.user_email or evt.user_id}" if (evt.user_email or evt.user_id) else ""
                console.print(f"  [dim]{timestamp}[/dim] {env} {user}")
        else:
            console.print("  [dim]No recent events found[/dim]")


@sentry_app.command("link")
def link_commit(
    error_id: str = typer.Argument(..., help="Error ID to link"),
    commit: Optional[str] = typer.Option(None, "--commit", "-c", help="Commit SHA (default: HEAD)")
):
    """Link a commit to an error."""
    sentry = _get_sentry()

    # Get commit SHA
    if not commit:
        try:
            gitops = GitOps()
            commit = gitops.get_current_commit_sha()
        except Exception:
            console.print("[red]Could not get current commit. Please specify --commit.[/red]")
            raise typer.Exit(1)

    console.print(f"Linking commit [cyan]{commit[:8]}[/cyan] to error [cyan]{error_id}[/cyan]...")

    success = sentry.link_commit_to_error(error_id, commit)

    if success:
        console.print(f"[green]Successfully linked commit to error.[/green]")
    else:
        console.print(f"[red]Failed to link commit to error.[/red]")
        raise typer.Exit(1)


@sentry_app.command("resolve")
def resolve_error(
    error_id: str = typer.Argument(..., help="Error ID to resolve"),
    status: str = typer.Option("resolved", "--status", "-s", help="New status: resolved, ignored, unresolved"),
    release: Optional[str] = typer.Option(None, "--release", "-r", help="Resolve in specific release")
):
    """Resolve or change status of an error."""
    sentry = _get_sentry()

    # Validate status
    valid_statuses = ["resolved", "ignored", "unresolved"]
    if status not in valid_statuses:
        console.print(f"[red]Invalid status. Use: {', '.join(valid_statuses)}[/red]")
        raise typer.Exit(1)

    console.print(f"Changing error [cyan]{error_id}[/cyan] to [yellow]{status}[/yellow]...")

    success = sentry.resolve_error(error_id, status, release)

    if success:
        console.print(f"[green]Successfully updated error status to {status}.[/green]")
        if release:
            console.print(f"[dim]Marked as resolved in release: {release}[/dim]")
    else:
        console.print(f"[red]Failed to update error status.[/red]")
        raise typer.Exit(1)


@sentry_app.command("status")
def show_status(
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Filter by environment")
):
    """Show error statistics for the project."""
    sentry = _get_sentry()

    console.print(f"\n[bold red]Sentry Status[/bold red]")
    console.print(f"[dim]Organization: {sentry.organization} | Project: {sentry.project_slug}[/dim]\n")

    with console.status("Fetching statistics..."):
        stats = sentry.get_error_stats(environment or sentry.default_environment)

    if not stats:
        console.print("[yellow]Could not fetch statistics.[/yellow]")
        return

    # Summary panel
    summary = Table(show_header=False, box=None)
    summary.add_column("Metric", style="dim")
    summary.add_column("Value", style="bold")

    summary.add_row("Environment", stats.get("environment", "-"))
    summary.add_row("Unresolved Errors", str(stats.get("total_errors", 0)))
    summary.add_row("Total Events", _format_count(stats.get("total_events", 0)))
    summary.add_row("Users Affected", _format_count(stats.get("total_users_affected", 0)))

    console.print(Panel(summary, title="Summary"))

    # By level breakdown
    by_level = stats.get("by_level", {})
    if by_level:
        console.print("\n[bold]By Level[/bold]")
        level_table = Table(show_header=True)
        level_table.add_column("Level")
        level_table.add_column("Count", justify="right")

        for level, count in sorted(by_level.items(), key=lambda x: x[1], reverse=True):
            level_table.add_row(_format_level(level), str(count))

        console.print(level_table)


@sentry_app.command("releases")
def list_releases(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of releases to show")
):
    """List recent releases."""
    sentry = _get_sentry()

    console.print(f"\n[bold cyan]Recent Releases[/bold cyan]\n")

    with console.status("Fetching releases..."):
        releases = sentry.get_releases(limit=limit)

    if not releases:
        console.print("[yellow]No releases found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Version", style="cyan")
    table.add_column("Created", style="dim")
    table.add_column("New Issues", justify="right")
    table.add_column("Status")

    for rel in releases:
        created = rel.get("dateCreated", "")[:10] if rel.get("dateCreated") else "-"
        new_groups = rel.get("newGroups", 0)
        status = "[green]Deployed[/green]" if rel.get("lastDeploy") else "[dim]Created[/dim]"

        table.add_row(
            rel.get("version", "-")[:30],
            created,
            str(new_groups),
            status
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(releases)} releases[/dim]")


# Export the app for registry
app = sentry_app
