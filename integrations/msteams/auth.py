"""
OAuth Device Code Flow for Microsoft Graph API.

Implements the Device Code Flow which is ideal for CLI applications:
1. User runs 'rg msteams login'
2. CLI displays a code and URL
3. User opens browser, enters code, and authenticates
4. CLI receives tokens automatically
"""

import json
import time
import webbrowser
from typing import Optional, Callable
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import importlib.util
from pathlib import Path

# Dynamic sibling import helper
def _import_sibling(module_name: str):
    module_path = Path(__file__).parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Import sibling modules
_models = _import_sibling("models")
_exceptions = _import_sibling("exceptions")

TokenInfo = _models.TokenInfo
AuthenticationError = _exceptions.AuthenticationError
TokenRefreshError = _exceptions.TokenRefreshError

# Microsoft identity platform endpoints
AUTHORITY = "https://login.microsoftonline.com"
DEVICE_CODE_ENDPOINT = "/oauth2/v2.0/devicecode"
TOKEN_ENDPOINT = "/oauth2/v2.0/token"

# Graph API permissions required
SCOPES = [
    "User.Read.All",
    "Team.ReadBasic.All",
    "Channel.ReadBasic.All",
    "ChannelMessage.Send",
    "ChatMessage.Send",
    "Chat.Create",
    "offline_access",
]


class DeviceCodeAuth:
    """
    Device Code Flow authentication for Microsoft Graph API.

    Usage:
        auth = DeviceCodeAuth(tenant_id, client_id)
        tokens = auth.authenticate()  # Displays code, waits for user
    """

    def __init__(self, tenant_id: str, client_id: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.authority_url = f"{AUTHORITY}/{tenant_id}"

    def authenticate(
        self,
        open_browser: bool = True,
        on_user_code: Optional[Callable[[str, str], None]] = None,
    ) -> TokenInfo:
        """
        Perform Device Code Flow authentication.

        Args:
            open_browser: Automatically open browser to verification URL
            on_user_code: Callback when user code is ready (code, url)

        Returns:
            TokenInfo with access and refresh tokens

        Raises:
            AuthenticationError: If authentication fails
        """
        # Step 1: Request device code
        device_code_response = self._request_device_code()

        user_code = device_code_response["user_code"]
        verification_url = device_code_response["verification_uri"]
        device_code = device_code_response["device_code"]
        expires_in = device_code_response.get("expires_in", 900)
        interval = device_code_response.get("interval", 5)

        # Notify about user code
        if on_user_code:
            on_user_code(user_code, verification_url)
        else:
            print(f"\nTo sign in, use a web browser to open {verification_url}")
            print(f"and enter the code: {user_code}\n")

        # Open browser automatically
        if open_browser:
            try:
                webbrowser.open(verification_url)
            except Exception:
                pass

        # Step 2: Poll for token
        return self._poll_for_token(device_code, expires_in, interval)

    def _request_device_code(self) -> dict:
        """Request device code from Azure AD."""
        url = f"{self.authority_url}{DEVICE_CODE_ENDPOINT}"

        data = (
            f"client_id={self.client_id}&scope={' '.join(SCOPES)}"
        ).encode()

        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            error_body = e.read().decode()
            raise AuthenticationError(f"Failed to get device code: {error_body}")

    def _poll_for_token(
        self, device_code: str, expires_in: int, interval: int
    ) -> TokenInfo:
        """Poll Azure AD for token after user authenticates."""
        url = f"{self.authority_url}{TOKEN_ENDPOINT}"

        data = (
            f"client_id={self.client_id}"
            f"&grant_type=urn:ietf:params:oauth:grant-type:device_code"
            f"&device_code={device_code}"
        ).encode()

        deadline = time.time() + expires_in

        while time.time() < deadline:
            time.sleep(interval)

            request = Request(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            try:
                with urlopen(request, timeout=30) as response:
                    result = json.loads(response.read().decode())

                    return TokenInfo(
                        access_token=result["access_token"],
                        refresh_token=result.get("refresh_token", ""),
                        expires_at=int(time.time()) + result.get("expires_in", 3600),
                        token_type=result.get("token_type", "Bearer"),
                        scope=result.get("scope", ""),
                    )

            except HTTPError as e:
                error_body = json.loads(e.read().decode())
                error_code = error_body.get("error")

                if error_code == "authorization_pending":
                    continue
                elif error_code == "slow_down":
                    interval += 5
                    continue
                elif error_code == "expired_token":
                    raise AuthenticationError("Device code expired. Please try again.")
                elif error_code == "authorization_declined":
                    raise AuthenticationError("User declined authorization.")
                else:
                    raise AuthenticationError(
                        f"Authentication failed: {error_body.get('error_description', error_code)}"
                    )

        raise AuthenticationError("Authentication timed out. Please try again.")

    def refresh_token(self, refresh_token: str) -> TokenInfo:
        """
        Refresh an access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New TokenInfo with fresh access token

        Raises:
            TokenRefreshError: If refresh fails
        """
        url = f"{self.authority_url}{TOKEN_ENDPOINT}"

        data = (
            f"client_id={self.client_id}"
            f"&grant_type=refresh_token"
            f"&refresh_token={refresh_token}"
            f"&scope={' '.join(SCOPES)}"
        ).encode()

        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())

                return TokenInfo(
                    access_token=result["access_token"],
                    refresh_token=result.get("refresh_token", refresh_token),
                    expires_at=int(time.time()) + result.get("expires_in", 3600),
                    token_type=result.get("token_type", "Bearer"),
                    scope=result.get("scope", ""),
                )

        except HTTPError as e:
            error_body = e.read().decode()
            raise TokenRefreshError(f"Failed to refresh token: {error_body}")