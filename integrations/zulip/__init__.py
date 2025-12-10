"""
Zulip integration for RedGit.

Send notifications to Zulip streams via Bot API.
"""

import os
import json
import base64
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


class ZulipIntegration(NotificationBase):
    """Zulip notification integration via Bot API"""

    name = "zulip"
    integration_type = IntegrationType.NOTIFICATION

    def __init__(self):
        super().__init__()
        self.server_url = ""
        self.bot_email = ""
        self.api_key = ""
        self.stream = ""
        self.topic = "RedGit"

    def setup(self, config: dict):
        """Setup Zulip bot."""
        self.server_url = config.get("server_url") or os.getenv("ZULIP_SERVER_URL", "")
        self.bot_email = config.get("bot_email") or os.getenv("ZULIP_BOT_EMAIL", "")
        self.api_key = config.get("api_key") or os.getenv("ZULIP_API_KEY", "")
        self.stream = config.get("stream") or os.getenv("ZULIP_STREAM", "")
        self.topic = config.get("topic", "RedGit")

        # Remove trailing slash
        self.server_url = self.server_url.rstrip("/")

        if not all([self.server_url, self.bot_email, self.api_key, self.stream]):
            self.enabled = False
            return

        self.enabled = True

    def send_message(self, message: str, channel: str = None) -> bool:
        """Send a simple text message."""
        if not self.enabled:
            return False

        return self._send_stream_message(
            stream=channel or self.stream,
            topic=self.topic,
            content=message
        )

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
            "commit": ":hammer:",
            "branch": ":seedling:",
            "pr": ":twisted_rightwards_arrows:",
            "task": ":clipboard:",
            "deploy": ":rocket:",
            "alert": ":warning:",
            "message": ":speech_balloon:",
        }
        emoji = emojis.get(event_type, ":bell:")

        level_emojis = {
            "info": ":information_source:",
            "success": ":check:",
            "warning": ":warning:",
            "error": ":cross_mark:",
        }
        level_emoji = level_emojis.get(level, "")

        # Build message content (Zulip uses Markdown)
        lines = [f"## {emoji} {title}"]

        if message:
            lines.append(f"\n{message}")

        if fields:
            lines.append("")
            for k, v in fields.items():
                lines.append(f"**{k}:** {v}")

        if url:
            lines.append(f"\n[View Details]({url})")

        lines.append(f"\n{level_emoji} *via RedGit*")

        content = "\n".join(lines)
        topic = f"{event_type}: {title[:30]}" if title else self.topic

        return self._send_stream_message(
            stream=channel or self.stream,
            topic=topic,
            content=content
        )

    def _send_stream_message(self, stream: str, topic: str, content: str) -> bool:
        """Send message to Zulip stream."""
        try:
            url = f"{self.server_url}/api/v1/messages"

            # Zulip uses form data
            from urllib.parse import urlencode
            payload = {
                "type": "stream",
                "to": stream,
                "topic": topic,
                "content": content
            }
            data = urlencode(payload).encode("utf-8")

            # Basic auth with bot email and API key
            auth = base64.b64encode(
                f"{self.bot_email}:{self.api_key}".encode()
            ).decode()

            req = Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth}"
                },
                method="POST"
            )

            with urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("result") == "success"
        except (HTTPError, URLError):
            return False

    @staticmethod
    def after_install(config_values: dict) -> dict:
        import typer
        server_url = config_values.get("server_url", "")
        bot_email = config_values.get("bot_email", "")
        api_key = config_values.get("api_key", "")
        stream = config_values.get("stream", "")

        if all([server_url, bot_email, api_key, stream]):
            typer.echo("\n   Testing Zulip bot...")
            temp = ZulipIntegration()
            temp.server_url = server_url.rstrip("/")
            temp.bot_email = bot_email
            temp.api_key = api_key
            temp.stream = stream
            temp.topic = "RedGit"
            temp.enabled = True
            if temp.send_message(":check: RedGit connected successfully!"):
                typer.secho("   Test message sent!", fg=typer.colors.GREEN)
            else:
                typer.secho("   Failed to send test message", fg=typer.colors.RED)
        return config_values