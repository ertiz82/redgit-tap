"""
Telegram integration for RedGit.

Send notifications to Telegram chats via Bot API.
Supports interactive features: inline keyboards, polls, and webhooks.
"""

import os
import json
from typing import Optional, Dict, List, Any
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
        supports_buttons = False
        supports_polls = False
        supports_webhooks = False
        def __init__(self):
            self.enabled = False
        def setup(self, config): pass
        def send_message(self, message, channel=None): pass
        def get_capabilities(self): return {}


class TelegramIntegration(NotificationBase):
    """Telegram notification integration via Bot API"""

    name = "telegram"
    integration_type = IntegrationType.NOTIFICATION

    # Capability flags
    supports_buttons = True
    supports_polls = True
    supports_threads = False
    supports_reactions = False
    supports_webhooks = True

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

    # =========================================================================
    # INTERACTIVE METHODS (v2)
    # =========================================================================

    def send_interactive(
        self,
        message: str,
        buttons: List[Dict[str, Any]] = None,
        channel: str = None
    ) -> Optional[str]:
        """
        Send a message with inline keyboard buttons.

        Args:
            message: Message text (HTML formatted)
            buttons: List of button definitions:
                - {"text": "Label", "action": "action_id", "data": {...}}
                - {"text": "Label", "url": "https://..."}
            channel: Optional chat ID override

        Returns:
            Message ID if successful, None otherwise
        """
        if not self.enabled:
            return None

        chat_id = channel or self.chat_id

        # Build inline keyboard
        keyboard = []
        if buttons:
            row = []
            for btn in buttons:
                if "url" in btn:
                    # URL button
                    row.append({
                        "text": btn["text"],
                        "url": btn["url"]
                    })
                else:
                    # Callback button
                    action = btn.get("action", "unknown")
                    data = btn.get("data", {})
                    callback_data = f"{action}:{json.dumps(data, separators=(',', ':'))}"

                    # Telegram callback_data has 64 byte limit
                    if len(callback_data) > 64:
                        callback_data = callback_data[:64]

                    row.append({
                        "text": btn["text"],
                        "callback_data": callback_data
                    })

                # Max 8 buttons per row, start new row
                if len(row) >= 3:
                    keyboard.append(row)
                    row = []

            if row:
                keyboard.append(row)

        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": self.parse_mode
        }

        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}

        result = self._api_call("sendMessage", payload)
        if result and result.get("ok"):
            return str(result.get("result", {}).get("message_id"))
        return None

    def send_poll(
        self,
        question: str,
        options: List[str],
        channel: str = None,
        anonymous: bool = False,
        allows_multiple: bool = False
    ) -> Optional[str]:
        """
        Send a poll.

        Args:
            question: Poll question (1-300 characters)
            options: List of answer options (2-10 options)
            channel: Optional chat ID override
            anonymous: Whether votes are anonymous
            allows_multiple: Whether multiple answers are allowed

        Returns:
            Poll ID if successful, None otherwise
        """
        if not self.enabled:
            return None

        if len(options) < 2 or len(options) > 10:
            return None

        chat_id = channel or self.chat_id

        payload = {
            "chat_id": chat_id,
            "question": question[:300],
            "options": json.dumps(options),
            "is_anonymous": anonymous,
            "allows_multiple_answers": allows_multiple
        }

        result = self._api_call("sendPoll", payload)
        if result and result.get("ok"):
            return str(result.get("result", {}).get("poll", {}).get("id"))
        return None

    def handle_callback(self, callback_data: dict) -> Optional[str]:
        """
        Handle a callback query from button click.

        Args:
            callback_data: Telegram callback_query object

        Returns:
            Response message or None
        """
        callback_id = callback_data.get("id")
        data = callback_data.get("data", "")

        # Parse callback data
        if ":" in data:
            action, payload_str = data.split(":", 1)
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                payload = {"raw": payload_str}
        else:
            action = data
            payload = {}

        # Execute action via ActionRegistry if available
        try:
            from redgit.core.actions import ActionRegistry, ActionContext

            context = ActionContext(
                user_id=str(callback_data.get("from", {}).get("id", "")),
                message_id=str(callback_data.get("message", {}).get("message_id", "")),
                chat_id=str(callback_data.get("message", {}).get("chat", {}).get("id", "")),
                integration="telegram",
                raw_data=callback_data
            )

            result = ActionRegistry.execute(action, payload, context)

            # Answer callback query
            self._answer_callback(callback_id, result.message or ("Done!" if result.success else result.error))

            return result.message

        except ImportError:
            # RedGit not available, just acknowledge
            self._answer_callback(callback_id, f"Action: {action}")
            return None

    def setup_webhook(self, url: str) -> bool:
        """
        Configure Telegram webhook URL.

        Args:
            url: Public webhook URL (must be HTTPS)

        Returns:
            True if webhook was configured successfully
        """
        if not self.enabled:
            return False

        webhook_url = f"{url}/telegram" if not url.endswith("/telegram") else url

        payload = {
            "url": webhook_url,
            "allowed_updates": json.dumps(["callback_query", "poll_answer"])
        }

        result = self._api_call("setWebhook", payload)
        return result.get("ok", False) if result else False

    def delete_webhook(self) -> bool:
        """Remove Telegram webhook (use polling instead)."""
        if not self.enabled:
            return False

        result = self._api_call("deleteWebhook", {})
        return result.get("ok", False) if result else False

    def get_webhook_info(self) -> Optional[Dict[str, Any]]:
        """Get current webhook configuration."""
        if not self.enabled:
            return None

        result = self._api_call("getWebhookInfo", {}, method="GET")
        if result and result.get("ok"):
            return result.get("result")
        return None

    def _api_call(
        self,
        method: str,
        payload: Dict[str, Any],
        method_type: str = "POST"
    ) -> Optional[Dict[str, Any]]:
        """Make a Telegram Bot API call."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                url,
                data=data if method_type == "POST" else None,
                headers={"Content-Type": "application/json"},
                method=method_type
            )
            with urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, json.JSONDecodeError):
            return None

    def _answer_callback(self, callback_id: str, text: str = None, show_alert: bool = False):
        """Answer a callback query."""
        if not callback_id:
            return

        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text[:200]  # Max 200 chars
            payload["show_alert"] = show_alert

        self._api_call("answerCallbackQuery", payload)