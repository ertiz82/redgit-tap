"""
Changelog plugin CLI commands.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path

console = Console()

changelog_app = typer.Typer(
    name="changelog",
    help="Changelog generation commands",
    no_args_is_help=True
)


def get_plugin():
    """Get the changelog plugin instance."""
    import importlib.util
    from pathlib import Path

    init_path = Path(__file__).parent / "__init__.py"
    spec = importlib.util.spec_from_file_location("changelog_plugin", init_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.ChangelogPlugin()


def get_language_from_config() -> str:
    """Get changelog language from config."""
    try:
        from redgit.core.config import ConfigManager
        config = ConfigManager().load()
        # Check daily.language or changelog.language
        lang = config.get("plugins", {}).get("changelog", {}).get("language")
        if not lang:
            lang = config.get("daily", {}).get("language", "en")
        return lang
    except Exception:
        return "en"


@changelog_app.command("generate")
def generate_cmd(
    version: str = typer.Option(
        None, "--version", "-v",
        help="Version to generate changelog for (uses version plugin if not specified)"
    ),
    from_ref: str = typer.Option(
        None, "--from", "-f",
        help="Starting ref (tag/commit). Default: latest tag. Use empty string for all commits."
    ),
    to_ref: str = typer.Option(
        "HEAD", "--to", "-t",
        help="Ending ref for changelog range"
    ),
    lang: str = typer.Option(
        None, "--lang", "-l",
        help="Language for AI summary (e.g., en, tr, de). Overrides config."
    ),
    update_main: bool = typer.Option(
        True, "--update-main/--no-update-main",
        help="Update main CHANGELOG.md file"
    ),
    no_ai: bool = typer.Option(
        False, "--no-ai",
        help="Skip AI summary generation"
    ),
):
    """Generate changelog for a version with AI-powered summary."""
    plugin = get_plugin()

    # Get version from version plugin if not specified
    if not version:
        try:
            from redgit.core.config import ConfigManager
            config = ConfigManager().load()
            version = config.get("plugins", {}).get("version", {}).get("current", "1.0.0")
        except Exception:
            version = "1.0.0"

    # Determine from_ref
    # Empty string means "all commits"
    if from_ref == "":
        from_ref = None
        from_ref_display = "all commits"
    elif from_ref is None:
        # Auto-detect: use latest tag
        from_ref = plugin.get_latest_tag()
        if from_ref:
            from_ref_display = from_ref
        else:
            from_ref_display = "all commits"
    else:
        from_ref_display = from_ref

    console.print(f"[cyan]Generating changelog for version {version}[/cyan]")
    console.print(f"[dim]Range: {from_ref_display} → {to_ref}[/dim]")

    # Fetch commits
    with console.status("Fetching commits..."):
        commits = plugin.get_commits_between(from_ref, to_ref)

    if not commits:
        console.print("[yellow]No commits found for changelog.[/yellow]")
        return

    original_count = len(commits)
    console.print(f"[dim]Found {original_count} commits[/dim]")

    # Deduplicate
    with console.status("Removing duplicates..."):
        commits = plugin.deduplicate_commits(commits)

    if len(commits) < original_count:
        console.print(f"[dim]After deduplication: {len(commits)} unique commits[/dim]")

    # Calculate author stats
    with console.status("Calculating contributor statistics..."):
        author_stats = plugin.calculate_author_stats(commits)

    # Generate LLM summary
    llm_summary = None
    if not no_ai:
        # Use command-line lang if provided, otherwise fall back to config
        language = lang if lang else get_language_from_config()
        console.print(f"[cyan]Generating AI summary ({language})...[/cyan]")
        with console.status("AI is analyzing commits..."):
            llm_summary = plugin.generate_llm_summary(
                commits,
                from_ref,
                version,
                language
            )

        if llm_summary:
            console.print("[green]AI summary generated[/green]")
        else:
            console.print("[yellow]AI summary skipped[/yellow]")

    # Generate markdown
    content = plugin.generate_markdown(
        version,
        commits,
        from_ref,
        llm_summary,
        author_stats
    )

    # Save version-specific file
    version_file = plugin.save_version_changelog(version, content)
    console.print(f"[green]Created {version_file}[/green]")

    # Update main CHANGELOG.md
    if update_main:
        main_file = plugin.update_main_changelog(version, content)
        console.print(f"[green]Updated {main_file}[/green]")

    # Show summary table
    grouped = plugin.group_commits_by_type(commits)
    table = Table(title="Changelog Summary", show_header=True)
    table.add_column("Type", style="cyan")
    table.add_column("Count", style="green", justify="right")

    for commit_type in plugin.TYPE_ORDER:
        if commit_type in grouped:
            type_commits = grouped[commit_type]
            display_name, emoji = plugin.TYPE_DISPLAY.get(commit_type, (commit_type, ""))
            table.add_row(f"{emoji} {display_name}", str(len(type_commits)))

    console.print(table)

    # Show contributor stats
    if author_stats:
        console.print("\n[bold]Contributors:[/bold]")
        for stat in author_stats[:5]:  # Top 5
            bar_length = int(stat.percentage / 5)
            bar = "█" * bar_length + "░" * (20 - bar_length)
            console.print(f"  {stat.name}: {stat.commits} commits ({stat.percentage}%) [dim]{bar}[/dim]")

        if len(author_stats) > 5:
            console.print(f"  [dim]... and {len(author_stats) - 5} more contributors[/dim]")


@changelog_app.command("show")
def show_cmd(
    version: str = typer.Option(
        None, "--version", "-v",
        help="Version to show (latest if not specified)"
    ),
):
    """Show changelog content."""
    plugin = get_plugin()
    output_dir = Path(plugin.config.get("output_dir", "changelogs"))

    if version:
        version_name = version if version.startswith("v") else f"v{version}"
        filepath = output_dir / f"{version_name}.md"
    else:
        if output_dir.exists():
            files = sorted(output_dir.glob("v*.md"), reverse=True)
            if files:
                filepath = files[0]
            else:
                console.print("[yellow]No changelog files found.[/yellow]")
                return
        else:
            console.print("[yellow]No changelogs directory found.[/yellow]")
            return

    if filepath.exists():
        content = filepath.read_text()
        console.print(Panel(content, title=f"[bold]{filepath.name}[/bold]", border_style="cyan"))
    else:
        console.print(f"[yellow]Changelog not found: {filepath}[/yellow]")


@changelog_app.command("list")
def list_cmd():
    """List all changelog versions."""
    plugin = get_plugin()
    output_dir = Path(plugin.config.get("output_dir", "changelogs"))

    if not output_dir.exists():
        console.print("[yellow]No changelogs directory found.[/yellow]")
        return

    files = sorted(output_dir.glob("v*.md"), reverse=True)
    if not files:
        console.print("[yellow]No changelog files found.[/yellow]")
        return

    table = Table(title="Changelogs", show_header=True)
    table.add_column("Version", style="cyan")
    table.add_column("File", style="dim")

    for f in files:
        version = f.stem
        table.add_row(version, str(f))

    console.print(table)