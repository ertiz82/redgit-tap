"""
Microsoft Teams integration for RedGit.

Supports two modes:
1. Graph API (recommended): Full Teams access with Device Code Flow authentication
   - List teams, channels, users
   - Send to any channel
   - Send direct messages

2. Webhook (legacy): Simple notifications via Incoming Webhooks
   - Send to a single configured channel
   - No authentication required
"""

import os
import json
from typing import Optional, Dict, List, Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from redgit.integrations.base import NotificationBase, IntegrationType
except ImportError:
    from enum import Enum

    class IntegrationType(Enum):
        NOTIFICATION = "notification"

    class NotificationBase:
        integration_type = IntegrationType.NOTIFICATION

        def __init__(self):
            self.enabled = False
            self._config = {}

        def setup(self, config):
            pass

        def send_message(self, message, channel=None):
            pass

        def set_config(self, config):
            self._config = config


class MSTeamsIntegration(NotificationBase):
    """
    Microsoft Teams notification integration.

    Supports both Graph API and Webhook modes:
    - Graph API: Full access to teams, channels, DMs
    - Webhook: Simple notifications to a single channel
    """

    name = "msteams"
    integration_type = IntegrationType.NOTIFICATION

    # Capability flags
    supports_buttons = False
    supports_polls = False
    supports_threads = True
    supports_reactions = False
    supports_webhooks = False

    def __init__(self):
        super().__init__()
        # Graph API
        self.tenant_id = ""
        self.client_id = ""
        self.access_token = ""
        self.refresh_token = ""
        self.token_expires_at = 0
        self.default_team_id = ""
        self.default_channel_id = ""
        self._graph_client = None

        # Webhook fallback
        self.webhook_url = ""

    def setup(self, config: dict):
        """Setup MS Teams with Graph API or webhook."""
        # Graph API credentials
        self.tenant_id = config.get("tenant_id", "")
        self.client_id = config.get("client_id", "")
        self.access_token = config.get("access_token", "")
        self.refresh_token = config.get("refresh_token", "")
        self.token_expires_at = config.get("token_expires_at", 0)
        self.default_team_id = config.get("default_team_id", "")
        self.default_channel_id = config.get("default_channel_id", "")

        # Webhook fallback
        self.webhook_url = config.get("webhook_url") or os.getenv(
            "MSTEAMS_WEBHOOK_URL", ""
        )

        # Initialize Graph client if we have tokens
        if self.access_token and self.tenant_id and self.client_id:
            try:
                from .graph_client import GraphClient

                self._graph_client = GraphClient(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    access_token=self.access_token,
                    refresh_token=self.refresh_token,
                    token_expires_at=self.token_expires_at,
                    on_token_refresh=self._save_tokens,
                )
                self.enabled = True
            except Exception:
                self._graph_client = None

        # Enable with webhook if Graph API not available
        if not self.enabled and self.webhook_url:
            self.enabled = True

    def _save_tokens(self, access_token: str, refresh_token: str, expires_at: int):
        """Callback to save refreshed tokens to config."""
        try:
            from redgit.core.common.config import ConfigManager

            config = ConfigManager().load()
            if "integrations" not in config:
                config["integrations"] = {}
            if "msteams" not in config["integrations"]:
                config["integrations"]["msteams"] = {}

            config["integrations"]["msteams"]["access_token"] = access_token
            config["integrations"]["msteams"]["refresh_token"] = refresh_token
            config["integrations"]["msteams"]["token_expires_at"] = expires_at
            ConfigManager().save(config)

            # Update instance
            self.access_token = access_token
            self.refresh_token = refresh_token
            self.token_expires_at = expires_at
        except Exception:
            pass

    def send_message(self, message: str, channel: str = None) -> bool:
        """
        Send a message to a Teams channel.

        Uses Graph API if available, falls back to webhook.

        Args:
            message: Message text
            channel: Channel identifier (Graph: "team_id:channel_id", Webhook: ignored)

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        # Try Graph API first
        if self._graph_client:
            return self._send_via_graph(message, channel)

        # Fall back to webhook
        return self._send_via_webhook(message)

    def _send_via_graph(self, message: str, channel: str = None) -> bool:
        """Send message via Graph API."""
        try:
            team_id, channel_id = self._parse_channel(channel)

            if not team_id or not channel_id:
                return False

            self._graph_client.send_channel_message(team_id, channel_id, message)
            return True
        except Exception:
            return False

    def _send_via_webhook(self, message: str) -> bool:
        """Send message via webhook (legacy)."""
        if not self.webhook_url:
            return False

        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "text": message,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as response:
                return response.status == 200
        except (HTTPError, URLError):
            return False

    def send_dm(self, email: str, message: str) -> bool:
        """
        Send a direct message to a user (Graph API only).

        Args:
            email: User's email address
            message: Message text

        Returns:
            True if successful
        """
        if not self._graph_client:
            return False

        try:
            chat_id = self._graph_client.get_or_create_chat(email)
            if not chat_id:
                return False
            self._graph_client.send_chat_message(chat_id, message)
            return True
        except Exception:
            return False

    def notify(
        self,
        event_type: str,
        title: str,
        message: str = "",
        url: str = None,
        fields: Dict[str, str] = None,
        level: str = "info",
        channel: str = None,
    ) -> bool:
        """Send a rich notification with MessageCard formatting."""
        if not self.enabled:
            return False

        colors = {
            "info": "0078D7",
            "success": "28A745",
            "warning": "FFC107",
            "error": "DC3545",
        }
        color = colors.get(level, colors["info"])

        emojis = {
            "commit": "\U0001F528",
            "branch": "\U0001F331",
            "pr": "\U0001F500",
            "task": "\U0001F4CB",
            "deploy": "\U0001F680",
            "alert": "\U000026A0",
            "message": "\U0001F4AC",
        }
        emoji = emojis.get(event_type, "\U0001F514")

        # Build MessageCard
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": title,
            "sections": [
                {
                    "activityTitle": f"{emoji} {title}",
                    "activitySubtitle": f"via RedGit | {event_type}",
                    "facts": [],
                    "markdown": True,
                }
            ],
        }

        if message:
            payload["sections"][0]["text"] = message

        if fields:
            payload["sections"][0]["facts"] = [
                {"name": k, "value": str(v)} for k, v in fields.items()
            ]

        if url:
            payload["potentialAction"] = [
                {"@type": "OpenUri", "name": "View Details", "targets": [{"os": "default", "uri": url}]}
            ]

        # Send via Graph API or webhook
        if self._graph_client:
            try:
                team_id, channel_id = self._parse_channel(channel)
                if team_id and channel_id:
                    # Graph API: send as HTML with card formatting
                    html_content = self._card_to_html(payload)
                    self._graph_client.send_channel_message(
                        team_id, channel_id, html_content
                    )
                    return True
            except Exception:
                pass

        # Fallback to webhook
        if self.webhook_url:
            try:
                data = json.dumps(payload).encode("utf-8")
                req = Request(
                    self.webhook_url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=10) as response:
                    return response.status == 200
            except (HTTPError, URLError):
                pass

        return False

    def _card_to_html(self, card: dict) -> str:
        """Convert MessageCard to HTML for Graph API."""
        sections = card.get("sections", [])
        if not sections:
            return card.get("summary", "")

        section = sections[0]
        html = f"<b>{section.get('activityTitle', '')}</b><br>"

        if section.get("text"):
            html += f"{section.get('text')}<br>"

        facts = section.get("facts", [])
        if facts:
            html += "<br>"
            for fact in facts:
                html += f"<b>{fact['name']}:</b> {fact['value']}<br>"

        actions = card.get("potentialAction", [])
        if actions:
            for action in actions:
                if action.get("@type") == "OpenUri":
                    targets = action.get("targets", [])
                    if targets:
                        uri = targets[0].get("uri", "")
                        html += f'<br><a href="{uri}">{action.get("name", "View")}</a>'

        return html

    def _parse_channel(self, channel: str = None) -> tuple:
        """Parse channel string into team_id and channel_id."""
        if not channel:
            return self.default_team_id, self.default_channel_id

        if ":" in channel:
            parts = channel.split(":", 1)
            return parts[0], parts[1]

        return self.default_team_id, channel

    # ========== Discovery Methods for CLI ==========

    def is_authenticated(self) -> bool:
        """Check if user is authenticated with valid Graph API tokens."""
        if not self._graph_client:
            return False

        try:
            self._graph_client.get_me()
            return True
        except Exception:
            return False

    def list_teams(self) -> List[dict]:
        """List all teams the user has access to."""
        if not self._graph_client:
            return []
        try:
            return self._graph_client.list_joined_teams()
        except Exception:
            return []

    def list_channels(self, team_id: str) -> List[dict]:
        """List channels in a team."""
        if not self._graph_client:
            return []
        try:
            return self._graph_client.list_channels(team_id)
        except Exception:
            return []

    def list_users(self, search: str = None) -> List[dict]:
        """List users for DM targeting."""
        if not self._graph_client:
            return []
        try:
            return self._graph_client.list_users(search)
        except Exception:
            return []

    def get_current_user(self) -> Optional[dict]:
        """Get current authenticated user info."""
        if not self._graph_client:
            return None
        try:
            return self._graph_client.get_me()
        except Exception:
            return None

    @staticmethod
    def after_install(config_values: dict) -> dict:
        """Hook called after install wizard."""
        import typer

        # Test webhook if provided
        webhook_url = config_values.get("webhook_url", "")
        if webhook_url:
            typer.echo("\n   Testing MS Teams webhook...")
            temp = MSTeamsIntegration()
            temp.webhook_url = webhook_url
            temp.enabled = True
            if temp.send_message("\u2705 RedGit connected successfully!"):
                typer.secho("   Test message sent!", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to send test message", fg=typer.colors.RED)

        # Prompt for Graph API auth if configured
        tenant_id = config_values.get("tenant_id", "")
        client_id = config_values.get("client_id", "")
        if tenant_id and client_id:
            typer.echo("\n   Graph API configured.")
            typer.echo("   Run 'rg msteams login' to authenticate.")

        return config_values