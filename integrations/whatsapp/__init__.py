"""
WhatsApp integration for RedGit.

Send notifications via WhatsApp Business Cloud API.
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


class WhatsAppIntegration(NotificationBase):
    """WhatsApp notification integration via Business Cloud API"""

    name = "whatsapp"
    integration_type = IntegrationType.NOTIFICATION

    def __init__(self):
        super().__init__()
        self.access_token = ""
        self.phone_number_id = ""
        self.recipient_number = ""

    def setup(self, config: dict):
        """Setup WhatsApp Business API."""
        self.access_token = config.get("access_token") or os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.phone_number_id = config.get("phone_number_id") or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.recipient_number = config.get("recipient_number") or os.getenv("WHATSAPP_RECIPIENT_NUMBER", "")

        if not all([self.access_token, self.phone_number_id, self.recipient_number]):
            self.enabled = False
            return

        self.enabled = True

    def send_message(self, message: str, channel: str = None) -> bool:
        """Send a simple text message."""
        if not self.enabled:
            return False

        recipient = channel or self.recipient_number
        return self._send_text_message(recipient, message)

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
        """Send a rich notification."""
        if not self.enabled:
            return False

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

        level_icons = {
            "info": "\U0001F535",      # Blue circle
            "success": "\U00002705",   # Check mark
            "warning": "\U000026A0",   # Warning
            "error": "\U0000274C",     # X mark
        }
        level_icon = level_icons.get(level, "")

        # Build message (WhatsApp has limited formatting)
        lines = [f"{emoji} *{title}*"]

        if message:
            lines.append(f"\n{message}")

        if fields:
            lines.append("")
            for k, v in fields.items():
                lines.append(f"*{k}:* {v}")

        if url:
            lines.append(f"\n{url}")

        lines.append(f"\n{level_icon} _via RedGit_")

        text = "\n".join(lines)
        recipient = channel or self.recipient_number

        return self._send_text_message(recipient, text)

    def _send_text_message(self, recipient: str, text: str) -> bool:
        """Send text message via WhatsApp Business API."""
        try:
            url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"

            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "text",
                "text": {
                    "preview_url": True,
                    "body": text
                }
            }

            data = json.dumps(payload).encode("utf-8")
            req = Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token}"
                },
                method="POST"
            )

            with urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                return "messages" in result
        except (HTTPError, URLError):
            return False

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        access_token = config_values.get("access_token", "")
        phone_number_id = config_values.get("phone_number_id", "")
        recipient_number = config_values.get("recipient_number", "")

        if all([access_token, phone_number_id, recipient_number]):
            typer.echo("\n   Testing WhatsApp Business API...")
            temp = WhatsAppIntegration()
            temp.access_token = access_token
            temp.phone_number_id = phone_number_id
            temp.recipient_number = recipient_number
            temp.enabled = True
            if temp.send_message("\U00002705 RedGit connected successfully!"):
                typer.secho("   Test message sent!", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to send test message", fg=typer.colors.RED)
                typer.echo("   Check your credentials and recipient number")
        return config_values