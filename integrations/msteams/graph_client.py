"""
Microsoft Graph API client for Teams operations.

Handles all communication with Microsoft Graph API including:
- Token management with automatic refresh
- Rate limiting awareness
- Error handling with retries
"""

import json
import time
import importlib.util
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import quote

# Dynamic sibling import helper
def _import_sibling(module_name: str):
    module_path = Path(__file__).parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Import sibling modules
_auth = _import_sibling("auth")
_models = _import_sibling("models")
_exceptions = _import_sibling("exceptions")

DeviceCodeAuth = _auth.DeviceCodeAuth
TokenInfo = _models.TokenInfo
GraphAPIError = _exceptions.GraphAPIError
RateLimitError = _exceptions.RateLimitError
TokenRefreshError = _exceptions.TokenRefreshError
NotFoundError = _exceptions.NotFoundError
PermissionDeniedError = _exceptions.PermissionDeniedError

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class GraphClient:
    """
    Microsoft Graph API client with automatic token refresh.

    Usage:
        client = GraphClient(
            tenant_id="...",
            client_id="...",
            access_token="...",
            refresh_token="...",
            on_token_refresh=save_tokens_callback
        )

        teams = client.list_joined_teams()
        client.send_channel_message(team_id, channel_id, "Hello!")
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        access_token: str = "",
        refresh_token: str = "",
        token_expires_at: int = 0,
        on_token_refresh: Optional[Callable[[str, str, int], None]] = None,
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at
        self.on_token_refresh = on_token_refresh

        self._auth = DeviceCodeAuth(tenant_id, client_id)
        self._user_id_cache: Dict[str, str] = {}

    def _ensure_token(self):
        """Ensure we have a valid access token, refreshing if needed."""
        if not self.access_token:
            raise GraphAPIError("Not authenticated. Run 'rg msteams login' first.")

        # Check if token is expired (with 5-minute buffer)
        if self.token_expires_at and time.time() > (self.token_expires_at - 300):
            self.refresh_access_token()

    def refresh_access_token(self):
        """Refresh the access token using refresh token."""
        if not self.refresh_token:
            raise TokenRefreshError("No refresh token available. Run 'rg msteams login'.")

        try:
            token_info = self._auth.refresh_token(self.refresh_token)

            self.access_token = token_info.access_token
            self.refresh_token = token_info.refresh_token
            self.token_expires_at = token_info.expires_at

            # Callback to save tokens
            if self.on_token_refresh:
                self.on_token_refresh(
                    token_info.access_token,
                    token_info.refresh_token,
                    token_info.expires_at,
                )

        except TokenRefreshError:
            raise
        except Exception as e:
            raise TokenRefreshError(f"Token refresh failed: {e}")

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        content_type: str = "application/json",
        retry_on_401: bool = True,
    ) -> dict:
        """
        Make an authenticated request to Graph API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            data: Request body data
            content_type: Content-Type header
            retry_on_401: Retry with refreshed token on 401

        Returns:
            Response JSON as dict

        Raises:
            GraphAPIError: On API errors
            RateLimitError: On rate limiting (429)
        """
        self._ensure_token()

        url = f"{GRAPH_BASE_URL}{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": content_type,
        }

        body = None
        if data:
            body = json.dumps(data).encode()

        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=30) as response:
                if response.status == 204:
                    return {}
                return json.loads(response.read().decode())

        except HTTPError as e:
            status = e.code

            if status == 401 and retry_on_401:
                try:
                    self.refresh_access_token()
                    return self._request(method, endpoint, data, content_type, False)
                except TokenRefreshError:
                    raise GraphAPIError("Authentication expired. Run 'rg msteams login'.")

            elif status == 429:
                retry_after = e.headers.get("Retry-After", "60")
                raise RateLimitError(f"Rate limited. Retry after {retry_after} seconds.")

            elif status == 404:
                raise NotFoundError(f"Resource not found: {endpoint}")

            elif status == 403:
                raise PermissionDeniedError("Permission denied. Check app permissions.")

            else:
                error_body = e.read().decode()
                try:
                    error_json = json.loads(error_body)
                    message = error_json.get("error", {}).get("message", error_body)
                except json.JSONDecodeError:
                    message = error_body
                raise GraphAPIError(f"Graph API error ({status}): {message}")

    # ========== User Operations ==========

    def get_me(self) -> dict:
        """Get current authenticated user's profile."""
        return self._request("GET", "/me")

    def list_users(self, search: Optional[str] = None, limit: int = 50) -> List[dict]:
        """
        List users in the organization.

        Args:
            search: Optional search query (searches displayName and mail)
            limit: Maximum number of results

        Returns:
            List of user dicts
        """
        endpoint = f"/users?$top={limit}&$select=id,displayName,mail,userPrincipalName"

        if search:
            encoded_search = quote(search)
            endpoint += (
                f"&$filter=startswith(displayName,'{encoded_search}') "
                f"or startswith(mail,'{encoded_search}')"
            )

        result = self._request("GET", endpoint)
        return result.get("value", [])

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email address."""
        if email in self._user_id_cache:
            return {"id": self._user_id_cache[email]}

        try:
            result = self._request("GET", f"/users/{quote(email)}")
            self._user_id_cache[email] = result["id"]
            return result
        except NotFoundError:
            return None

    # ========== Team Operations ==========

    def list_joined_teams(self) -> List[dict]:
        """List all teams the current user has joined."""
        result = self._request("GET", "/me/joinedTeams")
        return result.get("value", [])

    def get_team(self, team_id: str) -> dict:
        """Get team details by ID."""
        return self._request("GET", f"/teams/{team_id}")

    # ========== Channel Operations ==========

    def list_channels(self, team_id: str) -> List[dict]:
        """List channels in a team."""
        result = self._request("GET", f"/teams/{team_id}/channels")
        return result.get("value", [])

    def get_channel(self, team_id: str, channel_id: str) -> dict:
        """Get channel details."""
        return self._request("GET", f"/teams/{team_id}/channels/{channel_id}")

    # ========== Message Operations ==========

    def send_channel_message(
        self,
        team_id: str,
        channel_id: str,
        content: Any,
        content_type: str = "html",
    ) -> dict:
        """
        Send a message to a Teams channel.

        Args:
            team_id: Team ID
            channel_id: Channel ID
            content: Message content (string or Adaptive Card dict)
            content_type: "html", "text", or "application/vnd.microsoft.card.adaptive"

        Returns:
            Created message details
        """
        endpoint = f"/teams/{team_id}/channels/{channel_id}/messages"

        if content_type == "application/vnd.microsoft.card.adaptive":
            body = {
                "body": {"contentType": "html", "content": ""},
                "attachments": [
                    {
                        "contentType": content_type,
                        "content": json.dumps(content)
                        if isinstance(content, dict)
                        else content,
                    }
                ],
            }
        else:
            body = {"body": {"contentType": content_type, "content": content}}

        return self._request("POST", endpoint, body)

    def reply_to_message(
        self,
        team_id: str,
        channel_id: str,
        message_id: str,
        content: str,
        content_type: str = "html",
    ) -> dict:
        """Reply to a message in a thread."""
        endpoint = (
            f"/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies"
        )

        body = {"body": {"contentType": content_type, "content": content}}

        return self._request("POST", endpoint, body)

    # ========== Chat (DM) Operations ==========

    def get_or_create_chat(self, user_email: str) -> Optional[str]:
        """
        Get or create a 1:1 chat with a user.

        Args:
            user_email: Target user's email address

        Returns:
            Chat ID or None if user not found
        """
        user = self.get_user_by_email(user_email)
        if not user:
            return None

        user_id = user["id"]

        me = self.get_me()
        my_id = me["id"]

        body = {
            "chatType": "oneOnOne",
            "members": [
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{my_id}')",
                },
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')",
                },
            ],
        }

        result = self._request("POST", "/chats", body)
        return result.get("id")

    def send_chat_message(
        self, chat_id: str, content: str, content_type: str = "html"
    ) -> dict:
        """Send a message to a chat (DM or group chat)."""
        endpoint = f"/chats/{chat_id}/messages"

        body = {"body": {"contentType": content_type, "content": content}}

        return self._request("POST", endpoint, body)

    def list_chats(self) -> List[dict]:
        """List user's chats."""
        result = self._request("GET", "/me/chats")
        return result.get("value", [])