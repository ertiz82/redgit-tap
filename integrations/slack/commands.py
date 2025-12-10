"""
CLI commands for Slack integration.

Usage: rg slack <command>
"""

import typer

slack_app = typer.Typer(help="Slack integration commands")


@slack_app.command("status")
def status_cmd():
    """Show Slack integration status."""
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import load_integration_by_name

    config = ConfigManager().load()
    integration_config = config.get("integrations", {}).get("slack", {})

    if not integration_config.get("enabled"):
        typer.secho("❌ Slack integration is not enabled.", fg=typer.colors.RED)
        typer.echo("   Run: rg integration install slack")
        raise typer.Exit(1)

    integration = load_integration_by_name("slack", integration_config)

    if not integration or not integration.enabled:
        typer.secho("⚠️  Slack is enabled but webhook URL is missing.", fg=typer.colors.YELLOW)
        typer.echo("   Set SLACK_WEBHOOK_URL environment variable or configure in .redgit/config.yaml")
        raise typer.Exit(1)

    typer.secho("✅ Slack integration is active", fg=typer.colors.GREEN)
    typer.echo(f"   Channel: {integration.channel or '(default)'}")
    typer.echo(f"   Username: {integration.username}")
    typer.echo(f"   Notify on: {', '.join(integration.notify_on)}")

    # Validate webhook
    if integration.validate_connection():
        typer.echo("   Webhook: Valid")
    else:
        typer.secho("   Webhook: Invalid format", fg=typer.colors.RED)


@slack_app.command("test")
def test_cmd(
    message: str = typer.Option("Hello from RedGit! 🚀", "--message", "-m", help="Test message"),
    channel: str = typer.Option(None, "--channel", "-c", help="Channel override")
):
    """Send a test message to Slack."""
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import load_integration_by_name

    config = ConfigManager().load()
    integration_config = config.get("integrations", {}).get("slack", {})
    integration = load_integration_by_name("slack", integration_config)

    if not integration or not integration.enabled:
        typer.secho("❌ Slack integration is not configured.", fg=typer.colors.RED)
        typer.echo("   Run: rg integration install slack")
        raise typer.Exit(1)

    typer.echo(f"Sending test message to Slack...")

    success = integration.send_custom_message(message, channel=channel)

    if success:
        typer.secho("✅ Message sent successfully!", fg=typer.colors.GREEN)
    else:
        typer.secho("❌ Failed to send message.", fg=typer.colors.RED)
        typer.echo("   Check your webhook URL and network connection.")
        raise typer.Exit(1)


@slack_app.command("send")
def send_cmd(
    message: str = typer.Argument(..., help="Message to send"),
    channel: str = typer.Option(None, "--channel", "-c", help="Channel override"),
    mention: str = typer.Option(None, "--mention", help="Mention (@here, @channel, or user)")
):
    """Send a custom message to Slack."""
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import load_integration_by_name

    config = ConfigManager().load()
    integration_config = config.get("integrations", {}).get("slack", {})
    integration = load_integration_by_name("slack", integration_config)

    if not integration or not integration.enabled:
        typer.secho("❌ Slack integration is not configured.", fg=typer.colors.RED)
        raise typer.Exit(1)

    success = integration.send_custom_message(message, channel=channel, mention=mention)

    if success:
        typer.secho("✅ Sent!", fg=typer.colors.GREEN)
    else:
        typer.secho("❌ Failed to send.", fg=typer.colors.RED)
        raise typer.Exit(1)


@slack_app.command("notify")
def notify_cmd(
    event: str = typer.Argument(..., help="Event type: commit, branch, pr"),
    branch: str = typer.Option(None, "--branch", "-b", help="Branch name"),
    message: str = typer.Option(None, "--message", "-m", help="Commit message"),
    title: str = typer.Option(None, "--title", "-t", help="PR title"),
    url: str = typer.Option(None, "--url", "-u", help="PR URL")
):
    """Manually trigger a notification."""
    from redgit.core.config import ConfigManager
    from redgit.integrations.registry import load_integration_by_name

    config = ConfigManager().load()
    integration_config = config.get("integrations", {}).get("slack", {})
    integration = load_integration_by_name("slack", integration_config)

    if not integration or not integration.enabled:
        typer.secho("❌ Slack integration is not configured.", fg=typer.colors.RED)
        raise typer.Exit(1)

    if event == "commit":
        integration.on_commit({
            "branch": branch or "main",
            "message": message or "Manual notification",
            "files": [],
            "author": "CLI"
        })
        typer.secho("✅ Commit notification sent!", fg=typer.colors.GREEN)

    elif event == "branch":
        integration.on_branch_create(branch or "feature/test")
        typer.secho("✅ Branch notification sent!", fg=typer.colors.GREEN)

    elif event == "pr":
        integration.on_pr_create({
            "title": title or "Test PR",
            "url": url or "https://github.com",
            "head": branch or "feature/test",
            "base": "main"
        })
        typer.secho("✅ PR notification sent!", fg=typer.colors.GREEN)

    else:
        typer.secho(f"❌ Unknown event type: {event}", fg=typer.colors.RED)
        typer.echo("   Available: commit, branch, pr")
        raise typer.Exit(1)