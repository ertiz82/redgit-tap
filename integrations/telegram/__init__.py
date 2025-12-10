"""
Telegram integration for RedGit.

Send notifications to Telegram chats via Bot API.
"""

import os
import json
from typing import Optional, Dict
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import quote

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


class TelegramIntegration(NotificationBase):
    """Telegram notification integration via Bot API"""

    name = "telegram"
    integration_type = IntegrationType.NOTIFICATION

    def __init__(self):
        super().__init__()
        self.bot_token = ""
        self.chat_id = ""
        self.parse_mode = "HTML"

    def setup(self, config: dict):
        """Setup Telegram bot."""
        self.bot_token = config.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = config.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID", "")
        self.parse_mode = config.get("parse_mode", "HTML")

        if not self.bot_token or not self.chat_id:
            self.enabled = False
            return

        self.enabled = True

    def send_message(self, message: str, channel: str = None) -> bool:
        """Send a simple text message."""
        if not self.enabled:
            return False

        chat_id = channel or self.chat_id
        return self._send_message(chat_id, message)

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
        """Send a formatted notification."""
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

        # Build message
        lines = [f"{emoji} <b>{self._escape_html(title)}</b>"]

        if message:
            lines.append(f"\n{self._escape_html(message)}")

        if fields:
            lines.append("")
            for k, v in fields.items():
                lines.append(f"<b>{self._escape_html(k)}:</b> {self._escape_html(str(v))}")

        if url:
            lines.append(f"\n<a href=\"{url}\">View Details</a>")

        lines.append(f"\n{level_icon} <i>via RedGit</i>")

        text = "\n".join(lines)
        chat_id = channel or self.chat_id

        return self._send_message(chat_id, text)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _send_message(self, chat_id: str, text: str) -> bool:
        """Send message via Telegram Bot API."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": self.parse_mode,
                "disable_web_page_preview": False
            }
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("ok", False)
        except (HTTPError, URLError):
            return False

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        bot_token = config_values.get("bot_token", "")
        chat_id = config_values.get("chat_id", "")
        if bot_token and chat_id:
            typer.echo("\n   Testing Telegram bot...")
            temp = TelegramIntegration()
            temp.bot_token = bot_token
            temp.chat_id = chat_id
            temp.parse_mode = "HTML"
            temp.enabled = True
            if temp.send_message("\U00002705 RedGit connected successfully!"):
                typer.secho("   Test message sent!", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to send test message", fg=typer.colors.RED)
        return config_values