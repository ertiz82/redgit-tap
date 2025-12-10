"""
Slack Integration for RedGit

Send commit notifications, PR updates, and task status changes to Slack channels.

Features:
- Commit notifications with diff summary
- PR creation/merge notifications
- Task status change alerts
- Customizable message templates
- Support for multiple channels
"""

import os
import json
from typing import Optional, Dict, Any, List
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

from redgit.integrations.base import NotificationBase, IntegrationType


class SlackIntegration(NotificationBase):
    """
    Slack notification integration for RedGit.

    Configuration (.redgit/config.yaml):
        integrations:
          slack:
            enabled: true
            webhook_url: "https://hooks.slack.com/services/..."
            channel: "#dev-commits"
            username: "RedGit Bot"
            icon_emoji: ":robot_face:"
            notify_on:
              - commit
              - branch
              - pr
    """

    name = "slack"
    integration_type = IntegrationType.NOTIFICATION

    def __init__(self):
        super().__init__()
        self.webhook_url = ""
        self.channel = ""
        self.username = "RedGit"
        self.icon_emoji = ":git:"
        self.notify_on: List[str] = ["commit", "branch"]

    def setup(self, config: dict):
        """Initialize Slack integration with config values."""
        self.webhook_url = config.get("webhook_url") or os.getenv("SLACK_WEBHOOK_URL", "")
        self.channel = config.get("channel", "")
        self.username = config.get("username", "RedGit")
        self.icon_emoji = config.get("icon_emoji", ":git:")
        self.notify_on = config.get("notify_on", ["commit", "branch"])

        if not self.webhook_url:
            self.enabled = False
            return

        self.enabled = True

    def validate_connection(self) -> bool:
        """Test Slack webhook connectivity."""
        if not self.enabled or not self.webhook_url:
            return False

        # Send a test message (won't actually post, just validates URL format)
        try:
            # Just check if webhook URL is valid format
            return self.webhook_url.startswith("https://hooks.slack.com/")
        except Exception:
            return False

    def send_message(
        self,
        text: str,
        blocks: Optional[List[Dict]] = None,
        channel: Optional[str] = None
    ) -> bool:
        """
        Send a message to Slack.

        Args:
            text: Fallback text for notifications
            blocks: Rich message blocks (optional)
            channel: Override default channel (optional)

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        payload = {
            "text": text,
            "username": self.username,
            "icon_emoji": self.icon_emoji,
        }

        if channel or self.channel:
            payload["channel"] = channel or self.channel

        if blocks:
            payload["blocks"] = blocks

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
        except (HTTPError, URLError, Exception):
            return False

    # ==================== Event Handlers ====================

    def on_commit(self, commit_data: dict):
        """Send notification when a commit is created."""
        if "commit" not in self.notify_on:
            return

        branch = commit_data.get("branch", "unknown")
        message = commit_data.get("message", "No message")
        files = commit_data.get("files", [])
        author = commit_data.get("author", "Unknown")

        # Build message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔨 New Commit",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Branch:*\n`{branch}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Author:*\n{author}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message:*\n```{message}```"
                }
            }
        ]

        if files:
            file_list = "\n".join(f"• `{f}`" for f in files[:10])
            if len(files) > 10:
                file_list += f"\n... and {len(files) - 10} more"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Files ({len(files)}):*\n{file_list}"
                }
            })

        self.send_message(
            text=f"New commit on {branch}: {message[:50]}...",
            blocks=blocks
        )

    def on_branch_create(self, branch_name: str, issue_key: Optional[str] = None):
        """Send notification when a branch is created."""
        if "branch" not in self.notify_on:
            return

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🌿 New Branch Created",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Branch:* `{branch_name}`"
                }
            }
        ]

        if issue_key:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Linked Issue:* {issue_key}"
                }
            })

        self.send_message(
            text=f"New branch created: {branch_name}",
            blocks=blocks
        )

    def on_pr_create(self, pr_data: dict):
        """Send notification when a PR is created."""
        if "pr" not in self.notify_on:
            return

        title = pr_data.get("title", "Untitled PR")
        url = pr_data.get("url", "")
        branch = pr_data.get("head", "unknown")
        base = pr_data.get("base", "main")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔀 Pull Request Created",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{url}|{title}>*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*From:*\n`{branch}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*To:*\n`{base}`"
                    }
                ]
            }
        ]

        self.send_message(
            text=f"PR Created: {title}",
            blocks=blocks
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
        """
        Send a rich notification to Slack.

        This implements the standard NotificationBase interface so other
        integrations can send notifications through Slack.

        Args:
            event_type: Type of event (commit, branch, pr, task, deploy, alert, etc.)
            title: Notification title
            message: Notification body/description
            url: Optional URL to link to
            fields: Optional key-value pairs to display
            level: Notification level (info, success, warning, error)
            channel: Optional channel override

        Returns:
            True if successful
        """
        # Color based on level
        colors = {
            "info": "#2196F3",      # Blue
            "success": "#4CAF50",   # Green
            "warning": "#FF9800",   # Orange
            "error": "#F44336",     # Red
        }
        color = colors.get(level, colors["info"])

        # Event emoji
        emojis = {
            "commit": "🔨",
            "branch": "🌿",
            "pr": "🔀",
            "task": "📋",
            "deploy": "🚀",
            "alert": "⚠️",
            "message": "💬",
        }
        emoji = emojis.get(event_type, "📣")

        # Build attachment (for colored sidebar)
        attachment = {
            "color": color,
            "blocks": []
        }

        # Header
        header_text = f"{emoji} {title}"
        if url:
            header_text = f"{emoji} <{url}|{title}>"

        attachment["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{header_text}*"
            }
        })

        # Message body
        if message:
            attachment["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            })

        # Fields (key-value pairs)
        if fields:
            field_blocks = []
            for key, value in fields.items():
                field_blocks.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:*\n{value}"
                })

            # Split into groups of 2 for side-by-side display
            for i in range(0, len(field_blocks), 2):
                attachment["blocks"].append({
                    "type": "section",
                    "fields": field_blocks[i:i+2]
                })

        # Context footer
        attachment["blocks"].append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"via RedGit • {event_type}"
                }
            ]
        })

        # Build payload with attachments for colored sidebar
        payload = {
            "text": f"{emoji} {title}",
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [attachment]
        }

        if channel or self.channel:
            payload["channel"] = channel or self.channel

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
        except (HTTPError, URLError, Exception):
            return False

    # ==================== Custom Methods ====================

    def send_custom_message(
        self,
        message: str,
        channel: Optional[str] = None,
        mention: Optional[str] = None
    ) -> bool:
        """
        Send a custom message to Slack.

        Args:
            message: Message text (supports markdown)
            channel: Channel to send to (optional)
            mention: User/group to mention, e.g., "@here", "@channel", "<@U123>"

        Returns:
            True if successful
        """
        text = message
        if mention:
            text = f"{mention} {message}"

        return self.send_message(text=text, channel=channel)

    @classmethod
    def after_install(cls, config: dict) -> dict:
        """Hook called after installation."""
        # Set default notify_on if not specified
        if "notify_on" not in config:
            config["notify_on"] = ["commit", "branch"]
        return config