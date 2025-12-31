"""
CLI commands for Microsoft Teams integration.

Commands:
    rg msteams login     - Authenticate with Device Code Flow
    rg msteams logout    - Clear stored tokens
    rg msteams status    - Show authentication status
    rg msteams list      - List accessible teams
    rg msteams channels  - List channels in a team
    rg msteams users     - List users for DM targeting
    rg msteams send      - Send a test message
"""

import sys
import importlib.util
from pathlib import Path
import typer
from typing import Optional

# Get the directory containing this file for sibling imports
_THIS_DIR = Path(__file__).parent

def _import_sibling(module_name: str):
    """Import a sibling module from the same directory."""
    module_path = _THIS_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

msteams_app = typer.Typer(help="Microsoft Teams integration commands")


def _get_config():
    """Get redgit config."""
    try:
        from redgit.core.common.config import ConfigManager
        return ConfigManager().load()
    except ImportError:
        import yaml
        from pathlib import Path
        config_path = Path(".redgit/config.yaml")
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        return {}


def _save_config(config: dict):
    """Save redgit config."""
    try:
        from redgit.core.common.config import ConfigManager
        ConfigManager().save(config)
    except ImportError:
        import yaml
        from pathlib import Path
        config_path = Path(".redgit/config.yaml")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)


def _get_msteams_config() -> dict:
    """Get msteams integration config."""
    config = _get_config()
    return config.get("integrations", {}).get("msteams", {})


def _save_tokens(access_token: str, refresh_token: str, expires_at: int):
    """Save tokens to config file."""
    config = _get_config()
    if "integrations" not in config:
        config["integrations"] = {}
    if "msteams" not in config["integrations"]:
        config["integrations"]["msteams"] = {}

    config["integrations"]["msteams"]["access_token"] = access_token
    config["integrations"]["msteams"]["refresh_token"] = refresh_token
    config["integrations"]["msteams"]["token_expires_at"] = expires_at

    _save_config(config)


def _get_integration():
    """Get configured Teams integration with Graph client."""
    msteams_config = _get_msteams_config()

    if not msteams_config.get("enabled"):
        return None

    tenant_id = msteams_config.get("tenant_id", "")
    client_id = msteams_config.get("client_id", "")
    access_token = msteams_config.get("access_token", "")
    refresh_token = msteams_config.get("refresh_token", "")
    token_expires_at = msteams_config.get("token_expires_at", 0)

    if not tenant_id or not client_id:
        return None

    if not access_token:
        return None

    graph_client_module = _import_sibling("graph_client")
    GraphClient = graph_client_module.GraphClient

    return GraphClient(
        tenant_id=tenant_id,
        client_id=client_id,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        on_token_refresh=_save_tokens,
    )


@msteams_app.command("login")
def login_cmd(
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't open browser automatically"
    ),
):
    """
    Authenticate with Microsoft Teams using Device Code Flow.

    This will:
    1. Display a code and URL
    2. Open your browser (unless --no-browser)
    3. Wait for you to sign in and authorize
    4. Store tokens in config for future use
    """
    msteams_config = _get_msteams_config()

    tenant_id = msteams_config.get("tenant_id")
    client_id = msteams_config.get("client_id")

    if not tenant_id or not client_id:
        typer.secho("MS Teams integration not configured.", fg=typer.colors.RED)
        typer.echo("Run: rg install msteams")
        raise typer.Exit(1)

    typer.echo("\nAuthenticating with Microsoft Teams...")
    typer.echo("=" * 50)

    auth_module = _import_sibling("auth")
    DeviceCodeAuth = auth_module.DeviceCodeAuth
    AuthenticationError = auth_module.AuthenticationError

    auth = DeviceCodeAuth(tenant_id, client_id)

    def on_code(code: str, url: str):
        typer.echo(f"\nTo sign in, open: {url}")
        typer.secho(f"\nEnter code: {code}", fg=typer.colors.CYAN, bold=True)
        typer.echo("\nWaiting for authentication...")

    try:
        token_info = auth.authenticate(
            open_browser=not no_browser, on_user_code=on_code
        )

        _save_tokens(
            token_info.access_token,
            token_info.refresh_token,
            token_info.expires_at,
        )

        typer.echo("")
        typer.secho("Successfully authenticated!", fg=typer.colors.GREEN)

        # Show user info
        client = _get_integration()
        if client:
            try:
                user = client.get_me()
                typer.echo(
                    f"Signed in as: {user.get('displayName')} ({user.get('mail')})"
                )
            except Exception:
                pass

    except AuthenticationError as e:
        typer.secho(f"\nAuthentication failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@msteams_app.command("logout")
def logout_cmd():
    """Clear stored authentication tokens."""
    config = _get_config()
    msteams_config = config.get("integrations", {}).get("msteams", {})

    if not msteams_config:
        typer.echo("MS Teams integration is not configured.")
        return

    # Clear tokens
    msteams_config.pop("access_token", None)
    msteams_config.pop("refresh_token", None)
    msteams_config.pop("token_expires_at", None)

    config["integrations"]["msteams"] = msteams_config
    _save_config(config)

    typer.secho("Logged out. Tokens cleared.", fg=typer.colors.GREEN)


@msteams_app.command("status")
def status_cmd():
    """Show authentication and connection status."""
    msteams_config = _get_msteams_config()
    config = _get_config()
    active = config.get("active", {}).get("notification")

    typer.echo("\nMicrosoft Teams Integration Status")
    typer.echo("=" * 40)

    if not msteams_config.get("enabled"):
        typer.secho("Status: Not installed", fg=typer.colors.YELLOW)
        typer.echo("Run: rg install msteams")
        return

    typer.echo("Enabled: Yes")
    typer.echo(f"Active: {'Yes' if active == 'msteams' else 'No'}")
    typer.echo(f"Tenant ID: {msteams_config.get('tenant_id', 'Not set')}")

    client_id = msteams_config.get("client_id", "")
    if client_id:
        typer.echo(f"Client ID: {client_id[:20]}...")
    else:
        typer.echo("Client ID: Not set")

    # Check authentication
    client = _get_integration()

    if client:
        try:
            user = client.get_me()
            typer.secho("Authentication: Valid", fg=typer.colors.GREEN)
            typer.echo(f"User: {user.get('displayName')} ({user.get('mail')})")
        except Exception as e:
            typer.secho(f"Authentication: Invalid ({e})", fg=typer.colors.RED)
            typer.echo("Run: rg msteams login")
    else:
        typer.secho("Authentication: Not authenticated", fg=typer.colors.YELLOW)
        typer.echo("Run: rg msteams login")

    # Show defaults
    if msteams_config.get("default_team_id"):
        typer.echo(f"Default Team: {msteams_config.get('default_team_id')}")
    if msteams_config.get("default_channel_id"):
        typer.echo(f"Default Channel: {msteams_config.get('default_channel_id')}")


@msteams_app.command("list")
def list_teams_cmd():
    """List all accessible Teams."""
    client = _get_integration()

    if not client:
        typer.secho("Not authenticated. Run: rg msteams login", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo("\nAccessible Teams:")
    typer.echo("-" * 40)

    try:
        teams = client.list_joined_teams()

        if not teams:
            typer.echo("No teams found.")
            return

        for team in teams:
            typer.echo(f"  {team['displayName']}")
            typer.secho(f"    ID: {team['id']}", fg=typer.colors.BRIGHT_BLACK)

    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@msteams_app.command("channels")
def list_channels_cmd(
    team_id: str = typer.Argument(..., help="Team ID (from 'rg msteams list')")
):
    """List channels in a team."""
    client = _get_integration()

    if not client:
        typer.secho("Not authenticated. Run: rg msteams login", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo("\nChannels:")
    typer.echo("-" * 40)

    try:
        channels = client.list_channels(team_id)

        if not channels:
            typer.echo("No channels found.")
            return

        for channel in channels:
            typer.echo(f"  {channel['displayName']}")
            typer.secho(f"    ID: {channel['id']}", fg=typer.colors.BRIGHT_BLACK)

    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@msteams_app.command("users")
def list_users_cmd(
    search: Optional[str] = typer.Option(
        None, "--search", "-s", help="Search by name or email"
    )
):
    """List users for DM targeting."""
    client = _get_integration()

    if not client:
        typer.secho("Not authenticated. Run: rg msteams login", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo("\nUsers:")
    typer.echo("-" * 40)

    try:
        users = client.list_users(search)

        if not users:
            typer.echo("No users found.")
            return

        for user in users[:20]:
            typer.echo(f"  {user.get('displayName')}")
            email = user.get("mail") or user.get("userPrincipalName")
            typer.secho(f"    Email: {email}", fg=typer.colors.BRIGHT_BLACK)

        if len(users) > 20:
            typer.echo(f"\n  ... and {len(users) - 20} more (use --search to filter)")

    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@msteams_app.command("send")
def send_cmd(
    message: str = typer.Argument(..., help="Message to send"),
    team: Optional[str] = typer.Option(None, "--team", "-t", help="Team ID"),
    channel: Optional[str] = typer.Option(None, "--channel", "-c", help="Channel ID"),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="User email for DM"),
):
    """Send a test message to a channel or user."""
    client = _get_integration()

    if not client:
        typer.secho("Not authenticated. Run: rg msteams login", fg=typer.colors.RED)
        raise typer.Exit(1)

    msteams_config = _get_msteams_config()

    try:
        if email:
            # Send DM
            typer.echo(f"Sending DM to {email}...")
            chat_id = client.get_or_create_chat(email)
            if not chat_id:
                typer.secho(f"User not found: {email}", fg=typer.colors.RED)
                raise typer.Exit(1)
            client.send_chat_message(chat_id, message)
            typer.secho("Message sent!", fg=typer.colors.GREEN)
        else:
            # Send to channel
            team_id = team or msteams_config.get("default_team_id")
            channel_id = channel or msteams_config.get("default_channel_id")

            if not team_id or not channel_id:
                typer.secho(
                    "Specify --team and --channel, or set defaults with 'rg msteams set-default'",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(1)

            typer.echo("Sending to channel...")
            client.send_channel_message(team_id, channel_id, message)
            typer.secho("Message sent!", fg=typer.colors.GREEN)

    except Exception as e:
        typer.secho(f"Failed to send message: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@msteams_app.command("set-default")
def set_default_cmd(
    team: Optional[str] = typer.Option(None, "--team", "-t", help="Default team ID"),
    channel: Optional[str] = typer.Option(
        None, "--channel", "-c", help="Default channel ID"
    ),
):
    """Set default team and channel for notifications."""
    if not team and not channel:
        typer.echo("Specify --team and/or --channel")
        raise typer.Exit(1)

    config = _get_config()

    if "integrations" not in config:
        config["integrations"] = {}
    if "msteams" not in config["integrations"]:
        config["integrations"]["msteams"] = {}

    if team:
        config["integrations"]["msteams"]["default_team_id"] = team
    if channel:
        config["integrations"]["msteams"]["default_channel_id"] = channel

    _save_config(config)

    typer.secho("Default channel updated.", fg=typer.colors.GREEN)

    if team:
        typer.echo(f"  Team: {team}")
    if channel:
        typer.echo(f"  Channel: {channel}")