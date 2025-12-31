"""Data models for Microsoft Teams integration."""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class TokenInfo:
    """OAuth token information."""
    access_token: str
    refresh_token: str
    expires_at: int
    token_type: str = "Bearer"
    scope: str = ""


@dataclass
class Team:
    """Represents a Microsoft Teams team."""
    id: str
    display_name: str
    description: Optional[str] = None


@dataclass
class Channel:
    """Represents a channel within a team."""
    id: str
    display_name: str
    description: Optional[str] = None
    membership_type: str = "standard"


@dataclass
class User:
    """Represents a Teams/Azure AD user."""
    id: str
    display_name: str
    email: Optional[str] = None
    user_principal_name: Optional[str] = None


@dataclass
class Chat:
    """Represents a 1:1 or group chat."""
    id: str
    chat_type: str
    topic: Optional[str] = None
    members: Optional[List[str]] = None