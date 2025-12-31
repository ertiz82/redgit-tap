"""Custom exceptions for Microsoft Teams integration."""


class TeamsError(Exception):
    """Base exception for Teams integration."""
    pass


class AuthenticationError(TeamsError):
    """Authentication failed."""
    pass


class TokenRefreshError(TeamsError):
    """Failed to refresh access token."""
    pass


class GraphAPIError(TeamsError):
    """General Graph API error."""
    pass


class RateLimitError(GraphAPIError):
    """Rate limit exceeded."""
    pass


class NotFoundError(GraphAPIError):
    """Resource not found."""
    pass


class PermissionDeniedError(GraphAPIError):
    """Permission denied."""
    pass