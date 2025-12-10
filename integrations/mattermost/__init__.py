"""
Mattermost integration for RedGit.

Send notifications to Mattermost channels via Incoming Webhooks.
"""

import os
import json
from typing import Optional, Dict
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


class MattermostIntegration(NotificationBase):
    """Mattermost notification integration via Incoming Webhooks"""

    name = "mattermost"
    integration_type = IntegrationType.NOTIFICATION

    def __init__(self):
        super().__init__()
        self.webhook_url = ""
        self.username = "RedGit"
        self.icon_url = ""
        self.channel = None

    def setup(self, config: dict):
        """Setup Mattermost webhook."""
        self.webhook_url = config.get("webhook_url") or os.getenv("MATTERMOST_WEBHOOK_URL", "")
        self.username = config.get("username", "RedGit")
        self.icon_url = config.get("icon_url", "")
        self.channel = config.get("channel")

        if not self.webhook_url:
            self.enabled = False
            return

        self.enabled = True

    def send_message(self, message: str, channel: str = None) -> bool:
        """Send a simple text message."""
        if not self.enabled:
            return False

        payload = {
            "text": message,
            "username": self.username,
        }

        if channel or self.channel:
            payload["channel"] = channel or self.channel

        if self.icon_url:
            payload["icon_url"] = self.icon_url

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
        """Send a rich notification with attachment."""
        if not self.enabled:
            return False

        colors = {
            "info": "#3AA3E3",      # Blue
            "success": "#2EB67D",   # Green
            "warning": "#ECB22E",   # Yellow
            "error": "#E01E5A",     # Red
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

        # Build attachment
        attachment = {
            "fallback": f"{title}: {message}",
            "color": color,
            "title": f"{emoji} {title}",
            "footer": f"via RedGit | {event_type}",
        }

        if url:
            attachment["title_link"] = url

        if message:
            attachment["text"] = message

        if fields:
            attachment["fields"] = [
                {"short": True, "title": k, "value": str(v)}
                for k, v in fields.items()
            ]

        payload = {
            "username": self.username,
            "attachments": [attachment]
        }

        if channel or self.channel:
            payload["channel"] = channel or self.channel

        if self.icon_url:
            payload["icon_url"] = self.icon_url

        return self._send_webhook(payload)

    def _send_webhook(self, payload: dict) -> bool:
        """Send payload to Mattermost webhook."""
        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urlopen(req, timeout=10) as response:
                return response.status == 200
        except (HTTPError, URLError):
            return False

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        webhook_url = config_values.get("webhook_url", "")
        if webhook_url:
            typer.echo("\n   Testing Mattermost webhook...")
            temp = MattermostIntegration()
            temp.webhook_url = webhook_url
            temp.username = config_values.get("username", "RedGit")
            temp.channel = config_values.get("channel")
            temp.enabled = True
            if temp.send_message(":white_check_mark: RedGit connected successfully!"):
                typer.secho("   Test message sent!", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to send test message", fg=typer.colors.RED)
        return config_values