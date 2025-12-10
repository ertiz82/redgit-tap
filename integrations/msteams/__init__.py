"""
Microsoft Teams integration for RedGit.

Send notifications to Teams channels via Incoming Webhooks.
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


class MSTeamsIntegration(NotificationBase):
    """Microsoft Teams notification integration via Incoming Webhooks"""

    name = "msteams"
    integration_type = IntegrationType.NOTIFICATION

    def __init__(self):
        super().__init__()
        self.webhook_url = ""

    def setup(self, config: dict):
        """Setup MS Teams webhook."""
        self.webhook_url = config.get("webhook_url") or os.getenv("MSTEAMS_WEBHOOK_URL", "")

        if not self.webhook_url:
            self.enabled = False
            return

        self.enabled = True

    def send_message(self, message: str, channel: str = None) -> bool:
        """Send a simple text message."""
        if not self.enabled:
            return False

        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "text": message
        }

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
        """Send a rich notification with adaptive card."""
        if not self.enabled:
            return False

        colors = {
            "info": "0078D7",      # Blue
            "success": "28A745",   # Green
            "warning": "FFC107",   # Yellow
            "error": "DC3545",     # Red
        }
        color = colors.get(level, colors["info"])

        emojis = {
            "commit": "\U0001F528",      # Hammer
            "branch": "\U0001F331",      # Seedling
            "pr": "\U0001F500",          # Twisted arrows
            "task": "\U0001F4CB",        # Clipboard
            "deploy": "\U0001F680",      # Rocket
            "alert": "\U000026A0",       # Warning
            "message": "\U0001F4AC",     # Speech balloon
        }
        emoji = emojis.get(event_type, "\U0001F514")  # Bell

        # Build MessageCard
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": title,
            "sections": [{
                "activityTitle": f"{emoji} {title}",
                "activitySubtitle": f"via RedGit | {event_type}",
                "facts": [],
                "markdown": True
            }]
        }

        if message:
            payload["sections"][0]["text"] = message

        if fields:
            payload["sections"][0]["facts"] = [
                {"name": k, "value": str(v)}
                for k, v in fields.items()
            ]

        if url:
            payload["potentialAction"] = [{
                "@type": "OpenUri",
                "name": "View Details",
                "targets": [{"os": "default", "uri": url}]
            }]

        return self._send_webhook(payload)

    def _send_webhook(self, payload: dict) -> bool:
        """Send payload to Teams webhook."""
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
            typer.echo("\n   Testing MS Teams webhook...")
            temp = MSTeamsIntegration()
            temp.webhook_url = webhook_url
            temp.enabled = True
            if temp.send_message("\U00002705 RedGit connected successfully!"):
                typer.secho("   Test message sent!", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to send test message", fg=typer.colors.RED)
        return config_values