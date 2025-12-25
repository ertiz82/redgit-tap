"""
Version plugin CLI commands.
"""

import subprocess
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from pathlib import Path

console = Console()

version_app = typer.Typer(
    name="version",
    help="Semantic versioning management",
    no_args_is_help=True
)


def get_plugin():
    """Get the version plugin instance."""
    import importlib.util
    from pathlib import Path

    # Load the __init__.py from the same directory
    init_path = Path(__file__).parent / "__init__.py"
    spec = importlib.util.spec_from_file_location("version_plugin", init_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.VersionPlugin(), module.VersionInfo


@version_app.command("show")
def show_cmd():
    """Show current version."""
    plugin, _ = get_plugin()

    current = plugin.get_current_version()
    if current:
        console.print(f"[bold cyan]Current version:[/bold cyan] {current}")

        # Show detected version files
        files = plugin.get_version_files()
        if files:
            console.print("\n[dim]Version files:[/dim]")
            for filepath, _ in files:
                console.print(f"  [dim]- {filepath}[/dim]")
    else:
        console.print("[yellow]No version found. Run 'rg version init' to set up versioning.[/yellow]")


@version_app.command("init")
def init_cmd(
    version: str = typer.Option(
        None, "--version", "-v",
        help="Initial version (default: 0.1.0)"
    ),
):
    """Initialize versioning for the project."""
    plugin, VersionInfo = get_plugin()

    # Check if already initialized
    current = plugin.get_current_version()
    if current:
        console.print(f"[yellow]Version already initialized: {current}[/yellow]")
        if not Confirm.ask("Overwrite?", default=False):
            return

    # Get initial version
    if not version:
        version = Prompt.ask("Initial version", default="0.1.0")

    try:
        ver = VersionInfo.parse(version)
    except ValueError:
        console.print(f"[red]Invalid version format: {version}[/red]")
        console.print("[dim]Use semantic versioning: MAJOR.MINOR.PATCH (e.g., 1.0.0)[/dim]")
        raise typer.Exit(1)

    # Save to config
    plugin.save_version_to_config(ver)
    console.print(f"[green]Version initialized: {ver}[/green]")

    # Show detected files
    files = plugin.get_version_files()
    if files:
        console.print("\n[dim]Detected version files:[/dim]")
        for filepath, _ in files:
            console.print(f"  [dim]- {filepath}[/dim]")


@version_app.command("set")
def set_cmd(
    version: str = typer.Argument(..., help="Version to set (e.g., 1.2.0)"),
    update_files: bool = typer.Option(
        True, "--update-files/--no-update-files",
        help="Update version in project files"
    ),
):
    """Set a specific version."""
    plugin, VersionInfo = get_plugin()

    try:
        new_ver = VersionInfo.parse(version)
    except ValueError:
        console.print(f"[red]Invalid version format: {version}[/red]")
        raise typer.Exit(1)

    old_ver = plugin.get_current_version()

    # Update files if requested
    if update_files and old_ver:
        updated = plugin.update_all_versions(old_ver, new_ver)
        if updated:
            console.print("[green]Updated files:[/green]")
            for f in updated:
                console.print(f"  [dim]- {f}[/dim]")

    # Save to config
    plugin.save_version_to_config(new_ver)
    console.print(f"[green]Version set: {new_ver}[/green]")


@version_app.command("release")
def release_cmd(
    level: str = typer.Argument(..., help="Bump level: patch, minor, or major"),
    tag: bool = typer.Option(
        True, "--tag/--no-tag",
        help="Create git tag for the release"
    ),
    push: bool = typer.Option(
        False, "--push", "-p",
        help="Push tag to remote after creating"
    ),
    changelog: bool = typer.Option(
        True, "--changelog/--no-changelog",
        help="Generate changelog (if changelog plugin is enabled)"
    ),
):
    """Release a new version by bumping the specified level."""
    plugin, VersionInfo = get_plugin()

    if level not in ["patch", "minor", "major"]:
        console.print(f"[red]Invalid level: {level}[/red]")
        console.print("[dim]Use: patch, minor, or major[/dim]")
        raise typer.Exit(1)

    # Get current version
    current = plugin.get_current_version()
    if not current:
        console.print("[yellow]No version found. Run 'rg version init' first.[/yellow]")
        raise typer.Exit(1)

    # Bump version
    new_version = current.bump(level)

    console.print(f"[cyan]Bumping version: {current} -> {new_version}[/cyan]")

    # Update all files
    updated = plugin.update_all_versions(current, new_version)
    if updated:
        console.print("\n[green]Updated files:[/green]")
        for f in updated:
            console.print(f"  [dim]- {f}[/dim]")
    else:
        console.print("[yellow]No version files were updated.[/yellow]")

    # Save to config
    plugin.save_version_to_config(new_version)

    # Generate changelog if enabled
    if changelog and plugin.is_changelog_enabled():
        console.print("\n[cyan]Generating changelog...[/cyan]")
        try:
            # Get previous tag
            tag_prefix = plugin.get_tag_prefix()
            from_tag = f"{tag_prefix}{current}"

            # Import changelog plugin commands
            changelog_commands_path = Path(__file__).parent.parent / "changelog" / "commands.py"
            if changelog_commands_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("changelog_commands", changelog_commands_path)
                changelog_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(changelog_module)

                # Call generate with the from_tag
                changelog_module.generate_cmd(
                    version=str(new_version),
                    from_ref=from_tag,
                    to_ref="HEAD",
                    update_main=True
                )
        except Exception as e:
            console.print(f"[yellow]Changelog generation skipped: {e}[/yellow]")

    # Create git tag
    if tag:
        tag_name = f"{plugin.get_tag_prefix()}{new_version}"
        console.print(f"\n[cyan]Creating tag: {tag_name}[/cyan]")
        try:
            subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", f"Release {new_version}"],
                check=True,
                capture_output=True
            )
            console.print(f"[green]Created tag: {tag_name}[/green]")

            if push:
                console.print(f"[cyan]Pushing tag to remote...[/cyan]")
                subprocess.run(
                    ["git", "push", "origin", tag_name],
                    check=True,
                    capture_output=True
                )
                console.print(f"[green]Pushed tag: {tag_name}[/green]")

        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]Failed to create/push tag: {e.stderr.decode() if e.stderr else str(e)}[/yellow]")

    # Summary
    console.print(Panel(
        f"[bold green]Released version {new_version}[/bold green]",
        border_style="green"
    ))


@version_app.command("list")
def list_cmd():
    """List version tags from git history."""
    plugin, _ = get_plugin()
    tag_prefix = plugin.get_tag_prefix()

    try:
        result = subprocess.run(
            ["git", "tag", "-l", f"{tag_prefix}*", "--sort=-version:refname"],
            capture_output=True,
            text=True,
            check=True
        )

        tags = result.stdout.strip().split("\n")
        tags = [t for t in tags if t]

        if not tags:
            console.print("[yellow]No version tags found.[/yellow]")
            return

        table = Table(title="Version History", show_header=True)
        table.add_column("Version", style="cyan")
        table.add_column("Tag", style="dim")

        for tag in tags[:20]:  # Limit to 20
            version = tag.lstrip(tag_prefix)
            table.add_row(version, tag)

        if len(tags) > 20:
            table.add_row("...", f"and {len(tags) - 20} more")

        console.print(table)

    except subprocess.CalledProcessError:
        console.print("[red]Failed to list git tags.[/red]")


# Shortcuts for direct release commands
def release_shortcut():
    """Shortcut for 'rg release' -> 'rg version release'"""
    release_cmd(level="patch", tag=True, push=False, changelog=True)