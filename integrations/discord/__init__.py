"""
Discord integration for RedGit.

Send notifications to Discord channels via webhooks.
"""

import os
import json
from typing import Optional, Dict, List
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
        def setup(self, config): pass
        def send_message(self, message, channel=None): pass


class DiscordIntegration(NotificationBase):
    """Discord notification integration via webhooks"""

    name = "discord"
    integration_type = IntegrationType.NOTIFICATION

    def __init__(self):
        super().__init__()
        self.webhook_url = ""
        self.username = "RedGit"
        self.avatar_url = ""
        self.channel = None

    def setup(self, config: dict):
        """Setup Discord webhook."""
        self.webhook_url = config.get("webhook_url") or os.getenv("DISCORD_WEBHOOK_URL", "")
        self.username = config.get("username", "RedGit")
        self.avatar_url = config.get("avatar_url", "")

        if not self.webhook_url:
            self.enabled = False
            return

        self.enabled = True

    def send_message(self, message: str, channel: str = None) -> bool:
        """Send a simple text message."""
        if not self.enabled:
            return False

        payload = {
            "content": message,
            "username": self.username,
        }

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        return self._send_webhook(payload)

    def notify(
        self,
        event_type: str,
        title: str,
        message: str = "",
        url: str = None,
        fields: Dict[str, str] = None,
        level: str = "info",
        channel: str = None
    ) -> bool:
        """Send a rich notification with embed."""
        if not self.enabled:
            return False

        colors = {
            "info": 3447003,      # Blue
            "success": 3066993,   # Green
            "warning": 15105570,  # Orange
            "error": 15158332,    # Red
        }
        color = colors.get(level, colors["info"])

        emojis = {
            "commit": ":hammer:",
            "branch": ":seedling:",
            "pr": ":twisted_rightwards_arrows:",
            "task": ":clipboard:",
            "deploy": ":rocket:",
            "alert": ":warning:",
            "message": ":speech_balloon:",
        }
        emoji = emojis.get(event_type, ":bell:")

        embed = {
            "title": f"{emoji} {title}",
            "color": color,
        }

        if url:
            embed["url"] = url

        if message:
            embed["description"] = message

        if fields:
            embed["fields"] = [
                {"name": k, "value": str(v), "inline": True}
                for k, v in fields.items()
            ]

        embed["footer"] = {"text": f"via RedGit • {event_type}"}

        payload = {
            "username": self.username,
            "embeds": [embed]
        }

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        return self._send_webhook(payload)

    def _send_webhook(self, payload: dict) -> bool:
        """Send payload to Discord webhook."""
        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urlopen(req, timeout=10) as response:
                return response.status in [200, 204]
        except (HTTPError, URLError):
            return False

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        webhook_url = config_values.get("webhook_url", "")
        if webhook_url:
            typer.echo("\n   Testing Discord webhook...")
            temp = DiscordIntegration()
            temp.webhook_url = webhook_url
            temp.username = config_values.get("username", "RedGit")
            temp.enabled = True
            if temp.send_message("RedGit connected successfully!"):
                typer.secho("   Test message sent!", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to send test message", fg=typer.colors.RED)
        return config_values